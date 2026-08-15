"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, ContactShadows, Html } from "@react-three/drei";
import * as THREE from "three";

const MODEL_URL = "/models/dna.glb";

interface HotspotDef {
  id: string;
  yFraction: number; // -1..1 along the model's vertical extent
  angleDeg: number; // target direction around the vertical axis
  label: string;
  detail: string;
}

interface ResolvedHotspot {
  id: string;
  position: [number, number, number];
  label: string;
  detail: string;
}

// Standard B-DNA structural vocabulary — illustrative labels on the
// decorative hero model, not derived from any sequence/engine data.
// Positions are resolved at runtime by snapping to the nearest actual mesh
// vertex (see resolveHotspots) rather than hardcoded, since the source
// model's proportions/orientation aren't known in advance.
const HOTSPOT_DEFS: HotspotDef[] = [
  { id: "5prime", yFraction: 0.72, angleDeg: 35, label: "5′ terminus", detail: "The free phosphate end of a strand." },
  { id: "major-groove", yFraction: 0.32, angleDeg: 205, label: "Major groove", detail: "The wider groove — where most proteins read the sequence." },
  { id: "base-pair", yFraction: 0, angleDeg: 95, label: "Base pair", detail: "Hydrogen-bonded A–T and G–C pairs." },
  { id: "minor-groove", yFraction: -0.32, angleDeg: 320, label: "Minor groove", detail: "The narrower groove between the two backbones." },
  { id: "backbone", yFraction: -0.72, angleDeg: 150, label: "Sugar–phosphate backbone", detail: "The structural chain linking each nucleotide." },
];

function findFirstMesh(root: THREE.Object3D): THREE.Mesh | null {
  let found: THREE.Mesh | null = null;
  root.traverse((child) => {
    if (!found && child instanceof THREE.Mesh) found = child;
  });
  return found;
}

/** Largest-eigenvector direction of a point cloud via power iteration — the
 * mesh's true long axis, whatever arbitrary angle it was authored at. */
function principalAxis(points: THREE.Vector3[]): THREE.Vector3 {
  const centroid = new THREE.Vector3();
  points.forEach((p) => centroid.add(p));
  centroid.divideScalar(points.length);

  let xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
  const d = new THREE.Vector3();
  points.forEach((p) => {
    d.subVectors(p, centroid);
    xx += d.x * d.x;
    xy += d.x * d.y;
    xz += d.x * d.z;
    yy += d.y * d.y;
    yz += d.y * d.z;
    zz += d.z * d.z;
  });
  const n = points.length;
  xx /= n; xy /= n; xz /= n; yy /= n; yz /= n; zz /= n;

  let v = new THREE.Vector3(1, 1, 1).normalize();
  for (let i = 0; i < 60; i++) {
    const next = new THREE.Vector3(
      xx * v.x + xy * v.y + xz * v.z,
      xy * v.x + yy * v.y + yz * v.z,
      xz * v.x + yz * v.y + zz * v.z
    );
    if (next.lengthSq() < 1e-12) break;
    v = next.normalize();
  }
  return v;
}

/** Sample world-space positions of a mesh's vertices (subsampled for speed),
 * using its current (fully transformed) matrixWorld. */
function sampleWorldVertices(mesh: THREE.Mesh, targetCount: number): THREE.Vector3[] {
  const posAttr = mesh.geometry.attributes.position;
  const step = Math.max(1, Math.floor(posAttr.count / targetCount));
  const samples: THREE.Vector3[] = [];
  const tmp = new THREE.Vector3();
  for (let i = 0; i < posAttr.count; i += step) {
    tmp.fromBufferAttribute(posAttr, i);
    tmp.applyMatrix4(mesh.matrixWorld);
    samples.push(tmp.clone());
  }
  return samples;
}

/** For each desired (height, angle) slot, snap to whichever sampled vertex
 * is actually closest — guarantees every hotspot lands on real geometry
 * instead of a raycast that can miss through the helix's open gaps. */
function resolveHotspots(samplePoints: THREE.Vector3[], halfHeight: number, radius: number): ResolvedHotspot[] {
  return HOTSPOT_DEFS.map((def) => {
    const angle = (def.angleDeg * Math.PI) / 180;
    const target = new THREE.Vector3(Math.cos(angle) * radius, halfHeight * def.yFraction, Math.sin(angle) * radius);
    let best = samplePoints[0];
    let bestDistSq = Infinity;
    for (const p of samplePoints) {
      const distSq = p.distanceToSquared(target);
      if (distSq < bestDistSq) {
        bestDistSq = distSq;
        best = p;
      }
    }
    return { id: def.id, label: def.label, detail: def.detail, position: [best.x, best.y, best.z] };
  });
}

interface ModelProps {
  autoRotate: boolean;
  activeId: string | null;
  onSelect: (id: string | null) => void;
}

function Model({ autoRotate, activeId, onSelect }: ModelProps) {
  const { scene } = useGLTF(MODEL_URL);
  const ref = useRef<THREE.Group>(null);

  // The source glTF export varies wildly in scale/origin — normalize to a
  // fixed bounding size centered at the origin so it frames consistently.
  const { object, hotspots } = useMemo(() => {
    const clone = scene.clone(true);
    clone.updateMatrixWorld(true);

    const meshNode = findFirstMesh(clone);

    // The source mesh's long axis can be authored at an arbitrary diagonal
    // angle (not just a 90°-multiple tilt), so find it via PCA on the actual
    // vertex cloud and rotate that exact axis onto world Y — this is what
    // makes the helix stand upright regardless of how it was exported.
    if (meshNode) {
      const posAttr = meshNode.geometry.attributes.position;
      const step = Math.max(1, Math.floor(posAttr.count / 1000));
      const samples: THREE.Vector3[] = [];
      const tmp = new THREE.Vector3();
      for (let i = 0; i < posAttr.count; i += step) {
        tmp.fromBufferAttribute(posAttr, i);
        tmp.applyMatrix4(meshNode.matrixWorld);
        samples.push(tmp.clone());
      }
      const axis = principalAxis(samples);
      clone.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(axis.normalize(), new THREE.Vector3(0, 1, 0)));
      clone.updateMatrixWorld(true);
    }

    const box = new THREE.Box3().setFromObject(clone);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 8 / maxDim;
    const center = new THREE.Vector3();
    box.getCenter(center);
    // Position is applied in parent (already-scaled-by-`scale`) space, so the
    // centering offset must be scaled too, or it dwarfs the resized geometry
    // and pushes the model far outside the camera's view frustum.
    clone.scale.setScalar(scale);
    clone.position.copy(center).multiplyScalar(-scale);
    clone.updateMatrixWorld(true);

    // The source PBR material reads near-black without an HDRI environment
    // (no reflections to light the metal/roughness response) — cap metalness
    // and lift the color multiplier so it stays legible as a lab specimen
    // against the dark clinical backdrop instead of going fully black.
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
        const mat = child.material;
        mat.metalness = Math.min(mat.metalness, 0.2);
        mat.roughness = Math.max(mat.roughness, 0.55);
        mat.color.lerp(new THREE.Color("#eef3ee"), 0.4);
      }
    });

    const finalBox = new THREE.Box3().setFromObject(clone);
    const finalSize = new THREE.Vector3();
    finalBox.getSize(finalSize);
    const surfaceRadius = (finalSize.x + finalSize.z) / 4;
    const resolvedHotspots = meshNode
      ? resolveHotspots(sampleWorldVertices(meshNode, 4000), finalSize.y / 2, surfaceRadius)
      : [];

    return { object: clone, hotspots: resolvedHotspots };
  }, [scene]);

  useFrame((_, delta) => {
    if (autoRotate && ref.current) ref.current.rotation.y += delta * 0.2;
  });

  return (
    <group ref={ref}>
      <primitive object={object} />
      {hotspots.map((h) => (
        <Html key={h.id} position={h.position} center zIndexRange={[20, 0]}>
          <div className="relative flex items-center justify-center">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(activeId === h.id ? null : h.id);
              }}
              aria-label={h.label}
              className={`h-3 w-3 rounded-full border-2 border-background shadow-[0_0_0_3px_rgba(56,189,248,0.35)] hover:scale-125 transition-transform cursor-pointer ${
                activeId === h.id ? "bg-foreground scale-125" : "bg-primary"
              }`}
            />
            {activeId === h.id && (
              <div className="veyra-glass absolute bottom-5 left-1/2 -translate-x-1/2 w-40 h-[4.5rem] px-3 py-2 text-left overflow-hidden">
                <p className="font-mono text-[10px] uppercase tracking-wide text-accent mb-0.5 truncate">{h.label}</p>
                <p className="text-[11px] text-muted leading-snug line-clamp-3">{h.detail}</p>
              </div>
            )}
          </div>
        </Html>
      ))}
    </group>
  );
}

useGLTF.preload(MODEL_URL);

interface DnaHelixModelProps {
  autoRotate?: boolean;
  interactive?: boolean;
  className?: string;
}

export default function DnaHelixModel({ autoRotate = true, interactive = true, className }: DnaHelixModelProps) {
  const [active, setActive] = useState<string | null>(null);

  return (
    <div className={className}>
      <Canvas dpr={[1, 2]} camera={{ position: [3.0, 0, 5.2], fov: 30 }} gl={{ antialias: true, alpha: true }}>
        <hemisphereLight args={["#eef3ee", "#121512", 0.9]} />
        <ambientLight intensity={0.35} />
        <pointLight position={[5, 5, 5]} intensity={65} color="#38bdf8" />
        <pointLight position={[-5, -4, -5]} intensity={35} color="#34d399" />
        <pointLight position={[0, 6, -4]} intensity={30} color="#ffffff" />
        <Suspense fallback={null}>
          <Model autoRotate={autoRotate} activeId={active} onSelect={setActive} />
          <ContactShadows position={[0, -4.05, 0]} opacity={0.6} scale={10} blur={2.4} far={5} color="#000000" />
        </Suspense>
        {interactive && (
          <OrbitControls enablePan={false} enableZoom minDistance={3} maxDistance={10} autoRotate={false} />
        )}
      </Canvas>
    </div>
  );
}

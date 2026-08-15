"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, ContactShadows, Html } from "@react-three/drei";
import * as THREE from "three";

const MODEL_URL = "/models/dna.glb";

interface HotspotDef {
  id: string;
  yFraction: number; // -1..1 along the model's vertical extent
  angleDeg: number; // direction to raycast in from, around the vertical axis
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
// Positions are resolved at runtime by raycasting onto the actual mesh
// surface (see resolveHotspots) rather than hardcoded, since the source
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

/** Cast rays inward from outside the model at fixed heights/angles and snap
 * each hotspot to wherever it actually hits the mesh surface. */
function resolveHotspots(mesh: THREE.Mesh, halfHeight: number, outerRadius: number): ResolvedHotspot[] {
  const raycaster = new THREE.Raycaster();
  return HOTSPOT_DEFS.map((def) => {
    const angle = (def.angleDeg * Math.PI) / 180;
    const y = halfHeight * def.yFraction;
    const origin = new THREE.Vector3(Math.cos(angle) * outerRadius, y, Math.sin(angle) * outerRadius);
    const direction = new THREE.Vector3(-origin.x, 0, -origin.z).normalize();
    raycaster.set(origin, direction);
    const hit = raycaster.intersectObject(mesh, false)[0];
    const point = hit ? hit.point : new THREE.Vector3(0, y, 0);
    return { id: def.id, label: def.label, detail: def.detail, position: [point.x, point.y, point.z] };
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

  // Sketchfab exports vary wildly in scale/origin — normalize to a fixed
  // bounding size centered at the origin so it frames consistently.
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
    // and lift the color multiplier so it renders as a light, paper-theme
    // specimen instead of a dark Sketchfab-studio render.
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
        const mat = child.material;
        mat.metalness = Math.min(mat.metalness, 0.2);
        mat.roughness = Math.max(mat.roughness, 0.55);
        mat.color.lerp(new THREE.Color("#ffffff"), 0.55);
      }
    });

    const finalBox = new THREE.Box3().setFromObject(clone);
    const finalSize = new THREE.Vector3();
    finalBox.getSize(finalSize);
    const resolvedHotspots = meshNode
      ? resolveHotspots(meshNode, finalSize.y / 2, Math.max(finalSize.x, finalSize.y, finalSize.z))
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
        <Html key={h.id} position={h.position} center distanceFactor={9} zIndexRange={[20, 0]}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(activeId === h.id ? null : h.id);
            }}
            aria-label={h.label}
            className={`h-3 w-3 rounded-full border-2 border-[#fdfcf9] shadow-[0_0_0_3px_rgba(160,82,45,0.25)] hover:scale-125 transition-transform cursor-pointer ${
              activeId === h.id ? "bg-foreground scale-125" : "bg-accent"
            }`}
          />
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
  const activeDef = HOTSPOT_DEFS.find((d) => d.id === active) ?? null;

  return (
    <div className={`relative ${className ?? ""}`}>
      <Canvas dpr={[1, 2]} camera={{ position: [3.0, 0, 5.2], fov: 30 }} gl={{ antialias: true, alpha: true }}>
        <hemisphereLight args={["#fdfcf9", "#3a372f", 1.1]} />
        <ambientLight intensity={0.5} />
        <pointLight position={[5, 5, 5]} intensity={70} color="#fdfcf9" />
        <pointLight position={[-5, -4, -5]} intensity={35} color="#f2efe8" />
        <pointLight position={[0, 6, -4]} intensity={30} color="#ffffff" />
        <Suspense fallback={null}>
          <Model autoRotate={autoRotate} activeId={active} onSelect={setActive} />
          <ContactShadows position={[0, -4.05, 0]} opacity={0.35} scale={10} blur={2.4} far={5} color="#141311" />
        </Suspense>
        {interactive && (
          <OrbitControls enablePan={false} enableZoom minDistance={3} maxDistance={10} autoRotate={false} />
        )}
      </Canvas>

      {/* Fixed info panel — stays in one place regardless of which dot is
          active or how the model has rotated, instead of a card floating
          at the (moving) 3D hotspot position. */}
      {activeDef && (
        <div className="absolute bottom-4 left-4 w-56 rounded-sm border border-border bg-surface-raised px-3 py-2.5 shadow-[0_4px_12px_rgba(20,19,17,0.15)]">
          <div className="flex items-start justify-between gap-2">
            <p className="font-mono text-[10px] uppercase tracking-wide text-accent">{activeDef.label}</p>
            <button
              type="button"
              onClick={() => setActive(null)}
              aria-label="Close"
              className="text-muted hover:text-foreground leading-none text-sm cursor-pointer"
            >
              ×
            </button>
          </div>
          <p className="text-[11px] text-muted leading-snug mt-1">{activeDef.detail}</p>
        </div>
      )}
    </div>
  );
}

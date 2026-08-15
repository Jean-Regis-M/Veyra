"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, ContactShadows, Html } from "@react-three/drei";
import * as THREE from "three";

const MODEL_URL = "/models/dna.glb";

interface Hotspot {
  id: string;
  position: [number, number, number];
  label: string;
  detail: string;
}

// Standard B-DNA structural vocabulary — illustrative labels on the
// decorative hero model, not derived from any sequence/engine data.
const HOTSPOTS: Hotspot[] = [
  { id: "5prime", position: [0.9, 3.1, 0.4], label: "5′ terminus", detail: "The free phosphate end of a strand." },
  { id: "major-groove", position: [-1.1, 1.3, 0.7], label: "Major groove", detail: "The wider groove — where most proteins read the sequence." },
  { id: "base-pair", position: [1.0, -0.1, -0.6], label: "Base pair", detail: "Hydrogen-bonded A–T and G–C pairs." },
  { id: "minor-groove", position: [-0.9, -1.6, 0.6], label: "Minor groove", detail: "The narrower groove between the two backbones." },
  { id: "backbone", position: [0.8, -3.1, -0.4], label: "Sugar–phosphate backbone", detail: "The structural chain linking each nucleotide." },
];

function Model({ autoRotate }: { autoRotate: boolean }) {
  const { scene } = useGLTF(MODEL_URL);
  const ref = useRef<THREE.Group>(null);
  const [active, setActive] = useState<string | null>(null);

  // Sketchfab exports vary wildly in scale/origin — normalize to a fixed
  // bounding size centered at the origin so it frames consistently.
  const normalized = useMemo(() => {
    const clone = scene.clone(true);
    clone.updateMatrixWorld(true);

    // The Sketchfab export bakes an arbitrary camera-facing rotation into a
    // parent node, so the mesh tumbles in on a diagonal instead of standing
    // upright. Cancel it: rotate the root by the inverse of the mesh's
    // current world rotation so the mesh's own axes end up world-aligned.
    let meshNode: THREE.Object3D | null = null;
    clone.traverse((child) => {
      if (!meshNode && child instanceof THREE.Mesh) meshNode = child;
    });
    if (meshNode) {
      const worldQuat = new THREE.Quaternion();
      (meshNode as THREE.Object3D).getWorldQuaternion(worldQuat);
      clone.quaternion.copy(worldQuat.invert());
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

    return clone;
  }, [scene]);

  useFrame((_, delta) => {
    if (autoRotate && ref.current) ref.current.rotation.y += delta * 0.2;
  });

  return (
    <group ref={ref}>
      <primitive object={normalized} />
      {HOTSPOTS.map((h) => (
        <Html key={h.id} position={h.position} center distanceFactor={9} zIndexRange={[20, 0]}>
          <div className="relative flex items-center justify-center">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setActive((cur) => (cur === h.id ? null : h.id));
              }}
              aria-label={h.label}
              className="h-3 w-3 rounded-full border-2 border-[#fdfcf9] bg-accent shadow-[0_0_0_3px_rgba(160,82,45,0.25)] hover:scale-125 transition-transform cursor-pointer"
            />
            {active === h.id && (
              <div className="absolute bottom-5 left-1/2 -translate-x-1/2 w-44 rounded-sm border border-border bg-surface-raised px-3 py-2 shadow-[0_4px_12px_rgba(20,19,17,0.15)] text-left">
                <p className="font-mono text-[10px] uppercase tracking-wide text-accent mb-0.5">{h.label}</p>
                <p className="text-[11px] text-muted leading-snug">{h.detail}</p>
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
  return (
    <div className={className}>
      <Canvas dpr={[1, 2]} camera={{ position: [3.0, 0, 5.2], fov: 30 }} gl={{ antialias: true, alpha: true }}>
        <hemisphereLight args={["#fdfcf9", "#3a372f", 1.1]} />
        <ambientLight intensity={0.5} />
        <pointLight position={[5, 5, 5]} intensity={70} color="#fdfcf9" />
        <pointLight position={[-5, -4, -5]} intensity={35} color="#f2efe8" />
        <pointLight position={[0, 6, -4]} intensity={30} color="#ffffff" />
        <Suspense fallback={null}>
          <Model autoRotate={autoRotate} />
          <ContactShadows position={[0, -4.05, 0]} opacity={0.35} scale={10} blur={2.4} far={5} color="#141311" />
        </Suspense>
        {interactive && (
          <OrbitControls enablePan={false} enableZoom minDistance={3} maxDistance={10} autoRotate={false} />
        )}
      </Canvas>
    </div>
  );
}

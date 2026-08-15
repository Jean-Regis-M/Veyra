"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Instances, Instance } from "@react-three/drei";
import * as THREE from "three";

export interface HelixHighlight {
  /** base-pair index along the rendered strand */
  position: number;
  riskLevel: "low" | "moderate" | "high";
}

interface HelixSceneProps {
  basePairs: number;
  highlights: HelixHighlight[];
  autoRotate: boolean;
}

const BASE_COLORS: Record<number, string> = {
  0: "#22d3ee", // A - cyan
  1: "#a78bfa", // T - violet
  2: "#34d399", // G - emerald
  3: "#fb923c", // C - orange
};

const RISK_COLORS: Record<HelixHighlight["riskLevel"], string> = {
  low: "#34d399",
  moderate: "#fbbf24",
  high: "#f87171",
};

const RADIUS = 1.6;
const RISE_PER_BP = 0.34;
const TURN_PER_BP = (2 * Math.PI) / 10.5; // ~10.5 bp per full turn, B-DNA
const STRAND_TUBE_RADIUS = 0.13;
const SAMPLES_PER_BP = 6; // curve resolution for the tube backbone, independent of rung count

/** Cheap deterministic multi-octave sine "noise" — good enough for organic-looking
 * surface bumps without pulling in a gradient-noise dependency. */
function organicBump(x: number, y: number, z: number): number {
  return (
    Math.sin(x * 6.1 + z * 3.7) * 0.5 +
    Math.sin(y * 8.3 - x * 4.1 + 1.3) * 0.3 +
    Math.sin(z * 11.7 + y * 3.9 - 0.7) * 0.2
  );
}

function helixPoint(t: number, strandOffset: number): THREE.Vector3 {
  const angle = t * TURN_PER_BP + strandOffset;
  const y = t * RISE_PER_BP;
  return new THREE.Vector3(Math.cos(angle) * RADIUS, y, Math.sin(angle) * RADIUS);
}

/** Build a noise-displaced tube along the helical backbone curve for an organic, sculpted surface. */
function buildStrandGeometry(basePairs: number, strandOffset: number): THREE.TubeGeometry {
  const samples = Math.max(basePairs * SAMPLES_PER_BP, 16);
  const points: THREE.Vector3[] = [];
  for (let s = 0; s <= samples; s++) {
    const t = (s / samples) * (basePairs - 1);
    points.push(helixPoint(t, strandOffset));
  }
  const curve = new THREE.CatmullRomCurve3(points);
  const geometry = new THREE.TubeGeometry(curve, samples, STRAND_TUBE_RADIUS, 10, false);

  const pos = geometry.attributes.position;
  const normal = geometry.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    const nx = normal.getX(i);
    const ny = normal.getY(i);
    const nz = normal.getZ(i);
    const px = pos.getX(i);
    const py = pos.getY(i);
    const pz = pos.getZ(i);
    const bump = organicBump(px, py, pz) * 0.018;
    pos.setXYZ(i, px + nx * bump, py + ny * bump, pz + nz * bump);
  }
  pos.needsUpdate = true;
  geometry.computeVertexNormals();

  return geometry;
}

function useHelixGeometry(basePairs: number) {
  return useMemo(() => {
    const rungs: { a: THREE.Vector3; b: THREE.Vector3; mid: THREE.Vector3; colorIndex: number }[] = [];
    for (let i = 0; i < basePairs; i++) {
      const a = helixPoint(i, 0);
      const b = helixPoint(i, Math.PI);
      rungs.push({ a, b, mid: a.clone().lerp(b, 0.5), colorIndex: i % 4 });
    }
    const strandAGeometry = buildStrandGeometry(basePairs, 0);
    const strandBGeometry = buildStrandGeometry(basePairs, Math.PI);
    return { rungs, strandAGeometry, strandBGeometry };
  }, [basePairs]);
}

function HelixScene({ basePairs, highlights, autoRotate }: HelixSceneProps) {
  const group = useRef<THREE.Group>(null);
  const { rungs, strandAGeometry, strandBGeometry } = useHelixGeometry(basePairs);
  const highlightMap = useMemo(() => {
    const m = new Map<number, HelixHighlight["riskLevel"]>();
    for (const h of highlights) m.set(h.position, h.riskLevel);
    return m;
  }, [highlights]);

  useFrame((_, delta) => {
    if (autoRotate && group.current) {
      group.current.rotation.y += delta * 0.25;
    }
  });

  const centerY = ((basePairs - 1) * RISE_PER_BP) / 2;

  return (
    <group ref={group} position={[0, -centerY, 0]}>
      <mesh geometry={strandAGeometry}>
        <meshPhysicalMaterial color="#67e8f9" roughness={0.35} metalness={0.15} clearcoat={0.6} clearcoatRoughness={0.3} />
      </mesh>
      <mesh geometry={strandBGeometry}>
        <meshPhysicalMaterial color="#c4b5fd" roughness={0.35} metalness={0.15} clearcoat={0.6} clearcoatRoughness={0.3} />
      </mesh>

      <Instances limit={basePairs}>
        <cylinderGeometry args={[0.045, 0.045, RADIUS * 2 - 0.3, 8]} />
        <meshPhysicalMaterial roughness={0.4} clearcoat={0.4} />
        {rungs.map((r, i) => {
          const risk = highlightMap.get(i);
          const dir = r.b.clone().sub(r.a);
          const length = dir.length();
          const quaternion = new THREE.Quaternion().setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            dir.clone().normalize()
          );
          return (
            <Instance
              key={`rung-${i}`}
              position={r.mid}
              quaternion={quaternion}
              scale={[1, length / (RADIUS * 2 - 0.3), 1]}
              color={risk ? RISK_COLORS[risk] : BASE_COLORS[r.colorIndex]}
            />
          );
        })}
      </Instances>
    </group>
  );
}

interface DnaHelixProps {
  basePairs?: number;
  highlights?: HelixHighlight[];
  autoRotate?: boolean;
  interactive?: boolean;
  className?: string;
}

export default function DnaHelix({
  basePairs = 48,
  highlights = [],
  autoRotate = true,
  interactive = true,
  className,
}: DnaHelixProps) {
  return (
    <div className={className}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [4.5, 0, 4.5], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[5, 5, 5]} intensity={50} color="#67e8f9" />
        <pointLight position={[-5, -5, -5]} intensity={25} color="#c4b5fd" />
        <pointLight position={[0, 6, -4]} intensity={20} color="#ffffff" />
        <HelixScene basePairs={basePairs} highlights={highlights} autoRotate={autoRotate} />
        {interactive && (
          <OrbitControls
            enablePan={false}
            enableZoom={true}
            minDistance={3}
            maxDistance={12}
            autoRotate={false}
          />
        )}
      </Canvas>
    </div>
  );
}

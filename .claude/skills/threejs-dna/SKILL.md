---
name: threejs-dna
description: Use when building or editing the 3D DNA/genomic visualization component (double helix, base pairs, cut-site highlighting).
---

# Three.js DNA Visualization

## Stack

`three` + `@react-three/fiber` + `@react-three/drei`. This is the only 3D stack for this project — don't add another (no Babylon, no raw WebGL).

## Approach

- Double helix: two backbone strands as instanced tubes/spheres along a parametric helix curve, base-pair rungs connecting them at intervals. Instanced meshes (`InstancedMesh` via drei's `<Instances>`), not one mesh per base pair — a guide sequence can be 20+ bp and the site may render several candidates at once.
- Color base pairs by nucleotide (A/T/G/C) with a small fixed palette — this is a visual cue, not a data encoding that needs a legend unless the demo calls for one.
- Highlight cut sites / off-target positions by color + subtle pulse/glow on the affected rung, driven by props from the deterministic engine output — never hardcode a "risk" position.
- Wrap the canvas in a client component (`"use client"`) with a fixed-size container; use `<Canvas>` from fiber with an orbit control (`OrbitControls` from drei) so it's a centerpiece the user can rotate on the landing page.
- Keep geometry counts sane for a hackathon laptop demo: a landing-page hero helix can be decorative/looping (e.g. 40-60 bp segment), the analysis-view helix reflects the actual input sequence length capped at a reasonable render window.

## Performance

- `useMemo` for geometry/curve computation so it doesn't recompute every render.
- Cap devicePixelRatio (`dpr={[1, 2]}` on `<Canvas>`) to avoid killing frame rate on high-DPI laptops.
- Pause/reduce animation when the tab/canvas isn't visible if it becomes a battery/perf issue — not needed for MVP unless it visibly stutters.

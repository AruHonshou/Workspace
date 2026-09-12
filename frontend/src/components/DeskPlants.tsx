import { useEffect, useMemo } from "react";
import { BufferGeometry, CatmullRomCurve3, DoubleSide, Float32BufferAttribute, LatheGeometry, Matrix4, Quaternion, TubeGeometry, Vector2, Vector3 } from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { DeskPoint } from "./deskSceneCamera";

/** Cupped, tapered blades with an actual curved midrib, not ellipsoids.
 * Broad leaves have soft lobes; compact foliage has smooth pointed margins. */
export function createPlantLeaf(broad: boolean): BufferGeometry {
  const positions: number[] = [], indices: number[] = [];
  const rows = 40, columns = 8;
  for (let row = 0; row <= rows; row++) {
    const t = row / rows;
    const envelope = Math.sin(Math.PI * t) ** .78;
    const lobes = broad ? 1 - .2 * Math.sin(t * Math.PI * 4) ** 4 : 1;
    for (let col = 0; col <= columns; col++) {
      const side = col / columns * 2 - 1;
      const x = side * envelope * lobes * (broad ? .36 : .25);
      const z = .12 * Math.sin(Math.PI * t) - .24 * t * t - Math.abs(side) ** 1.6 * envelope * .085;
      positions.push(x, t, z);
    }
  }
  for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
    const a = row * (columns + 1) + col, b = a + columns + 1;
    indices.push(a, a + 1, b, b, a + 1, b + 1);
  }
  const leaf = new BufferGeometry();
  leaf.setAttribute("position", new Float32BufferAttribute(positions, 3));
  leaf.setIndex(indices); leaf.computeVertexNormals(); leaf.computeBoundingSphere();
  return leaf;
}

const palette = ["#496f4e", "#6c8058", "#3f6850", "#81966d"];
function foliage(broad: boolean) {
  const blade = createPlantLeaf(broad);
  const groups: BufferGeometry[][] = [[], [], [], []], stems: BufferGeometry[] = [], veins: BufferGeometry[] = [];
  const count = broad ? 12 : 32;
  for (let i = 0; i < count; i++) {
    const angle = i * 2.39996, tier = i % 4;
    const length = broad ? .54 + tier * .085 : .16 + (i % 3) * .025;
    const spread = broad ? .22 + (i % 3) * .095 : .09 + (i % 5) * .052;
    const origin = new Vector3(Math.sin(angle) * spread, broad ? .47 + tier * .14 : .42 + (i % 6) * .088, Math.cos(angle) * spread);
    const direction = new Vector3(Math.sin(angle) * .7, broad ? .72 + (i % 2) * .26 : .56, Math.cos(angle) * .7).normalize();
    const quaternion = new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), direction);
    // Slight twist makes different blades catch the key light naturally.
    quaternion.multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), Math.sin(angle) * .3));
    const transform = new Matrix4().compose(origin, quaternion, new Vector3(length, length, length));
    groups[i % 4].push(blade.clone().applyMatrix4(transform));
    const stemCurve = new CatmullRomCurve3([new Vector3(0, .29, 0), new Vector3(origin.x * .28, origin.y * .83, origin.z * .28), origin]);
    stems.push(new TubeGeometry(stemCurve, 10, broad ? .008 : .004, 5, false));
    if (broad) {
      const midrib = new CatmullRomCurve3([new Vector3(0, .025, .008), new Vector3(0, .4, .088), new Vector3(0, .72, -.013), new Vector3(0, .96, -.205)]);
      veins.push(new TubeGeometry(midrib, 12, .0035, 4, false).applyMatrix4(transform));
    }
  }
  blade.dispose();
  const merge = (parts: BufferGeometry[]) => {
    const merged = mergeGeometries(parts)!;
    parts.forEach(part => part.dispose());
    return merged;
  };
  return { leaves: groups.map(merge), stems: merge(stems), veins: veins.length ? merge(veins) : null };
}

export function DeskPlant({ position, scale = 1, variant = "broad" }: { position: DeskPoint; scale?: number; variant?: "broad" | "small" }) {
  const broad = variant === "broad";
  const shapes = useMemo(() => foliage(broad), [broad]);
  const pot = useMemo(() => new LatheGeometry([
    [0, .018], [.15, .018], [.181, .027], [.19, .06], [.221, .32], [.237, .351],
    [.236, .365], [.222, .371], [.208, .361], [.208, .339], [.171, .065], [0, .065],
  ].map(point => new Vector2(...point as [number, number])), 48), []);
  useEffect(() => () => { shapes.leaves.forEach(item => item.dispose()); shapes.stems.dispose(); shapes.veins?.dispose(); pot.dispose(); }, [shapes, pot]);
  return <group name={`desk-plant-${variant}`} position={position} scale={scale}>
    <mesh geometry={pot} castShadow receiveShadow>
      <meshPhysicalMaterial color={broad ? "#b4a68b" : "#858e78"} roughness={.68} clearcoat={.12} clearcoatRoughness={.65} />
    </mesh>
    <mesh position={[0, .324, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <circleGeometry args={[.204, 32]} /><meshStandardMaterial color="#292b20" roughness={1} />
    </mesh>
    {/* A raised ceramic foot anchors the pot without a razor-sharp cylinder. */}
    <mesh position={[0, .026, 0]} rotation={[-Math.PI / 2, 0, 0]} castShadow receiveShadow>
      <torusGeometry args={[.175, .013, 8, 48]} /><meshStandardMaterial color={broad ? "#948976" : "#687963"} roughness={.78} />
    </mesh>
    <mesh geometry={shapes.stems} castShadow><meshStandardMaterial color="#637346" roughness={.84} /></mesh>
    {shapes.leaves.map((geometry, i) => <mesh key={i} geometry={geometry} castShadow receiveShadow>
      <meshPhysicalMaterial color={palette[i]} roughness={.49 + i * .04} metalness={0} side={DoubleSide}
        clearcoat={.16} clearcoatRoughness={.58} emissive="#193c21" emissiveIntensity={.16} />
    </mesh>)}
    {shapes.veins && <mesh geometry={shapes.veins}><meshStandardMaterial color="#859159" roughness={.8} /></mesh>}
  </group>;
}

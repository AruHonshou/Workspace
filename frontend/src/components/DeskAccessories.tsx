import { useEffect, useMemo } from "react";
import { CatmullRomCurve3, DoubleSide, ExtrudeGeometry, Quaternion, Shape, Vector2, Vector3 } from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

type Point = [number, number, number];
type Profile = readonly (readonly [number, number])[];

/** Visual-only replacements. These world anchors deliberately match the existing
 * projected DOM hotspots; input, navigation and camera code remain elsewhere. */
export const DESK_ACCESSORY_ANCHORS = {
  notebook: [-1.65, 1.69, .12],
  coffee: [1.83, 1.595, .12],
  mouse: [1.15, 1.684, .29],
  lamp: [-2.17, 1.59, -.22],
} satisfies Record<string, Point>;

const CUP_PROFILE: Profile = [
  [0, .032], [.09, .032], [.111, .036], [.12, .053], [.122, .11],
  [.128, .235], [.135, .278], [.135, .289], [.132, .297], [.125, .299],
  [.120, .295], [.117, .285], [.115, .24], [.108, .079], [.1, .061], [0, .061],
];
const SHADE_PROFILE: Profile = [
  [.084, .154], [.085, .143], [.098, .129], [.111, .09], [.137, .049],
  [.169, .004], [.194, -.051], [.211, -.105], [.213, -.119],
  [.222, -.119], [.22, -.105], [.201, -.05], [.176, .003],
  [.145, .046], [.119, .084], [.105, .12], [.094, .148], [.084, .154],
];
const BASE_PROFILE: Profile = [
  [0, .005], [.208, .005], [.23, .011], [.238, .022], [.238, .04],
  [.23, .056], [.21, .065], [.075, .07], [0, .07],
];
const MOUSE_PROFILE: Profile = [
  [0, -.063], [.60, -.063], [.85, -.057], [.97, -.034], [1, -.006],
  [.96, .019], [.83, .046], [.60, .063], [.31, .072], [0, .075],
];
const LAMP_CORD: Point[] = [[.02, .026, -.17], [-.2, .035, -.25], [-.4, .025, -.33], [-.4, -.4, -.37]];
const CUP_HANDLE: Point[] = [[.115, .245, 0], [.178, .243, 0], [.205, .202, 0], [.201, .145, 0], [.173, .101, 0], [.116, .105, 0]];
const MOUSE_SEAM: Point[] = [[0, .049, -.123], [0, .065, -.071], [0, .074, -.018]];

function RoundedPart({ size, position, rotation, color, radius = .01, roughness = .55, metalness = 0 }: {
  size: Point; position?: Point; rotation?: Point; color: string;
  radius?: number; roughness?: number; metalness?: number;
}) {
  const geometry = useMemo(() => new RoundedBoxGeometry(
    ...size, 3, Math.min(radius, ...size.map((value) => value / 2)),
  ), [size[0], size[1], size[2], radius]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} position={position} rotation={rotation} castShadow receiveShadow>
    <meshStandardMaterial color={color} roughness={roughness} metalness={metalness} />
  </mesh>;
}

function LathedPart({ profile, color, roughness = .5, metalness = 0, clearcoat = 0, scale }: {
  profile: Profile; color: string; roughness?: number; metalness?: number; clearcoat?: number; scale?: Point;
}) {
  const points = useMemo(() => profile.map(([radius, height]) => new Vector2(radius, height)), [profile]);
  return <mesh scale={scale} castShadow receiveShadow>
    <latheGeometry args={[points, 48]} />
    <meshPhysicalMaterial color={color} roughness={roughness} metalness={metalness}
      clearcoat={clearcoat} clearcoatRoughness={.3} />
  </mesh>;
}

/** The notebook's plan corners can be round without inflating its thin covers. */
function BookLayer({ size, y, x = 0, color, roughness }: {
  size: Point; y: number; x?: number; color: string; roughness: number;
}) {
  const geometry = useMemo(() => {
    const halfWidth = (size[0] - .004) / 2;
    const halfDepth = (size[2] - .004) / 2;
    const corner = .028;
    const outline = new Shape();
    outline.moveTo(-halfWidth + corner, -halfDepth);
    outline.lineTo(halfWidth - corner, -halfDepth);
    outline.quadraticCurveTo(halfWidth, -halfDepth, halfWidth, -halfDepth + corner);
    outline.lineTo(halfWidth, halfDepth - corner);
    outline.quadraticCurveTo(halfWidth, halfDepth, halfWidth - corner, halfDepth);
    outline.lineTo(-halfWidth + corner, halfDepth);
    outline.quadraticCurveTo(-halfWidth, halfDepth, -halfWidth, halfDepth - corner);
    outline.lineTo(-halfWidth, -halfDepth + corner);
    outline.quadraticCurveTo(-halfWidth, -halfDepth, -halfWidth + corner, -halfDepth);
    const depth = size[1] - .004;
    const result = new ExtrudeGeometry(outline, {
      depth, steps: 1, bevelEnabled: true, bevelSize: .002, bevelThickness: .002, bevelSegments: 2, curveSegments: 4,
    });
    result.translate(0, 0, -depth / 2);
    result.rotateX(-Math.PI / 2);
    return result;
  }, [size[0], size[1], size[2]]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh position={[x, y, 0]} geometry={geometry} castShadow receiveShadow>
    <meshStandardMaterial color={color} roughness={roughness} />
  </mesh>;
}

function Rod({ from, to, radius, endRadius = radius, color, roughness = .4, metalness = .65 }: {
  from: Point; to: Point; radius: number; endRadius?: number;
  color: string; roughness?: number; metalness?: number;
}) {
  const transform = useMemo(() => {
    const first = new Vector3(...from);
    const last = new Vector3(...to);
    const direction = last.clone().sub(first);
    return {
      position: first.add(last).multiplyScalar(.5),
      quaternion: new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), direction.clone().normalize()),
      length: direction.length(),
    };
  }, [from[0], from[1], from[2], to[0], to[1], to[2]]);
  return <mesh position={transform.position} quaternion={transform.quaternion} castShadow receiveShadow>
    <cylinderGeometry args={[endRadius, radius, transform.length, 16]} />
    <meshStandardMaterial color={color} metalness={metalness} roughness={roughness} />
  </mesh>;
}

function Tube({ points, radius, color, roughness = .6, metalness = 0, clearcoat = 0 }: {
  points: Point[]; radius: number; color: string; roughness?: number; metalness?: number; clearcoat?: number;
}) {
  const curve = useMemo(() => new CatmullRomCurve3(points.map((point) => new Vector3(...point))), [points]);
  return <mesh castShadow receiveShadow>
    <tubeGeometry args={[curve, 28, radius, 8, false]} />
    <meshPhysicalMaterial color={color} roughness={roughness} metalness={metalness}
      clearcoat={clearcoat} clearcoatRoughness={.3} />
  </mesh>;
}

function Hinge({ position, radius = .047 }: { position: Point; radius?: number }) {
  return <group position={position}>
    <mesh rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[radius, radius, .078, 24]} />
      <meshStandardMaterial color="#9d7f49" metalness={.76} roughness={.36} />
    </mesh>
    <mesh position={[0, 0, .041]} rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[radius * .61, radius * .61, .008, 20]} />
      <meshStandardMaterial color="#384b42" metalness={.55} roughness={.43} />
    </mesh>
    <RoundedPart position={[0, 0, .047]} size={[radius * .59, .006, .003]} color="#b79b66" radius={.002} metalness={.8} />
  </group>;
}

export function DeskLamp() {
  return <group position={DESK_ACCESSORY_ANCHORS.lamp}>
    <LathedPart profile={BASE_PROFILE} color="#4c5b45" roughness={.39} metalness={.55} />
    <mesh position={[0, .061, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[.211, .003, 6, 48]} />
      <meshStandardMaterial color="#aa8b50" metalness={.8} roughness={.38} />
    </mesh>
    <Rod from={[0, .066, 0]} to={[0, .17, 0]} radius={.038} color="#52634e" />
    {[-.028, .028].map((z) => <group key={z}>
      <Rod from={[0, .17, z]} to={[-.1, .65, -.04 + z]} radius={.016} color="#435646" roughness={.47} />
      <Rod from={[-.1, .65, -.04 + z]} to={[.27, 1.25, .04 + z]} radius={.016} color="#435646" roughness={.47} />
    </group>)}
    <Hinge position={[0, .17, 0]} />
    <Hinge position={[-.1, .65, -.04]} />
    <Hinge position={[.27, 1.25, .04]} radius={.035} />
    <group position={[.23, 1.07, .16]} rotation={[-.6, 0, -.3]}>
      <LathedPart profile={SHADE_PROFILE} color="#3d5140" roughness={.38} metalness={.58} />
      <Rod from={[0, .147, 0]} to={[0, .212, 0]} radius={.065} color="#485c45" />
      <Rod from={[0, .212, 0]} to={[0, .231, 0]} radius={.021} color="#aa8a53" />
      <mesh position={[0, -.12, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[.217, .005, 8, 48]} />
        <meshStandardMaterial color="#b59861" metalness={.72} roughness={.37} />
      </mesh>
      <mesh position={[0, -.115, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[.209, 40]} />
        <meshStandardMaterial color="#fff1d0" emissive="#ffca7b" emissiveIntensity={1.8} roughness={.7} side={DoubleSide} />
      </mesh>
      {/* Reuses the original single practical light and its location; no extra shadow pass. */}
      <pointLight position={[0, -.17, 0]} color="#ffd5a0" intensity={2.2} distance={3.4} decay={2} />
    </group>
    <Tube points={LAMP_CORD} radius={.007} color="#26332e" roughness={.9} />
  </group>;
}

export function DeskNotebook() {
  return <group position={DESK_ACCESSORY_ANCHORS.notebook} rotation={[0, .14, 0]}>
    <BookLayer size={[.625, .019, .805]} y={-.074} color="#405c4b" roughness={.78} />
    <BookLayer size={[.58, .056, .765]} x={.008} y={-.038} color="#e9dfc7" roughness={.9} />
    <BookLayer size={[.625, .019, .805]} y={-.002} color="#6d8060" roughness={.77} />
    <RoundedPart size={[.026, .079, .798]} position={[-.298, -.038, 0]} color="#4e694f" radius={.012} roughness={.83} />
    {[-.059, -.047, -.035, -.023].map((y) => <RoundedPart key={y}
      size={[.559, .0014, .002]} position={[.011, y, .383]} color="#c7bea8" radius={.0006} roughness={1} />)}
    <RoundedPart size={[.037, .005, .812]} position={[.205, .01, 0]} color="#2b493b" radius={.002} roughness={.94} />
    {[-.403, .403].map((z) => <RoundedPart key={z} size={[.037, .084, .006]} position={[.205, -.03, z]}
      color="#2b493b" radius={.002} roughness={.94} />)}
    <RoundedPart size={[.018, .002, .12]} position={[-.12, -.067, .43]} color="#b59761" radius={.001} roughness={.85} />
    {/* A cap, ferrule and separate metal tip refine the existing diagonal pen. */}
    <Rod from={[-.18, .035, .28]} to={[.06, .035, -.18]} radius={.012} color="#23463c" roughness={.3} metalness={.5} />
    <Rod from={[.06, .035, -.18]} to={[.08, .035, -.218]} radius={.012} endRadius={.009} color="#b59960" roughness={.3} metalness={.8} />
    <Rod from={[.08, .035, -.218]} to={[.1, .035, -.256]} radius={.009} endRadius={.0015} color="#c7c9bd" roughness={.28} metalness={.85} />
    <Rod from={[-.18, .035, .28]} to={[-.17, .035, .261]} radius={.013} color="#aa915c" roughness={.36} metalness={.75} />
    <Rod from={[-.165, .049, .257]} to={[-.127, .049, .184]} radius={.0025} color="#b99e64" metalness={.8} />
  </group>;
}

export function DeskCoffee() {
  return <group position={DESK_ACCESSORY_ANCHORS.coffee}>
    <mesh position={[0, .015, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[.197, .2, .022, 48]} />
      <meshStandardMaterial color="#405744" roughness={.91} />
    </mesh>
    <mesh position={[0, .027, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <ringGeometry args={[.178, .189, 48]} />
      <meshStandardMaterial color="#6c7a54" roughness={.91} />
    </mesh>
    <LathedPart profile={CUP_PROFILE} color="#e6dbc2" roughness={.31} clearcoat={.24} />
    <Tube points={CUP_HANDLE} radius={.022} color="#e6dbc2" roughness={.31} clearcoat={.24} />
    <mesh position={[0, .267, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <circleGeometry args={[.115, 48]} />
      <meshPhysicalMaterial color="#241711" roughness={.24} clearcoat={.5} clearcoatRoughness={.2} />
    </mesh>
    <mesh position={[0, .268, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[.108, .115, 48]} />
      <meshStandardMaterial color="#624124" roughness={.4} />
    </mesh>
  </group>;
}

export function DeskMouse() {
  return <group position={DESK_ACCESSORY_ANCHORS.mouse}>
    <RoundedPart size={[.177, .015, .269]} position={[0, -.064, 0]} color="#34423b" radius={.007} roughness={.9} />
    <LathedPart profile={MOUSE_PROFILE} scale={[.12, 1, .18]} color="#d8d9c8" roughness={.4} clearcoat={.1} />
    <Tube points={MOUSE_SEAM} radius={.0012} color="#7e8b7d" roughness={.76} />
    <RoundedPart size={[.018, .005, .054]} position={[0, .066, -.065]} color="#4c6256" radius={.002} roughness={.88} />
    <mesh position={[0, .069, -.066]} rotation={[0, 0, Math.PI / 2]} castShadow>
      <cylinderGeometry args={[.018, .018, .012, 24]} />
      <meshStandardMaterial color="#95a38a" metalness={.18} roughness={.6} />
    </mesh>
  </group>;
}

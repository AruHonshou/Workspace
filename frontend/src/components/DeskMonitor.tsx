import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { BoxGeometry, ExtrudeGeometry, MeshBasicMaterial, PlaneGeometry, Shape } from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { DESK_SCREEN, type DeskPhase, type DeskPoint } from "./deskSceneCamera";

export type DeskMonitorProps = {
  phase: DeskPhase;
  progress: MutableRefObject<number>;
  locale: "es" | "en";
};

type MonitorPart = { size: DeskPoint; position: DeskPoint };
const [screenX, screenY, screenZ] = DESK_SCREEN.center;

/** The center is the deepest point of the shallow, cylindrical display. The
 * screen, bezel and enclosure share this curve so their edges stay together. */
export function monitorCurveOffset(x: number): number {
  const depth = DESK_SCREEN.curvatureDepth;
  if (depth <= 0) return 0;
  const radius = DESK_SCREEN.width ** 2 / (8 * depth) + depth / 2;
  return radius - Math.sqrt(Math.max(0, radius ** 2 - x ** 2));
}

export const MONITOR_GEOMETRY = {
  deskSurface: 1.59,
  chassis: {
    size: [DESK_SCREEN.width + 0.06, DESK_SCREEN.height + 0.065, 0.056],
    position: [screenX, screenY - 0.0025, screenZ - 0.035],
  } satisfies MonitorPart,
  bezel: {
    size: [DESK_SCREEN.width + 0.036, DESK_SCREEN.height + 0.041, 0.016],
    position: [screenX, screenY - 0.0025, screenZ - 0.004],
  } satisfies MonitorPart,
  mount: {
    size: [0.43, 0.36, 0.075],
    position: [screenX, 2.31, screenZ - 0.093],
  } satisfies MonitorPart,
  column: {
    size: [0.43, 0.775, 0.1],
    position: [screenX, 2.005, screenZ - 0.165],
  } satisfies MonitorPart,
  base: {
    size: [0.97, 0.033, 0.61],
    position: [screenX, 1.6065, screenZ + 0.095],
  } satisfies MonitorPart,
  displayZ: screenZ + 0.007,
  offSurface: { color: "#101c23", material: "MeshBasicMaterial", toneMapped: false },
} as const;

/** Only the plain display backing changes during the move into the browser.
 * The accessible hero itself is rendered by the DOM over the screen. */
export function monitorPower(phase: DeskPhase, progress: number): number {
  const safeProgress = Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0;
  if (phase === "home") return 0;
  if (phase === "working") return 1;
  if (phase === "leaving") return safeProgress ** 4;
  return Math.min(1, safeProgress * 2.5);
}

function HousingPart({ size, position, color, radius = 0.012, roughness = 0.42, metalness = 0.6 }: MonitorPart & {
  color: string; radius?: number; roughness?: number; metalness?: number;
}) {
  const geometry = useMemo(() => new RoundedBoxGeometry(
    size[0], size[1], size[2], 3,
    Math.min(radius, ...size.map((dimension) => dimension / 2)),
  ), [size[0], size[1], size[2], radius]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} position={position} castShadow receiveShadow>
    <meshPhysicalMaterial color={color} roughness={roughness} metalness={metalness} clearcoat={.12} clearcoatRoughness={.48} />
  </mesh>;
}

function CurvedHousing({ size, position, color, metalness, roughness }: MonitorPart & {
  color: string; metalness: number; roughness: number;
}) {
  const geometry = useMemo(() => {
    const curved = new BoxGeometry(size[0], size[1], size[2], 64, 1, 1);
    const vertices = curved.attributes.position;
    for (let index = 0; index < vertices.count; index += 1) {
      vertices.setZ(index, vertices.getZ(index) + monitorCurveOffset(vertices.getX(index)));
    }
    curved.computeVertexNormals();
    return curved;
  }, [size[0], size[1], size[2]]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} position={position} castShadow receiveShadow>
    <meshPhysicalMaterial color={color} roughness={roughness} metalness={metalness} clearcoat={.08} clearcoatRoughness={.5} />
  </mesh>;
}

function TaperedStand() {
  const { column } = MONITOR_GEOMETRY;
  const geometry = useMemo(() => {
    const halfWidth = column.size[0] / 2;
    const halfHeight = column.size[1] / 2;
    const shape = new Shape();
    shape.moveTo(-halfWidth, -halfHeight);
    shape.lineTo(halfWidth, -halfHeight);
    shape.lineTo(halfWidth * 0.66, halfHeight);
    shape.lineTo(-halfWidth * 0.66, halfHeight);
    shape.closePath();
    const stand = new ExtrudeGeometry(shape, {
      depth: column.size[2] - 0.008,
      bevelEnabled: true,
      bevelThickness: 0.004,
      bevelSize: 0.004,
      bevelSegments: 2,
      steps: 1,
    });
    stand.translate(0, 0, -(column.size[2] - 0.008) / 2);
    return stand;
  }, [column]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh name="monitor-tapered-stand" geometry={geometry} position={column.position} castShadow receiveShadow>
    <meshPhysicalMaterial color="#8d9b9b" metalness={0.72} roughness={0.36} clearcoat={.1} clearcoatRoughness={.5} />
  </mesh>;
}

export function DeskMonitor({ phase, progress }: DeskMonitorProps) {
  const poweredDisplay = useRef<MeshBasicMaterial>(null);
  const indicator = useRef<MeshBasicMaterial>(null);
  const displayGeometry = useMemo(() => {
    const geometry = new PlaneGeometry(DESK_SCREEN.width, DESK_SCREEN.height, 64, 1);
    const vertices = geometry.attributes.position;
    for (let index = 0; index < vertices.count; index += 1) {
      vertices.setZ(index, monitorCurveOffset(vertices.getX(index)));
    }
    geometry.computeVertexNormals();
    return geometry;
  }, []);
  useEffect(() => () => displayGeometry.dispose(), [displayGeometry]);

  useFrame(() => {
    const power = monitorPower(phase, progress.current);
    if (poweredDisplay.current) poweredDisplay.current.opacity = power;
    if (indicator.current) indicator.current.opacity = 0.45 + power * 0.25;
  });

  const { chassis, bezel, mount, base, displayZ, offSurface } = MONITOR_GEOMETRY;
  const initialPower = monitorPower(phase, progress.current);

  return <group name="desktop-monitor">
    {/* Original thin silver shell and charcoal gasket follow the same curve. */}
    <CurvedHousing {...chassis} color="#a2b1ad" roughness={0.36} metalness={0.75} />
    <CurvedHousing {...bezel} color="#192328" roughness={0.86} metalness={0.12} />

    <mesh name="monitor-off-display" geometry={displayGeometry} position={[screenX, screenY, displayZ]}>
      <meshBasicMaterial color={offSurface.color} toneMapped={offSurface.toneMapped} />
    </mesh>
    <mesh name="monitor-on-display" geometry={displayGeometry} position={[screenX, screenY, displayZ + 0.001]}>
      <meshBasicMaterial
        ref={poweredDisplay}
        color="#f5f6f3"
        toneMapped={false}
        transparent
        depthWrite={false}
        opacity={initialPower}
      />
    </mesh>

    {/* The broad upright is wholly behind the deepest part of the enclosure. */}
    <HousingPart {...mount} color="#8f9da1" radius={0.035} />
    <TaperedStand />
    <HousingPart {...base} color="#a7b3ad" radius={0.012} roughness={0.38} metalness={0.72} />

    {/* Subtle hardware detail, with no branding or generated screen content. */}
    <mesh position={[screenX + DESK_SCREEN.width * 0.4, screenY - DESK_SCREEN.height / 2 - 0.01,
      displayZ + monitorCurveOffset(DESK_SCREEN.width * 0.4)]}>
      <planeGeometry args={[0.015, 0.003]} />
      <meshBasicMaterial ref={indicator} color="#b2cbc7" transparent opacity={0.45 + initialPower * 0.25} toneMapped={false} depthWrite={false} />
    </mesh>
  </group>;
}

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import {
  BufferGeometry,
  CanvasTexture,
  DynamicDrawUsage,
  Float32BufferAttribute,
  InstancedMesh,
  Mesh,
  Object3D,
  SRGBColorSpace,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

type KeyColor = "ivory" | "sage" | "orange";
type DeskKey = { code: string; label: string; secondary?: string; units: number; column: number; row: number; color: KeyColor };
type KeySpec = [code: string, label: string, units?: number, color?: KeyColor, secondary?: string];
type Point = [number, number, number];

const PITCH = 0.103;
const BASE_WIDTH = 0.095;
const KEY_DEPTH = 0.078;
const CAP_HEIGHT = 0.052;
const ROW_Z = [-0.239, -0.136, -0.046, 0.044, 0.134, 0.224];
const ROW_Y = [0.05, 0.046, 0.04, 0.037, 0.039, 0.042];
const KEY_COLORS: Record<KeyColor, string> = { ivory: "#e7e2d5", sage: "#84988a", orange: "#c66c40" };

function row(rowIndex: number, specs: KeySpec[], offset = 0): DeskKey[] {
  let column = offset;
  return specs.map(([code, label, units = 1, color = "ivory", secondary]) => {
    const key = { code, label, units, column, row: rowIndex, color, secondary };
    column += units;
    return key;
  });
}

function letters(value: string): KeySpec[] {
  return [...value].map((letter) => [`Key${letter}`, letter]);
}

/** Authored ANSI 75% layout, with actual modifier widths and row staggering. */
export const DESK_KEYS: readonly DeskKey[] = [
  ...row(0, [["Escape", "Esc", 1, "orange"]]),
  ...[0, 1, 2].flatMap((block) => row(0, Array.from({ length: 4 }, (_, index): KeySpec => {
    const number = block * 4 + index + 1;
    return [`F${number}`, `F${number}`, 1, "sage"];
  }), 1.5 + block * 4.5)),
  ...row(0, [["Delete", "Del", 1, "sage"]], 15.25),
  ...row(1, [
    ["Backquote", "`", 1, "ivory", "~"],
    ...[..."1234567890"].map((digit, index): KeySpec => [`Digit${digit}`, digit, 1, "ivory", "!@#$%^&*()"[index]]),
    ["Minus", "−", 1, "ivory", "_"], ["Equal", "=", 1, "ivory", "+"], ["Backspace", "Back", 2, "sage"],
  ]),
  ...row(1, [["Home", "Home", 1, "sage"]], 15.25),
  ...row(2, [
    ["Tab", "Tab", 1.5, "sage"], ...letters("QWERTYUIOP"),
    ["BracketLeft", "[", 1, "ivory", "{"], ["BracketRight", "]", 1, "ivory", "}"],
    ["Backslash", "\\", 1.5, "ivory", "|"],
  ]),
  ...row(2, [["PageUp", "PgUp", 1, "sage"]], 15.25),
  ...row(3, [
    ["CapsLock", "Caps", 1.75, "sage"], ...letters("ASDFGHJKL"),
    ["Semicolon", ";", 1, "ivory", ":"], ["Quote", "'", 1, "ivory", '"'], ["Enter", "Enter", 2.25, "sage"],
  ]),
  ...row(3, [["PageDown", "PgDn", 1, "sage"]], 15.25),
  ...row(4, [
    ["ShiftLeft", "Shift", 2.25, "sage"], ...letters("ZXCVBNM"),
    ["Comma", ",", 1, "ivory", "<"], ["Period", ".", 1, "ivory", ">"], ["Slash", "/", 1, "ivory", "?"],
    ["ShiftRight", "Shift", 1.75, "sage"],
  ]),
  ...row(4, [["ArrowUp", "↑", 1, "sage"], ["End", "End", 1, "sage"]], 14.25),
  ...row(5, [
    ["ControlLeft", "Ctrl", 1.25, "sage"], ["MetaLeft", "Win", 1.25, "sage"], ["AltLeft", "Alt", 1.25, "sage"],
    ["Space", "", 6.25], ["AltRight", "Alt", 1, "sage"], ["Fn", "Fn", 1, "sage"], ["ControlRight", "Ctrl", 1, "sage"],
  ]),
  ...row(5, [["ArrowLeft", "←", 1, "sage"], ["ArrowDown", "↓", 1, "sage"], ["ArrowRight", "→", 1, "sage"]], 13.25),
];

const CODE_INDEX = new Map(DESK_KEYS.map((key, index) => [key.code, index]));
const COLOR_KEYS = (Object.keys(KEY_COLORS) as KeyColor[]).map((color) => ({
  color, indices: DESK_KEYS.flatMap((key, index) => key.color === color ? [index] : []),
}));

function keyPosition(key: DeskKey, depression = 0): Point {
  return [(key.column + key.units / 2 - 8.125) * PITCH, ROW_Y[key.row] + depression, ROW_Z[key.row]];
}

function keyWidth(key: DeskKey) { return key.units * PITCH - 0.008; }

/** No input text is read. Physical key codes are used only while this decorative
 * keyboard is enabled, and only outside all forms and editable controls. */
export function keyboardMayReact(event: Pick<KeyboardEvent, "target" | "defaultPrevented" | "isComposing">, activeElement: Element | null): boolean {
  const isEditable = (target: EventTarget | null) => target instanceof Element && Boolean(target.closest(
    'form,input,textarea,select,button,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="combobox"]',
  ));
  return !event.defaultPrevented && !event.isComposing && !isEditable(event.target) && !isEditable(activeElement);
}

/** Rounded, tapered skirt and gently dished top. All geometry is authored here;
 * no simulator source, model, font, sound, or remote texture is loaded. */
function createKeycapGeometry(): BufferGeometry {
  const vertices: number[] = [];
  const indices: number[] = [];
  const segments = 32;
  const rings = [
    { width: BASE_WIDTH, depth: KEY_DEPTH, radius: 0.009, y: 0 },
    { width: BASE_WIDTH, depth: KEY_DEPTH, radius: 0.009, y: 0.01 },
    { width: 0.083, depth: 0.067, radius: 0.008, y: CAP_HEIGHT - 0.006 },
    { width: 0.078, depth: 0.063, radius: 0.009, y: CAP_HEIGHT },
    { width: 0.047, depth: 0.036, radius: 0.012, y: CAP_HEIGHT - 0.0015 },
    { width: 0.015, depth: 0.012, radius: 0.005, y: CAP_HEIGHT - 0.0025 },
  ];
  for (const ring of rings) {
    for (let point = 0; point < segments; point += 1) {
      const corner = Math.floor(point / 8);
      const angle = corner * Math.PI / 2 + (point % 8) / 7 * Math.PI / 2;
      const centerX = (corner === 0 || corner === 3 ? 1 : -1) * (ring.width / 2 - ring.radius);
      const centerZ = (corner < 2 ? 1 : -1) * (ring.depth / 2 - ring.radius);
      vertices.push(centerX + Math.cos(angle) * ring.radius, ring.y, centerZ + Math.sin(angle) * ring.radius);
    }
  }
  for (let ring = 0; ring < rings.length - 1; ring += 1) {
    for (let point = 0; point < segments; point += 1) {
      const next = (point + 1) % segments;
      const a = ring * segments + point;
      const b = ring * segments + next;
      const c = (ring + 1) * segments + point;
      const d = (ring + 1) * segments + next;
      indices.push(a, c, b, b, c, d);
    }
  }
  const center = vertices.length / 3;
  vertices.push(0, CAP_HEIGHT - 0.0027, 0);
  const lastRing = (rings.length - 1) * segments;
  for (let point = 0; point < segments; point += 1) indices.push(lastRing + point, center, lastRing + (point + 1) % segments);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

function createLegends(): { texture: CanvasTexture | null; geometry: BufferGeometry } {
  const canvas = document.createElement("canvas");
  canvas.width = 2048;
  canvas.height = 1024;
  const context = canvas.getContext("2d");
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  DESK_KEYS.forEach((key, index) => {
    const tileX = index % 16;
    const tileY = Math.floor(index / 16);
    if (context) {
      context.fillStyle = key.color === "orange" ? "#fff2de" : "#24322e";
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.font = `${key.label.length > 2 ? "600 23" : "500 34"}px Arial, sans-serif`;
      context.fillText(key.label, tileX * 128 + 64, tileY * 128 + (key.secondary ? 82 : 61));
      if (key.secondary) {
        context.font = "500 22px Arial, sans-serif";
        context.fillText(key.secondary, tileX * 128 + 64, tileY * 128 + 34);
      }
    }
    const [x, y, z] = keyPosition(key);
    const labelX = x - (key.units > 1.3 && key.code !== "Space" ? keyWidth(key) / 2 - 0.055 : 0);
    const halfWidth = 0.035;
    const halfDepth = 0.027;
    positions.push(labelX - halfWidth, y + CAP_HEIGHT + 0.0003, z + halfDepth,
      labelX + halfWidth, y + CAP_HEIGHT + 0.0003, z + halfDepth,
      labelX - halfWidth, y + CAP_HEIGHT + 0.0003, z - halfDepth,
      labelX + halfWidth, y + CAP_HEIGHT + 0.0003, z - halfDepth);
    const u0 = tileX / 16;
    const u1 = (tileX + 1) / 16;
    const v0 = 1 - (tileY + 1) / 8;
    const v1 = 1 - tileY / 8;
    uvs.push(u0, v0, u1, v0, u0, v1, u1, v1);
    indices.push(index * 4, index * 4 + 1, index * 4 + 2, index * 4 + 2, index * 4 + 1, index * 4 + 3);
  });
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3).setUsage(DynamicDrawUsage));
  geometry.setAttribute("uv", new Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  const texture = context ? new CanvasTexture(canvas) : null;
  if (texture) { texture.colorSpace = SRGBColorSpace; texture.anisotropy = 8; }
  return { geometry, texture };
}

function CasePart({ size, position, color, radius = 0.012, metalness = 0.25 }: {
  size: Point; position: Point; color: string; radius?: number; metalness?: number;
}) {
  const geometry = useMemo(() => new RoundedBoxGeometry(...size, 3, Math.min(radius, ...size.map((value) => value / 2))), [size[0], size[1], size[2], radius]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} position={position} castShadow receiveShadow>
    <meshStandardMaterial color={color} roughness={0.51} metalness={metalness} />
  </mesh>;
}

export function DeskKeyboard({ interactive, reducedMotion }: { interactive: boolean; reducedMotion: boolean }) {
  const invalidate = useThree((state) => state.invalidate);
  const keycapGeometry = useMemo(createKeycapGeometry, []);
  const legends = useMemo(createLegends, []);
  const keyMeshes = useRef<Array<InstancedMesh | null>>([]);
  const ridges = useRef<Array<Mesh | null>>([]);
  const scratch = useMemo(() => new Object3D(), []);
  const depression = useRef(new Float32Array(DESK_KEYS.length));
  const pressed = useRef(new Set<number>());
  const hovered = useRef<number | null>(null);
  const pointerPressed = useRef<number | null>(null);
  const dirty = useRef(true);
  const requestFrame = () => { dirty.current = true; invalidate(); };

  useEffect(() => () => { keycapGeometry.dispose(); legends.geometry.dispose(); legends.texture?.dispose(); }, [keycapGeometry, legends]);

  useEffect(() => {
    const clear = () => {
      pressed.current.clear(); hovered.current = null; pointerPressed.current = null;
      dirty.current = true; invalidate();
    };
    clear();
    if (!interactive) return;
    const keyDown = (event: KeyboardEvent) => {
      if (!keyboardMayReact(event, document.activeElement)) return;
      if (event.composedPath().some((target) => !keyboardMayReact({ target, defaultPrevented: false, isComposing: false }, null))) return;
      const index = CODE_INDEX.get(event.code);
      if (index === undefined || pressed.current.has(index)) return;
      pressed.current.add(index); dirty.current = true; invalidate();
    };
    const keyUp = (event: KeyboardEvent) => {
      const index = CODE_INDEX.get(event.code);
      if (index !== undefined && pressed.current.delete(index)) { dirty.current = true; invalidate(); }
    };
    const pointerUp = () => { pointerPressed.current = null; dirty.current = true; invalidate(); };
    window.addEventListener("keydown", keyDown);
    window.addEventListener("keyup", keyUp);
    window.addEventListener("blur", clear);
    window.addEventListener("pointerup", pointerUp);
    window.addEventListener("pointercancel", clear);
    document.addEventListener("focusin", clear);
    document.addEventListener("visibilitychange", clear);
    return () => {
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("keyup", keyUp);
      window.removeEventListener("blur", clear);
      window.removeEventListener("pointerup", pointerUp);
      window.removeEventListener("pointercancel", clear);
      document.removeEventListener("focusin", clear);
      document.removeEventListener("visibilitychange", clear);
      clear();
    };
  }, [interactive, invalidate]);

  useFrame((_, delta) => {
    if (!dirty.current) return;
    let moving = false;
    DESK_KEYS.forEach((_, index) => {
      const target = interactive && (pressed.current.has(index) || pointerPressed.current === index) ? -0.017
        : interactive && hovered.current === index ? -0.003 : 0;
      const next = reducedMotion ? target : depression.current[index] + (target - depression.current[index]) * (1 - Math.exp(-28 * Math.min(delta, 0.1)));
      const settling = Math.abs(next - target) >= 0.0001;
      depression.current[index] = settling ? next : target;
      moving ||= settling;
    });
    COLOR_KEYS.forEach(({ indices }, colorIndex) => {
      const mesh = keyMeshes.current[colorIndex];
      if (!mesh) return;
      indices.forEach((index, instance) => {
        scratch.position.set(...keyPosition(DESK_KEYS[index], depression.current[index]));
        scratch.scale.set(keyWidth(DESK_KEYS[index]) / BASE_WIDTH, 1, 1);
        scratch.updateMatrix();
        mesh.setMatrixAt(instance, scratch.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
    });
    const positions = legends.geometry.getAttribute("position");
    DESK_KEYS.forEach((key, index) => {
      for (let vertex = 0; vertex < 4; vertex += 1) positions.setY(index * 4 + vertex, ROW_Y[key.row] + CAP_HEIGHT + 0.0003 + depression.current[index]);
    });
    positions.needsUpdate = true;
    ["KeyF", "KeyJ"].forEach((code, index) => {
      const keyIndex = CODE_INDEX.get(code)!;
      const ridge = ridges.current[index];
      if (ridge) ridge.position.y = ROW_Y[DESK_KEYS[keyIndex].row] + CAP_HEIGHT + 0.0007 + depression.current[keyIndex];
    });
    dirty.current = moving;
    if (moving) invalidate();
  });

  const pointerKey = (event: ThreeEvent<PointerEvent>, colorIndex: number) => event.instanceId === undefined ? null : COLOR_KEYS[colorIndex].indices[event.instanceId] ?? null;

  return <group name="mechanical-desk-keyboard" position={[0, 1.65, 0.27]}>
    <CasePart size={[1.8, 0.065, 0.62]} position={[0, -0.008, 0]} color="#293334" radius={0.027} />
    <CasePart size={[1.782, 0.008, 0.601]} position={[0, 0.02, 0]} color="#69736d" radius={0.004} metalness={0.7} />
    <CasePart size={[1.79, 0.026, 0.61]} position={[0, 0.033, 0]} color="#374240" radius={0.012} />
    <CasePart size={[1.708, 0.006, 0.55]} position={[0, 0.045, -0.007]} color="#1e2827" radius={0.008} metalness={0} />
    {[-0.76, 0.76].flatMap((x) => [-0.235, 0.235].map((z) => <CasePart key={`${x}-${z}`} size={[0.15, 0.018, 0.08]} position={[x, -0.049, z]} color="#192220" radius={0.008} metalness={0} />))}
    {[-0.864, 0.864].flatMap((x) => [-0.277, 0.277].map((z) => <mesh key={`${x}-${z}`} position={[x, 0.047, z]}>
      <cylinderGeometry args={[0.007, 0.007, 0.002, 12]} />
      <meshStandardMaterial color="#99937e" metalness={0.8} roughness={0.42} />
    </mesh>))}

    {COLOR_KEYS.map(({ color, indices }, colorIndex) => <instancedMesh
      key={color}
      name={`keyboard-${color}-keycaps`}
      ref={(mesh) => { keyMeshes.current[colorIndex] = mesh; if (mesh) { mesh.instanceMatrix.setUsage(DynamicDrawUsage); dirty.current = true; } }}
      args={[keycapGeometry, undefined, indices.length]}
      frustumCulled={false}
      castShadow
      receiveShadow
      onPointerOver={interactive ? (event) => { event.stopPropagation(); hovered.current = pointerKey(event, colorIndex); requestFrame(); } : undefined}
      onPointerMove={interactive ? (event) => { const next = pointerKey(event, colorIndex); if (next !== hovered.current) { hovered.current = next; requestFrame(); } } : undefined}
      onPointerOut={interactive ? (event) => { if (hovered.current === pointerKey(event, colorIndex)) { hovered.current = null; requestFrame(); } } : undefined}
      onPointerDown={interactive ? (event) => { if (event.button !== 0) return; event.stopPropagation(); pointerPressed.current = pointerKey(event, colorIndex); requestFrame(); } : undefined}
    >
      <meshPhysicalMaterial color={KEY_COLORS[color]} roughness={0.52} metalness={0.015} clearcoat={.08} clearcoatRoughness={.6} />
    </instancedMesh>)}

    {legends.texture && <mesh name="keyboard-legends" geometry={legends.geometry} raycast={() => null}>
      <meshBasicMaterial map={legends.texture} transparent alphaTest={0.15} depthWrite={false} toneMapped={false} polygonOffset polygonOffsetFactor={-1} />
    </mesh>}
    {["KeyF", "KeyJ"].map((code, index) => {
      const key = DESK_KEYS[CODE_INDEX.get(code)!];
      const [x, y, z] = keyPosition(key);
      return <mesh key={code} ref={(mesh) => { ridges.current[index] = mesh; }} position={[x, y + CAP_HEIGHT + 0.0007, z + 0.021]} raycast={() => null}>
        <boxGeometry args={[0.018, 0.0015, 0.0025]} />
        <meshStandardMaterial color="#c0bdaf" roughness={0.7} />
      </mesh>;
    })}
    <CasePart size={[0.08, 0.024, 0.018]} position={[-0.54, -0.008, -0.308]} color="#18211f" radius={0.006} />
    <mesh position={[0.73, 0.048, -0.287]} rotation={[-Math.PI / 2, 0, 0]}>
      <circleGeometry args={[0.0035, 12]} />
      <meshBasicMaterial color="#abc4a0" toneMapped={false} />
    </mesh>
  </group>;
}

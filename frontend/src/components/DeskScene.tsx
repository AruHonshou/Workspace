import { Component, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  ACESFilmicToneMapping,
  type Texture,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { DESK_CAMERA_FOV, DESK_SCREEN, deskCameraFrame, type DeskPhase, type DeskPoint, type DeskLook } from "./deskSceneCamera";
import { DeskMonitor } from "./DeskMonitor";
import { DeskKeyboard } from "./DeskKeyboard";
import { DeskLamp, DeskNotebook, DeskCoffee, DeskMouse, DESK_ACCESSORY_ANCHORS } from "./DeskAccessories";
import { DeskPlant } from "./DeskPlants";
import { createDeskTexture, DeskContactShadows, DeskEnvironment } from "./DeskAtmosphere";
import { monitorCorners, projectDeskPoint, quadTransform } from "./deskProjection";
import { publicAsset } from "../app/publicAsset";

export type DeskSceneProps = {
  phase: DeskPhase;
  reducedMotion: boolean;
  locale: "es" | "en";
  onSettled: () => void;
  onUnavailable?: () => void;
  onReady?: () => void;
  screenElement?: RefObject<HTMLElement | null>;
  look?: RefObject<DeskLook>;
  requestFrame?: RefObject<(() => void) | null>;
  hotspots?: { linkedin: RefObject<HTMLAnchorElement | null>; github: RefObject<HTMLAnchorElement | null>; portfolio: RefObject<HTMLAnchorElement | null> };
};

const COLORS = {
  background: "#101f22",
  floor: "#16242b",
  charcoal: "#252d32",
  metal: "#4b5759",
  walnut: "#885c3f",
  walnutEdge: "#654332",
  ivory: "#e5e0d4",
};

type BoxProps = {
  size: DeskPoint;
  position?: DeskPoint;
  rotation?: DeskPoint;
  color: string;
  radius?: number;
  metalness?: number;
  roughness?: number;
  castShadow?: boolean;
  map?: Texture;
  bumpMap?: Texture;
  bumpScale?: number;
};

function SoftBox({ size, position, rotation, color, radius = 0.04, metalness = 0, roughness = 0.65, castShadow = true, map, bumpMap, bumpScale = .001 }: BoxProps) {
  const geometry = useMemo(() => new RoundedBoxGeometry(
    size[0], size[1], size[2], 3, Math.min(radius, ...size.map((value) => value / 2)),
  ), [size[0], size[1], size[2], radius]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh position={position} rotation={rotation} geometry={geometry} castShadow={castShadow} receiveShadow>
    <meshStandardMaterial color={color} roughness={roughness} metalness={metalness} map={map} bumpMap={bumpMap} bumpScale={bumpScale} />
  </mesh>;
}

function Desk({ interactive, reducedMotion }: { interactive: boolean; reducedMotion: boolean }) {
  const wood = useMemo(() => createDeskTexture("wood"), []);
  const grain = useMemo(() => createDeskTexture("grain"), []);
  useEffect(() => () => { wood.dispose(); grain.dispose(); }, [wood, grain]);
  return <group>
    <SoftBox size={[5.12, 0.16, 1.88]} position={[0, 1.51, -0.18]} color="#ffffff" map={wood} bumpMap={grain} bumpScale={.0012} radius={0.055} roughness={0.55} />
    <SoftBox size={[4.92, 0.028, 1.68]} position={[0, 1.414, -0.18]} color={COLORS.walnutEdge} radius={0.018} />
    {[-2.18, 2.18].map((x) => <group key={x}>
      <SoftBox size={[0.105, 1.36, 0.105]} position={[x, 0.73, -0.81]} color={COLORS.charcoal} radius={0.018} metalness={0.55} />
      <SoftBox size={[0.105, 1.36, 0.105]} position={[x, 0.73, 0.45]} color={COLORS.charcoal} radius={0.018} metalness={0.55} />
      <SoftBox size={[0.115, 0.1, 1.42]} position={[x, 0.1, -0.18]} color={COLORS.charcoal} radius={0.018} metalness={0.55} />
    </group>)}
    <SoftBox size={[4.4, 0.12, 0.06]} position={[0, 0.57, -0.82]} color={COLORS.charcoal} radius={0.014} />
    <SoftBox size={[2.72, 0.012, 0.82]} position={[0.22, 1.602, 0.27]} color="#354e44" radius={0.04} roughness={0.92} bumpMap={grain} bumpScale={.0015} />
    <DeskKeyboard interactive={interactive} reducedMotion={reducedMotion} />
    <DeskMouse />
    <DeskNotebook />
    <DeskCoffee />
  </group>;
}



function Studio() {
  return <group>
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[70, 70]} />
      <meshStandardMaterial color={COLORS.floor} roughness={0.93} />
    </mesh>
    <SoftBox size={[4.9, 0.026, 3.18]} position={[-0.1, 0.017, 0.58]} color="#243635" radius={0.012} castShadow={false} roughness={1} />
    <SoftBox size={[4.73, 0.006, 3.01]} position={[-0.1, 0.033, 0.58]} color="#293c39" radius={0.003} castShadow={false} roughness={1} />
    {/* Low furniture and a restrained gallery wall add depth without competing with the controls. */}
    <SoftBox size={[1.45, 1.15, 0.62]} position={[3.13, 0.63, -1.2]} color="#364441" radius={0.045} />
    <SoftBox size={[1.39, 0.055, 0.66]} position={[3.13, 1.24, -1.2]} color="#98714e" radius={0.025} />
    {[0.35, 0.78].map((y) => <group key={y}>
      <SoftBox size={[1.3, 0.025, 0.012]} position={[3.13, y, -0.881]} color="#1f2e2e" radius={0.005} castShadow={false} />
      <SoftBox size={[0.27, 0.023, 0.035]} position={[3.13, y + 0.12, -0.86]} color="#82918a" radius={0.01} metalness={0.7} />
    </group>)}
    <DeskPlant position={[2.75, 1.27, -1.24]} scale={1} />
    <SoftBox size={[0.27, 0.06, 0.36]} position={[2.67, 1.30, -1.08]} color="#b7b5a6" radius={0.01} />
    <SoftBox size={[0.28, 0.06, 0.34]} position={[2.65, 1.36, -1.08]} rotation={[0, 0.12, 0]} color="#7b8c81" radius={0.01} />
    <DeskPlant position={[2.01, 1.59, -0.82]} scale={0.62} variant="small" />
  </group>;
}

function Motion({ phase, reducedMotion, progress, onSettled, onReady, screenElement, look, requestFrame, hotspots }: DeskSceneProps & {
  progress: React.MutableRefObject<number>;
}) {
  const { camera, size, invalidate } = useThree();
  const completed = useRef<DeskPhase | null>(null);
  const settledCallback = useRef(onSettled);
  const currentLook = useRef<DeskLook>({ yaw: 0, pitch: 0 });
  settledCallback.current = onSettled;
  const applyFrame = (value: number) => {
    const frame = deskCameraFrame(value, size.width / Math.max(1, size.height), currentLook.current);
    camera.position.set(...frame.position);
    camera.lookAt(...frame.target);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    if (screenElement?.current) {
      const element = screenElement.current;
      const pixelWidth = size.width < 600 ? 420 : 1000;
      const pixelHeight = pixelWidth * DESK_SCREEN.height / DESK_SCREEN.width;
      const transform = quadTransform(monitorCorners(camera, size.width, size.height), pixelWidth, pixelHeight);
      if (transform) {
        element.style.width = `${pixelWidth}px`;
        element.style.height = `${pixelHeight}px`;
        element.style.transform = transform;
        element.dataset.compact = String(size.width < 600);
      }
    }
    for (const [element, point, halfWidth, halfHeight] of [
      [hotspots?.linkedin.current, [DESK_ACCESSORY_ANCHORS.coffee[0], 1.78, DESK_ACCESSORY_ANCHORS.coffee[2]], .22, .20],
      [hotspots?.github.current, [1.15, 1.70, .29], .14, .12],
      [hotspots?.portfolio.current, [-1.65, 1.69, .12], .28, .13],
    ] as const) {
      if (!element) continue;
      const center = projectDeskPoint([...point], camera, size.width, size.height);
      const left = projectDeskPoint([point[0] - halfWidth, point[1], point[2]], camera, size.width, size.height);
      const top = projectDeskPoint([point[0], point[1] + halfHeight, point[2]], camera, size.width, size.height);
      element.style.left = `${center.x}px`;
      element.style.top = `${center.y}px`;
      // Keep hover/focus labels inside the viewport while the user turns.
      element.style.setProperty("--tooltip-offset", `${Math.max(146 - center.x, Math.min(0, size.width - 146 - center.x))}px`);
      element.style.width = `${Math.max(44, Math.abs(center.x - left.x) * 2)}px`;
      element.style.height = `${Math.max(44, Math.abs(center.y - top.y) * 2)}px`;
      element.style.visibility = center.x < 20 || center.x > size.width - 20 || center.y < 20 || center.y > size.height - 70 ? "hidden" : "visible";
    }
  };
  useLayoutEffect(() => {
    completed.current = null;
    if (requestFrame) requestFrame.current = invalidate;
    if (phase === "home" || phase === "working" || reducedMotion) progress.current = phase === "home" || phase === "leaving" ? 0 : 1;
    if (phase === "working") currentLook.current = { yaw: 0, pitch: 0 };
    applyFrame(progress.current);
    onReady?.();
    invalidate();
    if (reducedMotion && (phase === "entering" || phase === "leaving")) {
      completed.current = phase;
      settledCallback.current();
    }
    return () => { if (requestFrame) requestFrame.current = null; };
    // DOM nodes and camera are stable; transforms also refresh on resize.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, reducedMotion, size.width, size.height, camera, invalidate, progress]);

  useFrame((_, delta) => {
    if (phase === "home") {
      const goal = look?.current ?? { yaw: 0, pitch: 0 };
      const ease = reducedMotion ? 1 : 1 - Math.exp(-Math.min(delta, .1) * 15);
      currentLook.current.yaw += (goal.yaw - currentLook.current.yaw) * ease;
      currentLook.current.pitch += (goal.pitch - currentLook.current.pitch) * ease;
      applyFrame(0);
      if (Math.abs(goal.yaw - currentLook.current.yaw) + Math.abs(goal.pitch - currentLook.current.pitch) > .0001) invalidate();
      return;
    }
    if (phase !== "entering" && phase !== "leaving") return;
    const direction = phase === "entering" ? 1 : -1;
    progress.current = Math.max(0, Math.min(1, progress.current + direction * Math.min(delta, .1) / 1.02));
    applyFrame(progress.current);
    if (((direction === 1 && progress.current === 1) || (direction === -1 && progress.current === 0)) && completed.current !== phase) {
      completed.current = phase;
      settledCallback.current();
    }
  }, -1);
  return null;
}

function ContextGuard({ onUnavailable }: { onUnavailable: () => void }) {
  const { gl } = useThree();
  useEffect(() => {
    const canvas = gl.domElement;
    const lost = (event: Event) => {
      event.preventDefault();
      onUnavailable();
    };
    canvas.addEventListener("webglcontextlost", lost);
    return () => canvas.removeEventListener("webglcontextlost", lost);
  }, [gl, onUnavailable]);
  return null;
}

class DeskBoundary extends Component<{ children: ReactNode; onUnavailable: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onUnavailable(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function canUseWebGL(): boolean {
  if (typeof window === "undefined" || typeof document === "undefined") return false;
  if (/jsdom/i.test(navigator.userAgent)) return false;
  return Boolean(window.WebGLRenderingContext || window.WebGL2RenderingContext);
}

export function DeskScene(props: DeskSceneProps) {
  const { phase, reducedMotion, locale, onSettled, onUnavailable } = props;
  const [available, setAvailable] = useState(canUseWebGL);
  const progress = useRef(phase === "working" ? 1 : 0);
  const notifiedUnavailable = useRef(false);
  const fallbackCompleted = useRef<DeskPhase | null>(null);
  const latestSettled = useRef(onSettled);
  const latestUnavailable = useRef(onUnavailable);
  latestSettled.current = onSettled;
  latestUnavailable.current = onUnavailable;
  useEffect(() => {
    if (available) return;
    if (!notifiedUnavailable.current) {
      notifiedUnavailable.current = true;
      latestUnavailable.current?.();
    }
    if (phase === "entering" || phase === "leaving") {
      if (fallbackCompleted.current !== phase) {
        fallbackCompleted.current = phase;
        latestSettled.current();
      }
    } else fallbackCompleted.current = null;
  }, [available, phase]);

  const description = locale === "es"
    ? "Vista en primera persona del escritorio, monitor ultrapanorámico, teclado y plantas"
    : "First-person workspace with an ultrawide monitor, keyboard and plants";
  return <section className={`desk-scene desk-scene--${phase}`} aria-label={description}>
    {!available ? <img className="desk-scene-fallback" src={publicAsset("branding/desk-fallback.svg")} alt={description} /> : <DeskBoundary onUnavailable={() => setAvailable(false)}>
      <Canvas
        className="desk-scene-canvas"
        camera={{ position: deskCameraFrame(phase === "working" ? 1 : 0, 1.7).position, fov: DESK_CAMERA_FOV, near: 0.025, far: 70 }}
        frameloop={phase === "entering" || phase === "leaving" ? "always" : "demand"}
        dpr={[1, 1.5]}
        shadows="variance"
        gl={{ antialias: true, alpha: false, powerPreference: "low-power", toneMapping: ACESFilmicToneMapping, toneMappingExposure: 1 }}
      >
        <color attach="background" args={[COLORS.background]} />
        <fog attach="fog" args={[COLORS.background, 16, 35]} />
        <ambientLight intensity={0.22} color="#b7ccca" />
        <hemisphereLight args={["#b8cfcd", "#20221b", 0.65]} />
        <directionalLight
          position={[-3.8, 6, 2.5]}
          color="#ffe1af"
          intensity={2.5}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-4.5}
          shadow-camera-right={4.5}
          shadow-camera-top={4}
          shadow-camera-bottom={-4}
          shadow-camera-near={.5}
          shadow-camera-far={16}
          shadow-normalBias={0.012}
          shadow-bias={-0.0001}
          shadow-radius={4}
          shadow-blurSamples={8}
        />
        <directionalLight position={[4, 4.8, -2]} color="#9bbdb0" intensity={1.15} />
        <pointLight position={[0, 2.6, -.62]} color="#b1d8cb" intensity={.25} distance={2.8} />
        <DeskEnvironment />
        <DeskContactShadows />
        <Studio />
        <Desk interactive={phase === "home"} reducedMotion={reducedMotion} />
        <DeskLamp />
        <DeskMonitor phase={phase} progress={progress} locale={locale} />
        <Motion {...props} progress={progress} />
        <ContextGuard onUnavailable={() => setAvailable(false)} />
      </Canvas>
    </DeskBoundary>}
  </section>;
}

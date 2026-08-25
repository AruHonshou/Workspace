import { Component, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  AnimationMixer,
  Box3,
  LoopRepeat,
  MathUtils,
  MOUSE,
  Object3D,
  Vector3,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

const MODEL_URL = "/models/ame-terrarium.glb";

class SceneBoundary extends Component<{ children: React.ReactNode; fallback: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function TerrariumModel({ reducedMotion }: { reducedMotion: boolean }) {
  const gltf = useLoader(GLTFLoader, MODEL_URL);
  const scene = useMemo(() => clone(gltf.scene) as Object3D, [gltf.scene]);
  const mixer = useMemo(() => new AnimationMixer(scene), [scene]);
  const transform = useMemo(() => {
    const box = new Box3().setFromObject(scene);
    const center = box.getCenter(new Vector3());
    const size = box.getSize(new Vector3());
    const scale = 4.8 / Math.max(size.x, size.y, size.z, 0.001);
    return { position: center.multiplyScalar(-scale), scale };
  }, [scene]);

  useEffect(() => {
    const clip = gltf.animations[0];
    if (!clip || reducedMotion) return undefined;
    const action = mixer.clipAction(clip);
    action.setLoop(LoopRepeat, Infinity).play();
    return () => {
      action.stop();
      mixer.stopAllAction();
    };
  }, [gltf.animations, mixer, reducedMotion]);

  useFrame((_, delta) => {
    if (!reducedMotion) mixer.update(Math.min(delta, 0.05));
  });

  return (
    <group scale={transform.scale} position={transform.position}>
      <primitive object={scene} />
    </group>
  );
}

function CameraControls({ resetToken }: { resetToken: number }) {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControls | null>(null);
  const initialPosition = useMemo(() => new Vector3(0, 0.25, 7.4), []);

  useEffect(() => {
    const instance = new OrbitControls(camera, gl.domElement);
    instance.enableDamping = true;
    instance.dampingFactor = 0.075;
    instance.enablePan = true;
    instance.screenSpacePanning = true;
    instance.minDistance = 3.2;
    instance.maxDistance = 11;
    instance.minPolarAngle = MathUtils.degToRad(25);
    instance.maxPolarAngle = MathUtils.degToRad(150);
    instance.mouseButtons.LEFT = MOUSE.ROTATE;
    instance.mouseButtons.RIGHT = MOUSE.PAN;
    instance.target.set(0, 0, 0);
    controls.current = instance;
    const constrain = () => {
      instance.target.x = MathUtils.clamp(instance.target.x, -1.25, 1.25);
      instance.target.y = MathUtils.clamp(instance.target.y, -0.9, 1.2);
      instance.target.z = MathUtils.clamp(instance.target.z, -0.75, 0.75);
    };
    instance.addEventListener("change", constrain);
    return () => {
      instance.removeEventListener("change", constrain);
      instance.dispose();
    };
  }, [camera, gl, initialPosition]);

  useEffect(() => {
    camera.position.copy(initialPosition);
    controls.current?.target.set(0, 0, 0);
    controls.current?.update();
  }, [camera, initialPosition, resetToken]);

  useFrame(() => controls.current?.update());
  return null;
}

function StaticFallback({ locale }: { locale: "es" | "en" }) {
  const label = locale === "es" ? "Ame en su terrario retro" : "Ame in her retro terrarium";
  return (
    <div className="terrarium-fallback" role="img" aria-label={label}>
      <img src="/models/ame-terrarium-poster.svg" alt="" />
    </div>
  );
}

export function OrchestratorScene({ reducedMotion, locale }: { reducedMotion: boolean; locale: "es" | "en" }) {
  const [resetToken, setResetToken] = useState(0);
  const [webgl] = useState(() => {
    try {
      if (navigator.userAgent.toLowerCase().includes("jsdom")) return false;
      const canvas = document.createElement("canvas");
      return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
    } catch {
      return false;
    }
  });

  if (!webgl) return <StaticFallback locale={locale} />;

  return (
    <section className="orchestrator-world" aria-label={locale === "es" ? "Escena 3D de Ame, la orquestadora" : "3D scene of Ame, the orchestrator"}>
      <SceneBoundary fallback={<StaticFallback locale={locale} />}>
        <Canvas
          className="terrarium-canvas"
          camera={{ position: [0, 0.25, 7.4], fov: 34, near: 0.1, far: 100 }}
          dpr={[1, 1.7]}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        >
          <ambientLight intensity={2.2} />
          <hemisphereLight args={["#fff8dc", "#214f56", 1.6]} />
          <directionalLight position={[4, 7, 6]} intensity={2.3} color="#fff3cf" />
          <directionalLight position={[-4, 2, 2]} intensity={1.1} color="#8fe5df" />
          <Suspense fallback={null}>
            <TerrariumModel reducedMotion={reducedMotion} />
          </Suspense>
          <CameraControls resetToken={resetToken} />
        </Canvas>
      </SceneBoundary>
      <button
        type="button"
        className="camera-reset"
        onClick={() => setResetToken((value) => value + 1)}
        title={locale === "es" ? "Restablecer cámara" : "Reset camera"}
        aria-label={locale === "es" ? "Restablecer cámara 3D" : "Reset 3D camera"}
      >
        <span aria-hidden="true">↺</span>
        <span>{locale === "es" ? "Vista inicial" : "Initial view"}</span>
      </button>
      <div className="scene-help" aria-hidden="true">{locale === "es" ? "Arrastra para explorar · Rueda para acercar" : "Drag to explore · Wheel to zoom"}</div>
    </section>
  );
}

useLoader.preload(GLTFLoader, MODEL_URL);

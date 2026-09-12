import { useEffect, useLayoutEffect, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import { DataTexture, EquirectangularReflectionMapping, LinearFilter, PMREMGenerator, RepeatWrapping, RGBAFormat, SRGBColorSpace, UnsignedByteType } from "three";

/** Small, deterministic maps authored in code. No downloaded images or shaders. */
export function createDeskTexture(kind: "wood" | "grain" | "contact") {
  const width = kind === "wood" ? 512 : 128, height = kind === "wood" ? 256 : 128;
  const pixels = new Uint8Array(width * height * 4);
  let seed = 93217;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const noise = seed / 4294967296, offset = (y * width + x) * 4;
    if (kind === "contact") {
      const distance = Math.hypot((x + .5) / width * 2 - 1, (y + .5) / height * 2 - 1);
      pixels.set([255, 255, 255, Math.round(Math.max(0, 1 - distance) ** 1.8 * 210)], offset);
    } else if (kind === "wood") {
      const u = x / width, v = y / height;
      const wave = v * 130 + Math.sin(u * 5.5 + v * 13) * 1.8 + Math.sin(u * 14 + v * 3) * .45;
      const grain = Math.sin(wave * Math.PI) * .016 + Math.sin(wave * Math.PI * 3) * .008;
      const figure = Math.sin(v * 24 + Math.sin(u * 4) * 1.2) * .07;
      const shade = 1 + grain + figure + (noise - .5) * .05;
      pixels.set([Math.round(125 * shade), Math.round(83 * shade), Math.round(51 * shade), 255], offset);
    } else {
      const grain = 150 + Math.round((noise - .5) * 32) + (x % 2 === y % 2 ? 5 : -5);
      pixels.set([grain, grain, grain, 255], offset);
    }
  }
  const texture = new DataTexture(pixels, width, height, RGBAFormat, UnsignedByteType);
  texture.minFilter = texture.magFilter = LinearFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  if (kind === "wood") { texture.colorSpace = SRGBColorSpace; texture.anisotropy = 4; }
  if (kind === "grain") { texture.wrapS = texture.wrapT = RepeatWrapping; texture.repeat.set(8, 5); }
  return texture;
}

/** Reflection-only studio: broad softboxes, not a visible HDR background.
 * PMREM is computed once, reused on demand, and released on unmount. */
export function DeskEnvironment() {
  const { gl, scene, invalidate } = useThree();
  useLayoutEffect(() => {
    const width = 256, height = 128, pixels = new Uint8Array(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const u = x / width, v = y / height;
      const softbox = Math.exp(-(((u - .22) / .095) ** 4) - ((v - .30) / .12) ** 4);
      const rim = Math.exp(-(((u - .73) / .06) ** 4) - ((v - .4) / .17) ** 4);
      const ceiling = Math.max(0, 1 - v) * 25;
      pixels.set([22 + ceiling + softbox * 200 + rim * 90, 30 + ceiling + softbox * 174 + rim * 118,
        31 + ceiling + softbox * 141 + rim * 115, 255].map(Math.round), (y * width + x) * 4);
    }
    const source = new DataTexture(pixels, width, height, RGBAFormat);
    source.mapping = EquirectangularReflectionMapping;
    source.colorSpace = SRGBColorSpace;
    source.needsUpdate = true;
    const generator = new PMREMGenerator(gl);
    const environment = generator.fromEquirectangular(source);
    const previous = scene.environment, previousIntensity = scene.environmentIntensity;
    scene.environment = environment.texture;
    scene.environmentIntensity = .55;
    source.dispose(); generator.dispose(); invalidate();
    return () => {
      if (scene.environment === environment.texture) { scene.environment = previous; scene.environmentIntensity = previousIntensity; }
      environment.dispose();
    };
  }, [gl, scene, invalidate]);
  return null;
}

/** Bake-like contact occlusion, independent of camera, interaction and time. */
export function DeskContactShadows() {
  const map = useMemo(() => createDeskTexture("contact"), []);
  useEffect(() => () => map.dispose(), [map]);
  const contacts = [
    { at: [0, 1.611, .27], size: [2.04, .83], opacity: .48 },
    { at: [1.15, 1.612, .29], size: [.37, .49], opacity: .42 },
    { at: [-1.65, 1.593, .12], size: [.83, 1.04], opacity: .52 },
    { at: [1.83, 1.593, .12], size: [.55, .55], opacity: .5 },
    { at: [0, 1.593, -.805], size: [1.26, .82], opacity: .52 },
    { at: [-2.17, 1.593, -.22], size: [.65, .61], opacity: .48 },
    { at: [2.01, 1.593, -.82], size: [.48, .48], opacity: .46 },
    { at: [2.75, 1.271, -1.24], size: [.7, .7], opacity: .46 },
  ];
  return <group name="desk-contact-occlusion">{contacts.map(({ at, size, opacity }, i) => <mesh key={i}
    position={at as [number, number, number]} rotation={[-Math.PI / 2, 0, i === 2 ? .14 : 0]} raycast={() => null}>
    <planeGeometry args={size as [number, number]} />
    <meshBasicMaterial map={map} color="#15211a" transparent opacity={opacity} depthWrite={false} toneMapped={false} />
  </mesh>)}</group>;
}

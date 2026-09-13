import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("offline asset boundary", () => {
  it("does not load remote resources from the shipped HTML or CSS", () => {
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
    expect(html).not.toMatch(/\b(?:src|href)\s*=\s*["']https?:\/\//i);
    const sourceRoot = resolve(process.cwd(), "src");
    for (const file of readdirSync(sourceRoot, { recursive: true }).map(String).filter(file => file.endsWith(".css"))) {
      const css = readFileSync(resolve(sourceRoot, file), "utf8");
      expect(css, file).not.toMatch(/@import\s+(?:url\()?\s*["']?https?:\/\//i);
      expect(css, file).not.toMatch(/url\(\s*["']?https?:\/\//i);
    }
  });

  it("ships only documented artwork and no external models or soundtrack", () => {
    const publicRoot = resolve(process.cwd(), "public");
    const files = readdirSync(publicRoot, { recursive: true }).map(String);
    expect(files.filter((file) => /\.(?:glb|gltf|mp3|wav|ogg|m4a|flac)$/i.test(file))).toEqual([]);
    expect(files.filter((file) => /\.(?:svg|png|jpe?g|webp|gif)$/i.test(file))
      .map((file) => file.replaceAll("\\", "/")).sort()).toEqual([
      "branding/desk-fallback.svg", "branding/workspace-mark.svg",
    ]);
  });

  it("uses a local neutral SVG favicon and an offline scene fallback", () => {
    for (const name of ["workspace-mark.svg", "desk-fallback.svg"]) {
      const svg = readFileSync(resolve(process.cwd(), "public/branding", name), "utf8");
      const document = new DOMParser().parseFromString(svg, "image/svg+xml");
      expect(document.querySelector("parsererror")).toBeNull();
      expect(document.documentElement.localName).toBe("svg");
      expect(document.documentElement.hasAttribute("viewBox")).toBe(true);
      expect(document.querySelector("script, foreignObject, image, audio, video")).toBeNull();
      expect(svg).not.toMatch(/(?:href|src)\s*=\s*["'][^#"'\s]|url\(\s*["']?[^#"')\s]/i);
    }
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
    expect(html).toContain('href="/branding/workspace-mark.svg"');
    expect(html).toContain("<title>Workspace · Espacio profesional</title>");
  });

  it("does not request external models or start audio from runtime source", () => {
    const sourceRoot = resolve(process.cwd(), "src");
    const files = readdirSync(sourceRoot, { recursive: true }).map(String)
      .filter((file) => /\.tsx?$/.test(file) && !/\.test\.tsx?$/.test(file));
    for (const file of files) {
      const source = readFileSync(resolve(sourceRoot, file), "utf8");
      expect(source, file).not.toMatch(/GLTFLoader|["']\/models\/|<audio\b|new\s+Audio\s*\(/i);
    }
  });
});

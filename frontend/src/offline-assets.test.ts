import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("offline asset boundary", () => {
  it("does not load remote resources from the shipped HTML or CSS", () => {
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
    const css = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

    expect(html).not.toMatch(/\b(?:src|href)\s*=\s*["']https?:\/\//i);
    expect(css).not.toMatch(/@import\s+(?:url\()?\s*["']?https?:\/\//i);
    expect(css).not.toMatch(/url\(\s*["']?https?:\/\//i);
  });

  it("ships only the embedded Ame terrarium GLB", () => {
    const path = resolve(process.cwd(), "public", "models", "ame-terrarium.glb");
    expect(statSync(path).size).toBeGreaterThan(1_000_000);
    expect(readFileSync(path).subarray(0, 4).toString("ascii")).toBe("glTF");
    const source = readFileSync(resolve(process.cwd(), "src/components/OrchestratorScene.tsx"), "utf8");
    expect(source).not.toMatch(/(?:gura|ina|kiara|calli)\.glb/i);
    expect(source).not.toMatch(/animation_cue|speech/i);
  });
});

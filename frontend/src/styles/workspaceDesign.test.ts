import { readFileSync } from "node:fs";
import { URL } from "node:url";
import { describe, expect, it } from "vitest";

function readCss(filename: string): string {
  return readFileSync(new URL(filename, import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
}

const tokenCss = readCss("./workspaceTokens.css");
const productCss = readCss("./product.css");
const declarations = [...tokenCss.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)].map((match) => [match[1], match[2].trim()] as const);
const tokens = Object.fromEntries(declarations);

function luminance(hex: string): number {
  expect(hex).toMatch(/^#[0-9a-f]{6}$/i);
  const channels = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((channel) => channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4);
  return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
}

function contrast(foreground: string, background: string): number {
  const values = [luminance(foreground), luminance(background)];
  return (Math.max(...values) + .05) / (Math.min(...values) + .05);
}

describe("calm workspace visual contract", () => {
  it("keeps the requested sage, cream and forest palette", () => {
    expect(tokens).toMatchObject({
      "--bg-app": "#EDF3EF", "--surface": "#F8F7F0", "--surface-secondary": "#E5EFE9", "--surface-hover": "#D7E6DE",
      "--border": "#CBD9D2", "--border-strong": "#ADC4B8", "--text-primary": "#173A34", "--text-secondary": "#586F65", "--text-muted": "#81928C",
      "--primary": "#0D6258", "--primary-hover": "#084E47", "--primary-active": "#063E38", "--primary-soft": "#D8EBE4", "--primary-soft-hover": "#C9E0D5",
      "--focus": "#7CCABD", "--accent": "#C49A58", "--accent-soft": "#F0E2C9",
      "--success": "#32866D", "--success-soft": "#DDEEE6", "--warning": "#C08A39", "--warning-soft": "#F3E6CD",
      "--danger": "#BE5966", "--danger-soft": "#F4DEE1", "--info": "#4C80A3", "--info-soft": "#DFEAF1",
    });
  });

  it("declares tokens once at root and resolves every compatibility reference", () => {
    expect(tokenCss.match(/:root\s*\{/g)).toHaveLength(1);
    expect(declarations.length).toBeGreaterThan(40);
    expect(new Set(declarations.map(([name]) => name)).size).toBe(declarations.length);
    for (const [name, value] of declarations) {
      expect(value, name).not.toBe("");
      for (const reference of value.matchAll(/var\((--[\w-]+)\)/g)) {
        expect(tokens, `${name} refers to ${reference[1]}`).toHaveProperty(reference[1]);
      }
    }
  });

  it("provides readable text for the intended content and app surface pairings", () => {
    const pairings = [
      ["--text-primary", "--surface"], ["--text-primary", "--bg-app"],
      ["--text-secondary", "--surface"], ["--text-secondary", "--surface-secondary"],
      ["--text-on-canvas", "--bg-app"],
    ];
    for (const [foreground, background] of pairings) {
      expect(contrast(tokens[foreground], tokens[background]), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the primary action label readable in normal, hover and active states", () => {
    expect(tokens["--ui-on-accent"]).toBe("#F8FAF7");
    for (const background of ["--primary", "--primary-hover", "--primary-active"]) {
      expect(contrast(tokens["--ui-on-accent"], tokens[background]), background).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("uses darker status text with sufficient contrast on each soft status surface", () => {
    for (const status of ["success", "warning", "danger", "info"]) {
      const foreground = tokens[`--${status}-text`];
      expect(luminance(foreground), status).toBeLessThan(luminance(tokens[`--${status}`]));
      expect(contrast(foreground, tokens[`--${status}-soft`]), status).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("does not reintroduce a separate dark workspace palette", () => {
    expect(productCss).not.toMatch(/\[\s*data-workspace-theme\s*=\s*["']?dark\b/i);
  });

  it("keeps keyboard focus from scrolling the outer desktop shell", () => {
    expect(productCss).toMatch(/\.desktop-shell\.phase-working\s*\{\s*overflow:\s*clip\s*;/);
    expect(productCss).toMatch(/\.browser-workspace\s*\{[^}]*overflow:\s*clip\s*;/);
  });

  it("bundles all three licensed fonts locally without runtime network dependencies", () => {
    for (const [font, license] of [["inter-latin.woff2", "OFL-Inter.txt"], ["manrope-latin.woff2", "OFL-Manrope.txt"], ["caveat-latin.woff2", "OFL-Caveat.txt"]]) {
      const assetPath = `../../public/fonts/${font}`;
      const licensePath = `../../public/fonts/${license}`;
      expect(readFileSync(new URL(assetPath, import.meta.url)).subarray(0, 4).toString()).toBe("wOF2");
      expect(readFileSync(new URL(licensePath, import.meta.url), "utf8")).toContain("SIL OPEN FONT LICENSE");
      expect(tokenCss).toContain(`/fonts/${font}`);
    }
    expect(tokenCss).not.toMatch(/url\(["']?https?:/);
  });

  it("disables portal motion when reduced motion is requested", () => {
    const reducedMotion = productCss.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*)/);
    expect(reducedMotion).not.toBeNull();
    const rules = [...reducedMotion![1].matchAll(/([^{}]+)\{([^{}]+)\}/g)];
    for (const portal of [".filter-menu", ".country-options"]) {
      const rule = rules.find(([, selectors, body]) => selectors.split(",").some((selector) => selector.trim() === portal)
        && /animation:\s*none\s*!important/.test(body) && /transition:\s*none\s*!important/.test(body));
      expect(rule, `${portal} reduced motion rule`).toBeDefined();
    }
  });
});

import { describe, expect, it } from "vitest";
import { createDeskTexture } from "./DeskAtmosphere";
import { createPlantLeaf } from "./DeskPlants";
import { DESK_ACCESSORY_ANCHORS } from "./DeskAccessories";

describe("lightweight authored desk surfaces", () => {
  it.each(["wood", "grain", "contact"] as const)("creates a deterministic, bounded %s texture", (kind) => {
    const first = createDeskTexture(kind), second = createDeskTexture(kind);
    expect(first.image.data).toEqual(second.image.data);
    expect(first.image.data.byteLength).toBeLessThanOrEqual(512 * 256 * 4);
    if (kind === "contact") {
      const pixels = first.image.data as Uint8Array;
      expect(pixels[3]).toBe(0);
      const center = (64 * 128 + 64) * 4 + 3;
      expect(pixels[center]).toBeGreaterThan(190);
    }
    first.dispose(); second.dispose();
  });

  it.each([true, false])("creates finite curved plant blades (broad=%s)", (broad) => {
    const leaf = createPlantLeaf(broad);
    expect(leaf.getAttribute("position").count).toBeLessThan(400);
    expect(leaf.index!.count / 3).toBeLessThan(700);
    for (const key of ["position", "normal"]) {
      expect(Array.from(leaf.getAttribute(key).array).every(Number.isFinite)).toBe(true);
    }
    expect(leaf.boundingSphere!.radius).toBeGreaterThan(.5);
    leaf.dispose();
  });

  it("keeps the entire coffee coaster outside the desk mat and on the desk", () => {
    const coasterRadius = .2, matRight = .22 + 2.72 / 2, deskRight = 5.12 / 2;
    expect(DESK_ACCESSORY_ANCHORS.coffee[0] - coasterRadius).toBeGreaterThan(matRight);
    expect(DESK_ACCESSORY_ANCHORS.coffee[0] + .23).toBeLessThan(deskRight);
  });
});

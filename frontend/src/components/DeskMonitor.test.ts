import { describe, expect, it } from "vitest";
import { MONITOR_GEOMETRY, monitorCurveOffset, monitorPower } from "./DeskMonitor";
import { DESK_SCREEN } from "./deskSceneCamera";

describe("curved ultrawide desktop monitor", () => {
  it("shares the screen center and shallow curve with the projected hero", () => {
    expect(monitorCurveOffset(0)).toBeCloseTo(0, 8);
    expect(monitorCurveOffset(DESK_SCREEN.width / 2)).toBeCloseTo(DESK_SCREEN.curvatureDepth, 8);
    expect(monitorCurveOffset(-DESK_SCREEN.width / 2)).toBeCloseTo(DESK_SCREEN.curvatureDepth, 8);
    expect(monitorCurveOffset(DESK_SCREEN.width / 4)).toBeGreaterThan(0);
    expect(monitorCurveOffset(DESK_SCREEN.width / 4)).toBeLessThan(DESK_SCREEN.curvatureDepth);
  });

  it("keeps the rear stand behind the deepest point of the display", () => {
    const { chassis, column, mount, displayZ } = MONITOR_GEOMETRY;
    const chassisBack = chassis.position[2] - chassis.size[2] / 2;
    expect(column.position[2] + column.size[2] / 2).toBeLessThan(chassisBack);
    expect(mount.position[2] + mount.size[2] / 2).toBeLessThan(displayZ);
    expect(chassis.position[2] + chassis.size[2] / 2).toBeLessThan(displayZ);
  });

  it("connects the rear enclosure to its stand and base", () => {
    const { chassis, mount, column, base } = MONITOR_GEOMETRY;
    const overlaps = (a: { position: readonly number[]; size: readonly number[] }, b: { position: readonly number[]; size: readonly number[] }, axis: number) => (
      a.position[axis] - a.size[axis] / 2 <= b.position[axis] + b.size[axis] / 2
      && a.position[axis] + a.size[axis] / 2 >= b.position[axis] - b.size[axis] / 2
    );
    for (const axis of [0, 1, 2]) {
      expect(overlaps(chassis, mount, axis)).toBe(true);
      expect(overlaps(mount, column, axis)).toBe(true);
      expect(overlaps(column, base, axis)).toBe(true);
    }
  });

  it("rests the slim base on the desk below the display", () => {
    const { base, deskSurface } = MONITOR_GEOMETRY;
    expect(base.position[1] - base.size[1] / 2).toBeCloseTo(deskSurface, 8);
    expect(base.position[1] + base.size[1] / 2).toBeLessThan(DESK_SCREEN.center[1] - DESK_SCREEN.height / 2);
    expect(base.position[2] - base.size[2] / 2).toBeGreaterThan(-1.12);
  });

  it("matches the DOM hero background without reflecting a light hotspot", () => {
    expect(MONITOR_GEOMETRY.offSurface.color).toBe("#101c23");
    expect(MONITOR_GEOMETRY.offSurface.material).toBe("MeshBasicMaterial");
    expect(MONITOR_GEOMETRY.offSurface.toneMapped).toBe(false);
    expect(monitorPower("home", 1)).toBe(0);
    expect(monitorPower("leaving", 0)).toBe(0);
  });

  it("preserves the transition into the browser and sanitizes invalid progress", () => {
    expect(monitorPower("working", 0)).toBe(1);
    expect(monitorPower("entering", 0)).toBe(0);
    expect(monitorPower("entering", 1)).toBe(1);
    expect(monitorPower("entering", -1)).toBe(0);
    expect(monitorPower("leaving", 2)).toBe(1);
    expect(monitorPower("entering", Number.NaN)).toBe(0);
    expect(monitorPower("leaving", 0.5)).toBeLessThan(monitorPower("entering", 0.5));
  });
});

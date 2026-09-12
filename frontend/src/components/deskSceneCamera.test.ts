import { describe, expect, it } from "vitest";
import { DESK_CAMERA_FOV, DESK_LOOK_LIMIT, DESK_SCREEN, clampDeskLook, deskCameraFrame, deskEase, type DeskPoint } from "./deskSceneCamera";

const distance = (a: DeskPoint, b: DeskPoint) => Math.hypot(...a.map((value, axis) => value - b[axis]));

describe("seated desktop camera", () => {
  it("clamps progress and settles at exact endpoints", () => {
    expect(deskEase(-1)).toBe(0);
    expect(deskEase(2)).toBe(1);
    expect(deskCameraFrame(-1, 1.8)).toEqual(deskCameraFrame(0, 1.8));
    expect(deskCameraFrame(2, 1.8)).toEqual(deskCameraFrame(1, 1.8));
  });

  it.each([0.4, 0.7, 1, 1.7, 2.5, 3.5])("covers the viewport with the monitor at aspect %s", (aspect) => {
    const frame = deskCameraFrame(1, aspect);
    expect(frame.target).toEqual(DESK_SCREEN.center);
    expect(frame.position[0]).toBe(DESK_SCREEN.center[0]);
    expect(frame.position[1]).toBe(DESK_SCREEN.center[1]);
    const distance = frame.position[2] - DESK_SCREEN.center[2];
    const visibleHeight = 2 * distance * Math.tan(DESK_CAMERA_FOV * Math.PI / 360);
    expect(visibleHeight).toBeLessThan(DESK_SCREEN.height);
    expect(visibleHeight * aspect).toBeLessThan(DESK_SCREEN.width);
    expect(distance).toBeGreaterThan(0.2);
  });

  it("remains finite and above the desk along the complete reversible path", () => {
    for (let step = 0; step <= 100; step += 1) {
      const frame = deskCameraFrame(step / 100, 1.7);
      expect(frame.position.every(Number.isFinite)).toBe(true);
      expect(frame.position[1]).toBeGreaterThan(2.5);
      expect(frame.position[2]).toBeGreaterThan(DESK_SCREEN.center[2]);
    }
  });

  it("limits horizontal and vertical looking independently", () => {
    expect(clampDeskLook({ yaw: 100, pitch: -100 })).toEqual({ yaw: DESK_LOOK_LIMIT.yaw, pitch: -DESK_LOOK_LIMIT.pitch });
    expect(clampDeskLook({ yaw: -100, pitch: 100 })).toEqual({ yaw: -DESK_LOOK_LIMIT.yaw, pitch: DESK_LOOK_LIMIT.pitch });
    expect(clampDeskLook({ yaw: .07, pitch: -.03 })).toEqual({ yaw: .07, pitch: -.03 });
    expect(clampDeskLook({ yaw: Number.NaN, pitch: Number.POSITIVE_INFINITY })).toEqual({ yaw: 0, pitch: 0 });
    expect(deskCameraFrame(0, 1.7, { yaw: 100, pitch: -100 })).toEqual(
      deskCameraFrame(0, 1.7, { yaw: DESK_LOOK_LIMIT.yaw, pitch: -DESK_LOOK_LIMIT.pitch }),
    );
  });

  it.each([0, .25, .65, 1])("rotates the gaze without translating the seated camera at progress %s", (progress) => {
    const resting = deskCameraFrame(progress, 1.7);
    for (const yaw of [-DESK_LOOK_LIMIT.yaw, DESK_LOOK_LIMIT.yaw]) {
      for (const pitch of [-DESK_LOOK_LIMIT.pitch, DESK_LOOK_LIMIT.pitch]) {
        const looking = deskCameraFrame(progress, 1.7, { yaw, pitch });
        expect(looking.position).toEqual(resting.position);
        expect(distance(looking.position, looking.target)).toBeCloseTo(distance(resting.position, resting.target), 10);
        if (progress < 1) expect(looking.target).not.toEqual(resting.target);
        else expect(looking.target).toEqual(DESK_SCREEN.center);
      }
    }
  });

  it("turns the home gaze by the requested yaw and pitch", () => {
    const angles = (look: { yaw: number; pitch: number }) => {
      const { position, target } = deskCameraFrame(0, 1.7, look);
      const [x, y, z] = target.map((value, axis) => value - position[axis]);
      return { yaw: Math.atan2(x, -z), pitch: Math.atan2(y, Math.hypot(x, z)) };
    };
    const baseline = angles({ yaw: 0, pitch: 0 });
    const looking = angles({ yaw: .2, pitch: .1 });
    expect(looking.yaw - baseline.yaw).toBeCloseTo(.2, 10);
    expect(looking.pitch - baseline.pitch).toBeCloseTo(.1, 10);
  });

  it.each([.4, 1.7, 3.5])("smoothly converges onto the display from a turned gaze at aspect %s", (aspect) => {
    const look = { yaw: DESK_LOOK_LIMIT.yaw, pitch: -DESK_LOOK_LIMIT.pitch };
    const endpoint = deskCameraFrame(1, aspect, look);
    const near = deskCameraFrame(.98, aspect, look);
    const nearer = deskCameraFrame(.99, aspect, look);
    expect(endpoint).toEqual(deskCameraFrame(1, aspect));
    expect(endpoint.target).toEqual(DESK_SCREEN.center);
    // Halving the remaining time shrinks the remaining travel by about four,
    // so both translation and gaze ease into the HTML handoff without a snap.
    expect(distance(nearer.position, endpoint.position)).toBeLessThan(distance(near.position, endpoint.position) * .3);
    expect(distance(nearer.target, endpoint.target)).toBeLessThan(distance(near.target, endpoint.target) * .3);
  });

  it("sanitizes invalid input before producing position and gaze coordinates", () => {
    for (const progress of [-100, 0, .5, 1, 100, Number.NaN, Number.NEGATIVE_INFINITY]) {
      for (const aspect of [-1, 0, .1, 10, Number.NaN, Number.POSITIVE_INFINITY]) {
        const frame = deskCameraFrame(progress, aspect, { yaw: Number.NaN, pitch: Number.NEGATIVE_INFINITY });
        expect([...frame.position, ...frame.target].every(Number.isFinite)).toBe(true);
        expect(frame.position[2]).toBeGreaterThan(DESK_SCREEN.center[2]);
      }
    }
  });
});

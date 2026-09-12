import { Box3, PerspectiveCamera, Ray, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { MONITOR_GEOMETRY, monitorCurveOffset } from "./DeskMonitor";
import { DESK_CAMERA_FOV, DESK_LOOK_LIMIT, DESK_SCREEN, deskCameraFrame, type DeskLook } from "./deskSceneCamera";
import { monitorCorners, projectDeskPoint, quadTransform } from "./deskProjection";

const viewports = [
  [1920, 1080],
  [1440, 900],
  [2560, 1080],
  [3440, 1440],
] as const;

function cameraAt(width: number, height: number, progress = 0, look: DeskLook = { yaw: 0, pitch: 0 }) {
  const camera = new PerspectiveCamera(DESK_CAMERA_FOV, width / height, .025, 70);
  const frame = deskCameraFrame(progress, width / height, look);
  camera.position.set(...frame.position);
  camera.lookAt(...frame.target);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  return camera;
}

describe("visual refinements preserve the existing seated display contracts", () => {
  it.each(viewports)("keeps the complete home display on screen at %s × %s", (width, height) => {
    const corners = monitorCorners(cameraAt(width, height), width, height);
    for (const point of corners) {
      expect(point.x).toBeGreaterThan(0);
      expect(point.x).toBeLessThan(width);
      expect(point.y).toBeGreaterThan(0);
      expect(point.y).toBeLessThan(height);
    }
    // The monitor remains centered and readable, without prescribing its materials.
    expect((corners[0].x + corners[1].x) / 2).toBeCloseTo(width / 2, 6);
    expect(corners[2].y - corners[1].y).toBeGreaterThan(height * .35);
    expect(quadTransform(corners, 1000, 1000 * DESK_SCREEN.height / DESK_SCREEN.width)).not.toBeNull();
  });

  it.each(viewports)("keeps the support behind the visible screen at %s × %s", (width, height) => {
    const bounds = [MONITOR_GEOMETRY.column, MONITOR_GEOMETRY.mount, MONITOR_GEOMETRY.base]
      .map(part => new Box3().setFromCenterAndSize(new Vector3(...part.position), new Vector3(...part.size)));
    for (const progress of [0, .5, 1]) {
      for (const side of [-1, 0, 1]) {
        const camera = cameraAt(width, height, progress, {
          yaw: side * DESK_LOOK_LIMIT.yaw,
          pitch: side * DESK_LOOK_LIMIT.pitch,
        });
        for (const horizontal of [-.45, 0, .45]) {
          for (const vertical of [-.45, 0, .45]) {
            const x = DESK_SCREEN.width * horizontal;
            const displayPoint = new Vector3(
              DESK_SCREEN.center[0] + x,
              DESK_SCREEN.center[1] + DESK_SCREEN.height * vertical,
              MONITOR_GEOMETRY.displayZ + monitorCurveOffset(x),
            );
            const distanceToScreen = camera.position.distanceTo(displayPoint);
            const ray = new Ray(camera.position.clone(), displayPoint.clone().sub(camera.position).normalize());
            for (const bound of bounds) {
              const hit = ray.intersectBox(bound, new Vector3());
              if (hit) expect(camera.position.distanceTo(hit)).toBeGreaterThan(distanceToScreen);
            }
          }
        }
      }
    }
  });

  it.each(viewports)("preserves the centered route handoff after a full head turn at %s × %s", (width, height) => {
    for (const yaw of [-DESK_LOOK_LIMIT.yaw, DESK_LOOK_LIMIT.yaw]) {
      for (const pitch of [-DESK_LOOK_LIMIT.pitch, DESK_LOOK_LIMIT.pitch]) {
        const camera = cameraAt(width, height, 1, { yaw, pitch });
        const center = projectDeskPoint(DESK_SCREEN.center, camera, width, height);
        expect(center.x).toBeCloseTo(width / 2, 7);
        expect(center.y).toBeCloseTo(height / 2, 7);
        const corners = monitorCorners(camera, width, height);
        expect(corners[0].x).toBeLessThan(0);
        expect(corners[1].x).toBeGreaterThan(width);
        expect(corners[0].y).toBeLessThan(0);
        expect(corners[3].y).toBeGreaterThan(height);
      }
    }
  });
});

import { describe, expect, it } from "vitest";
import { PerspectiveCamera } from "three";
import { DESK_CAMERA_FOV, DESK_LOOK_LIMIT, DESK_SCREEN, deskCameraFrame, type DeskLook } from "./deskSceneCamera";
import { monitorCorners, projectDeskPoint, quadTransform, type ScreenPoint } from "./deskProjection";

type Quad = [ScreenPoint, ScreenPoint, ScreenPoint, ScreenPoint];

function cameraAt(progress: number, width: number, height: number, look: DeskLook = { yaw: 0, pitch: 0 }) {
  const camera = new PerspectiveCamera(DESK_CAMERA_FOV, width / height, .1, 100);
  const frame = deskCameraFrame(progress, width / height, look);
  camera.position.set(...frame.position);
  camera.lookAt(...frame.target);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  return camera;
}

/** Browser CSS uses column-major matrix3d values and divides by homogeneous w. */
function applyCssMatrix(transform: string, x: number, y: number): ScreenPoint {
  const matrix = transform.slice("matrix3d(".length, -1).split(",").map(Number);
  expect(matrix).toHaveLength(16);
  expect(matrix.every(Number.isFinite)).toBe(true);
  const w = matrix[3] * x + matrix[7] * y + matrix[15];
  return {
    x: (matrix[0] * x + matrix[4] * y + matrix[12]) / w,
    y: (matrix[1] * x + matrix[5] * y + matrix[13]) / w,
  };
}

function expectMappedCorners(points: Quad, width = 1200, height = 502) {
  const transform = quadTransform(points, width, height);
  expect(transform).not.toBeNull();
  const local = [[0, 0], [width, 0], [width, height], [0, height]];
  local.forEach(([x, y], index) => {
    const mapped = applyCssMatrix(transform!, x, y);
    expect(mapped.x).toBeCloseTo(points[index].x, 7);
    expect(mapped.y).toBeCloseTo(points[index].y, 7);
  });
}

describe("interactive monitor projection", () => {
  it("maps all four HTML corners onto an oblique display quadrilateral", () => {
    expectMappedCorners([
      { x: 190, y: 110 }, { x: 935, y: 205 },
      { x: 840, y: 520 }, { x: 115, y: 620 },
    ]);
  });

  it("maps a translated, unskewed display without requiring perspective", () => {
    expectMappedCorners([
      { x: 31, y: 19 }, { x: 671, y: 19 },
      { x: 671, y: 319 }, { x: 31, y: 319 },
    ], 1280, 600);
  });

  it.each([[390, 844], [768, 1024], [1440, 900], [2560, 1080]])(
    "keeps the curved monitor projection finite and aligned in a %s × %s viewport",
    (width, height) => {
      for (const progress of [0, .25, .75, .99, 1]) {
        for (const side of [-1, 0, 1]) {
          const camera = cameraAt(progress, width, height, {
            yaw: side * DESK_LOOK_LIMIT.yaw,
            pitch: -side * DESK_LOOK_LIMIT.pitch,
          });
          const corners = monitorCorners(camera, width, height);
          expect(corners.flatMap(point => [point.x, point.y]).every(Number.isFinite)).toBe(true);
          expect(corners[1].x).toBeGreaterThan(corners[0].x);
          expect(corners[3].y).toBeGreaterThan(corners[0].y);
          expectMappedCorners(corners);
        }
      }
    },
  );

  it("projects the centered gaze to the viewport center at the HTML handoff", () => {
    const width = 1440, height = 900;
    const center = projectDeskPoint(DESK_SCREEN.center, cameraAt(1, width, height), width, height);
    expect(center.x).toBeCloseTo(width / 2, 8);
    expect(center.y).toBeCloseTo(height / 2, 8);
  });

  it("keeps the central mobile action reachable at both horizontal head limits", () => {
    for (const width of [320, 390, 540]) {
      for (const side of [-1, 1]) {
        const corners = monitorCorners(cameraAt(0, width, 844, { yaw: side * 100, pitch: 0 }), width, 844);
        const transform = quadTransform(corners, 420, 420 * DESK_SCREEN.height / DESK_SCREEN.width)!;
        // The compact action occupies the central 230px of the HTML display.
        for (const x of [95, 325]) {
          const point = applyCssMatrix(transform, x, 120);
          expect(point.x).toBeGreaterThan(0);
          expect(point.x).toBeLessThan(width);
        }
      }
    }
  });

  it("rejects invalid element dimensions and degenerate quads", () => {
    const square: Quad = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }];
    for (const [width, height] of [[0, 1], [1, 0], [-1, 1], [1, Number.NaN], [Number.POSITIVE_INFINITY, 1]]) {
      expect(quadTransform(square, width, height)).toBeNull();
    }
    expect(quadTransform([{ x: Number.NaN, y: 0 }, square[1], square[2], square[3]], 1200, 502)).toBeNull();
    expect(quadTransform([{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 2, y: 2 }, { x: 3, y: 3 }], 1200, 502)).toBeNull();
  });
});

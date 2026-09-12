import { Vector3, type Camera } from "three";
import { DESK_SCREEN, type DeskPoint } from "./deskSceneCamera";
export type ScreenPoint = { x: number; y: number };
export function projectDeskPoint(point: DeskPoint, camera: Camera, width: number, height: number): ScreenPoint {
  const projected = new Vector3(...point).project(camera);
  return { x: (projected.x + 1) * width / 2, y: (1 - projected.y) * height / 2 };
}
/** CSS homography keeps real selectable HTML aligned with the display. */
export function quadTransform(points: [ScreenPoint, ScreenPoint, ScreenPoint, ScreenPoint], width: number, height: number): string | null {
  if (![width, height, ...points.flatMap(p => [p.x, p.y])].every(Number.isFinite) || width <= 0 || height <= 0) return null;
  const [p0, p1, p2, p3] = points;
  const dx1 = p1.x - p2.x, dx2 = p3.x - p2.x, dx3 = p0.x - p1.x + p2.x - p3.x;
  const dy1 = p1.y - p2.y, dy2 = p3.y - p2.y, dy3 = p0.y - p1.y + p2.y - p3.y;
  const denominator = dx1 * dy2 - dx2 * dy1;
  if (Math.abs(denominator) < 1e-8) return null;
  const g = (dx3 * dy2 - dx2 * dy3) / denominator, h = (dx1 * dy3 - dx3 * dy1) / denominator;
  const matrix = [
    (p1.x - p0.x + g * p1.x) / width, (p1.y - p0.y + g * p1.y) / width, 0, g / width,
    (p3.x - p0.x + h * p3.x) / height, (p3.y - p0.y + h * p3.y) / height, 0, h / height,
    0, 0, 1, 0, p0.x, p0.y, 0, 1,
  ];
  return matrix.every(Number.isFinite) ? `matrix3d(${matrix.join(",")})` : null;
}
export function monitorCorners(camera: Camera, width: number, height: number): [ScreenPoint, ScreenPoint, ScreenPoint, ScreenPoint] {
  const [x, y, z] = DESK_SCREEN.center;
  return [[-1, 1], [1, 1], [1, -1], [-1, -1]].map(([side, vertical]) => projectDeskPoint([
    x + side * DESK_SCREEN.width / 2, y + vertical * DESK_SCREEN.height / 2, z + DESK_SCREEN.curvatureDepth + .004,
  ], camera, width, height)) as [ScreenPoint, ScreenPoint, ScreenPoint, ScreenPoint];
}

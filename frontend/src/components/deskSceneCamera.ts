export type DeskPhase = "home" | "entering" | "working" | "leaving";
export type DeskPoint = [number, number, number];
export type DeskLook = { yaw: number; pitch: number };
export const DESK_CAMERA_FOV = 42;
export const DESK_SCREEN = {
  center: [0, 2.56, -0.9] as DeskPoint,
  width: 3.25,
  height: 1.36,
  curvatureDepth: .10,
};
export const DESK_LOOK_LIMIT = { yaw: .34, pitch: .13 };
const finite = (value: number, fallback = 0) => Number.isFinite(value) ? value : fallback;
export function clampDeskLook(look: DeskLook, viewportAspect?: number): DeskLook {
  // Portrait viewports have a narrow horizontal FOV. Keep the central screen
  // reachable even at the end of a head turn, without permitting an orbit.
  const yawLimit = viewportAspect && Number.isFinite(viewportAspect) && viewportAspect > 0
    ? Math.min(DESK_LOOK_LIMIT.yaw, Math.atan(viewportAspect * Math.tan(DESK_CAMERA_FOV * Math.PI / 360)) * .45)
    : DESK_LOOK_LIMIT.yaw;
  return {
    yaw: Math.max(-yawLimit, Math.min(yawLimit, finite(look.yaw))),
    pitch: Math.max(-DESK_LOOK_LIMIT.pitch, Math.min(DESK_LOOK_LIMIT.pitch, finite(look.pitch))),
  };
}
export function deskEase(value: number): number {
  const t = Math.min(1, Math.max(0, finite(value)));
  return t * t * (3 - 2 * t);
}
/** A seated eye position, not an orbit around an avatar. Small screens use a
 * wider framing distance so the ultrawide display remains fully accessible. */
export function deskCameraFrame(progress: number, viewportAspect: number, requestedLook: DeskLook = { yaw: 0, pitch: 0 }): {
  position: DeskPoint; target: DeskPoint;
} {
  const aspect = Math.max(.3, Math.min(4, finite(viewportAspect, 1.7) || 1.7));
  const t = deskEase(progress), look = clampDeskLook(requestedLook, aspect);
  const halfFov = DESK_CAMERA_FOV * Math.PI / 360;
  const homeDistance = Math.max(4.05, DESK_SCREEN.width / (2 * aspect * Math.tan(halfFov)) * 1.15);
  const home: DeskPoint = [0, 2.96, DESK_SCREEN.center[2] + homeDistance];
  const endDistance = Math.min(DESK_SCREEN.height, DESK_SCREEN.width / aspect) / (2 * Math.tan(halfFov)) * .88;
  const end: DeskPoint = [0, DESK_SCREEN.center[1], DESK_SCREEN.center[2] + endDistance];
  const position = home.map((v, axis) => v + (end[axis] - v) * t) as DeskPoint;
  const basePitch = Math.atan2(2.30 - home[1], homeDistance);
  const yaw = look.yaw * (1 - t), pitch = (basePitch + look.pitch) * (1 - t);
  const length = homeDistance * (1 - t) + endDistance * t;
  const target: DeskPoint = t === 1 ? [...DESK_SCREEN.center] : [
    position[0] + Math.sin(yaw) * Math.cos(pitch) * length,
    position[1] + Math.sin(pitch) * length,
    position[2] - Math.cos(yaw) * Math.cos(pitch) * length,
  ];
  return { position, target };
}

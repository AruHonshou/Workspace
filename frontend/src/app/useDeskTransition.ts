import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

export type DeskPhase = "home" | "entering" | "working" | "leaving";

export function nextDeskPhase(phase: DeskPhase, atHome: boolean, immediate: boolean): DeskPhase {
  if (immediate) return atHome ? "home" : "working";
  if (atHome) return phase === "home" ? "home" : "leaving";
  return phase === "working" ? "working" : "entering";
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

/** Presentation never owns the route, starts a request, or resets a page. */
export function useDeskTransition(atHome: boolean, immediate: boolean) {
  const [phase, setPhase] = useState<DeskPhase>(() => atHome ? "home" : "working");
  const destination = useRef(atHome);
  destination.current = atHome;
  useLayoutEffect(() => {
    setPhase(current => nextDeskPhase(current, atHome, immediate));
  }, [atHome, immediate]);
  const settle = useCallback(() => setPhase(destination.current ? "home" : "working"), []);
  useEffect(() => {
    if (phase !== "entering" && phase !== "leaving") return;
    // A failed graphics context or slow lazy chunk must never block navigation.
    const timeout = window.setTimeout(settle, 1800);
    return () => window.clearTimeout(timeout);
  }, [phase, settle]);
  return { phase, settle };
}

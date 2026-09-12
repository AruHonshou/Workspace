import {
  useCallback,
  useLayoutEffect,
  useState,
  type CSSProperties,
  type RefObject,
} from "react";

type FloatingPlacement = "top" | "bottom";

interface FloatingMenuOptions<T extends HTMLElement> {
  open: boolean;
  triggerRef: RefObject<T | null>;
  minWidth?: number;
  maxWidth?: number;
  estimatedHeight?: number;
  align?: "start" | "end";
  gap?: number;
}

interface FloatingMenuLayout {
  style: CSSProperties;
  placement: FloatingPlacement;
  ready: boolean;
}

/**
 * Positions selection menus in the viewport instead of inside scrollable cards.
 * This keeps them above every panel and prevents clipping by modal overflow.
 */
export function useFloatingMenu<T extends HTMLElement>({
  open,
  triggerRef,
  minWidth = 240,
  maxWidth = 420,
  estimatedHeight = 320,
  align = "start",
  gap = 8,
}: FloatingMenuOptions<T>): FloatingMenuLayout {
  const [layout, setLayout] = useState<FloatingMenuLayout>({
    style: { visibility: "hidden" },
    placement: "bottom",
    ready: false,
  });

  const update = useCallback(() => {
    const trigger = triggerRef.current;
    if (!open || !trigger) return;

    const rect = trigger.getBoundingClientRect();
    const viewportPadding = 12;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(
      Math.max(rect.width, minWidth),
      maxWidth,
      Math.max(160, viewportWidth - viewportPadding * 2),
    );
    const roomBelow = Math.max(
      0,
      viewportHeight - rect.bottom - gap - viewportPadding,
    );
    const roomAbove = Math.max(0, rect.top - gap - viewportPadding);
    const placement: FloatingPlacement =
      roomBelow < Math.min(estimatedHeight, 190) && roomAbove > roomBelow
        ? "top"
        : "bottom";
    const available = placement === "bottom" ? roomBelow : roomAbove;
    const menuHeight = Math.min(
      estimatedHeight,
      Math.max(112, available),
    );
    const naturalLeft = align === "end" ? rect.right - width : rect.left;
    const left = Math.min(
      Math.max(viewportPadding, naturalLeft),
      Math.max(viewportPadding, viewportWidth - width - viewportPadding),
    );
    const top =
      placement === "bottom"
        ? Math.min(
            rect.bottom + gap,
            Math.max(viewportPadding, viewportHeight - menuHeight - viewportPadding),
          )
        : Math.max(viewportPadding, rect.top - gap - menuHeight);

    setLayout({
      style: {
        left,
        top,
        width,
        maxHeight: menuHeight,
        visibility: "visible",
      },
      placement,
      ready: true,
    });
  }, [align, estimatedHeight, gap, maxWidth, minWidth, open, triggerRef]);

  useLayoutEffect(() => {
    if (!open) {
      setLayout((current) =>
        current.ready
          ? { ...current, style: { visibility: "hidden" }, ready: false }
          : current,
      );
      return undefined;
    }

    update();
    const frame = window.requestAnimationFrame(update);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, update]);

  return layout;
}

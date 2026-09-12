import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextDeskPhase, useDeskTransition } from "./useDeskTransition";

afterEach(() => vi.useRealTimers());

describe("Desk presentation choreography", () => {
  it("opens direct module URLs immediately and animates only crossing the home boundary", () => {
    const { result, rerender } = renderHook(({ home }) => useDeskTransition(home, false), { initialProps: { home: false } });
    expect(result.current.phase).toBe("working");
    rerender({ home: false });
    expect(result.current.phase).toBe("working");
    rerender({ home: true });
    expect(result.current.phase).toBe("leaving");
    act(() => result.current.settle());
    expect(result.current.phase).toBe("home");
    rerender({ home: false });
    expect(result.current.phase).toBe("entering");
    act(() => result.current.settle());
    expect(result.current.phase).toBe("working");
  });

  it("reverses safely after quick Home/Back input; late completion settles the latest destination", () => {
    const { result, rerender } = renderHook(({ home }) => useDeskTransition(home, false), { initialProps: { home: true } });
    rerender({ home: false });
    const oldCallback = result.current.settle;
    rerender({ home: true });
    expect(result.current.phase).toBe("leaving");
    act(() => oldCallback());
    expect(result.current.phase).toBe("home");
  });

  it("does not trap navigation when the graphics module cannot finish", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ home }) => useDeskTransition(home, false), { initialProps: { home: true } });
    rerender({ home: false });
    expect(result.current.phase).toBe("entering");
    act(() => vi.advanceTimersByTime(1800));
    expect(result.current.phase).toBe("working");
  });

  it("bypasses camera motion for reduced-motion, static mode or graphics fallback", () => {
    expect(nextDeskPhase("home", false, true)).toBe("working");
    expect(nextDeskPhase("entering", true, true)).toBe("home");
    const { result, rerender } = renderHook(({ immediate }) => useDeskTransition(false, immediate), { initialProps: { immediate: false } });
    rerender({ immediate: true });
    expect(result.current.phase).toBe("working");
  });
});

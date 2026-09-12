import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { THEME_KEY, useWorkspaceTheme } from "./useWorkspaceTheme";

describe("workspace theme", () => {
  it("restores and persists the explicit choice", () => {
    localStorage.setItem(THEME_KEY, "dark");
    const { result } = renderHook(useWorkspaceTheme);
    expect(document.documentElement.dataset.workspaceTheme).toBe("dark");
    act(() => result.current.toggleTheme());
    expect(result.current.theme).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
  });

  it("still toggles when browser storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    const { result } = renderHook(useWorkspaceTheme);
    act(() => result.current.toggleTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("synchronizes an explicit choice from another tab", () => {
    const { result } = renderHook(useWorkspaceTheme);
    act(() => {
      localStorage.setItem(THEME_KEY, "dark");
      window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY }));
    });
    expect(result.current.theme).toBe("dark");
  });

  it("follows the system until a preference is selected and removes listeners", () => {
    let listener: (() => void) | undefined;
    const media = { matches: false, addEventListener: vi.fn((_event, callback) => { listener = callback; }), removeEventListener: vi.fn() };
    vi.spyOn(window, "matchMedia").mockReturnValue(media as unknown as MediaQueryList);
    const { result, unmount } = renderHook(useWorkspaceTheme);
    act(() => { media.matches = true; listener?.(); });
    expect(result.current.theme).toBe("dark");
    act(() => result.current.toggleTheme());
    act(() => { media.matches = false; listener?.(); media.matches = true; listener?.(); });
    expect(result.current.theme).toBe("light");
    unmount();
    expect(media.removeEventListener).toHaveBeenCalledWith("change", listener);
  });
});

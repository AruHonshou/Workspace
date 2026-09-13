import { describe, expect, it, vi } from "vitest";
import { migrateBrowserPreferences } from "./migrateBrowserPreferences";

describe("browser preference migration", () => {
  it("preserves the selected profile, country and saved search across an upgrade", () => {
    localStorage.setItem("career-orchestrator-profile-id", "profile_qa");
    localStorage.setItem("amework-search-country", "CR");
    localStorage.setItem("amework-simple-search", "search_saved");
    localStorage.setItem("workspace-theme", "dark");
    migrateBrowserPreferences();
    expect(localStorage.getItem("workspace-profile-id")).toBe("profile_qa");
    expect(localStorage.getItem("workspace-search-country")).toBe("CR");
    expect(localStorage.getItem("workspace-last-search-id")).toBe("search_saved");
    expect(localStorage.getItem("workspace-theme")).toBe("dark");
    expect(localStorage.getItem("amework-simple-search")).toBeNull();
    expect(localStorage.getItem("career-orchestrator-profile-id")).toBeNull();
    expect(localStorage.getItem("amework-search-country")).toBeNull();
  });

  it("keeps newer selections and is safe to run repeatedly", () => {
    localStorage.setItem("amework-search-country", "CR");
    localStorage.setItem("workspace-search-country", "CO");
    migrateBrowserPreferences();
    migrateBrowserPreferences();
    expect(localStorage.getItem("workspace-search-country")).toBe("CO");
    expect(localStorage.getItem("amework-search-country")).toBeNull();
  });

  it("retains the original when the browser cannot save the new key", () => {
    localStorage.setItem("amework-simple-search", "search_saved");
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Storage quota exceeded", "QuotaExceededError");
    });
    expect(() => migrateBrowserPreferences()).not.toThrow();
    expect(localStorage.getItem("amework-simple-search")).toBe("search_saved");
  });

  it("allows startup when access to storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Storage unavailable", "SecurityError");
    });
    expect(() => migrateBrowserPreferences()).not.toThrow();
  });
});

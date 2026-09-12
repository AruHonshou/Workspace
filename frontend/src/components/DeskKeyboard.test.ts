import { describe, expect, it } from "vitest";
import { DESK_KEYS, keyboardMayReact } from "./DeskKeyboard";

describe("decorative keyboard input boundary", () => {
  const keyEvent = (target: EventTarget | null = document.body) => ({ target, defaultPrevented: false, isComposing: false });

  it.each(["input", "textarea", "select", "button"])("ignores keys while %s is focused", (tag) => {
    const control = document.createElement(tag);
    expect(keyboardMayReact(keyEvent(), control)).toBe(false);
    expect(keyboardMayReact(keyEvent(control), document.body)).toBe(false);
  });

  it("also ignores editable descendants, form content, IME composition and handled shortcuts", () => {
    const editable = document.createElement("div");
    editable.setAttribute("contenteditable", "true");
    const child = editable.appendChild(document.createElement("span"));
    expect(keyboardMayReact(keyEvent(child), document.body)).toBe(false);
    const form = document.createElement("form");
    expect(keyboardMayReact(keyEvent(form.appendChild(document.createElement("div"))), null)).toBe(false);
    expect(keyboardMayReact({ ...keyEvent(), isComposing: true }, null)).toBe(false);
    expect(keyboardMayReact({ ...keyEvent(), defaultPrevented: true }, null)).toBe(false);
    expect(keyboardMayReact(keyEvent(), document.body)).toBe(true);
  });
});

describe("physical 75% keyboard layout", () => {
  it("has unique physical codes and non-overlapping keys inside the case", () => {
    expect(new Set(DESK_KEYS.map((key) => key.code)).size).toBe(DESK_KEYS.length);
    for (let row = 0; row < 6; row += 1) {
      const keys = DESK_KEYS.filter((key) => key.row === row).sort((a, b) => a.column - b.column);
      keys.forEach((key, index) => {
        expect(key.column).toBeGreaterThanOrEqual(0);
        expect(key.column + key.units).toBeLessThanOrEqual(16.25);
        if (index > 0) expect(key.column).toBeGreaterThanOrEqual(keys[index - 1].column + keys[index - 1].units);
      });
    }
  });

  it("includes the full alphabet, a real spacebar, staggered rows and an inverted-T arrow cluster", () => {
    for (const letter of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") expect(DESK_KEYS.some((key) => key.code === `Key${letter}`)).toBe(true);
    const key = (code: string) => DESK_KEYS.find((item) => item.code === code)!;
    expect(key("Space").units).toBe(6.25);
    expect(key("KeyQ").column).toBe(1.5);
    expect(key("KeyA").column).toBe(1.75);
    expect(key("KeyZ").column).toBe(2.25);
    expect(key("ArrowUp").column).toBe(key("ArrowDown").column);
    expect(key("ArrowUp").row).toBe(key("ArrowDown").row - 1);
    expect(key("ArrowLeft").column + 1).toBe(key("ArrowDown").column);
    expect(key("ArrowRight").column - 1).toBe(key("ArrowDown").column);
  });
});

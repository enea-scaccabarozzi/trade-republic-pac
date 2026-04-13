import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useKeyboardShortcuts } from "../use-keyboard-shortcuts";

function fireKey(key: string, opts: Partial<KeyboardEventInit> = {}) {
  document.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, ...opts }));
}

describe("useKeyboardShortcuts", () => {
  it("calls handler for a single-key shortcut", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "/", handler, description: "Focus search" }]));
    fireKey("/");
    expect(handler).toHaveBeenCalledOnce();
  });

  it("calls handler for a multi-key sequence", () => {
    vi.useFakeTimers();
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "g h", handler, description: "Go home" }]));
    fireKey("g");
    fireKey("h");
    expect(handler).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });

  it("allows Escape even when target is an input", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "Escape", handler, description: "Close" }]));

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(handler).toHaveBeenCalledOnce();
    document.body.removeChild(input);
  });

  it("ignores non-Escape keys when target is an input", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "/", handler, description: "Search" }]));

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
    expect(handler).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("ignores keys with modifier keys held", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "/", handler, description: "Search" }]));
    fireKey("/", { ctrlKey: true });
    fireKey("/", { metaKey: true });
    fireKey("/", { altKey: true });
    expect(handler).not.toHaveBeenCalled();
  });

  it("resets sequence after timeout", () => {
    vi.useFakeTimers();
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ keys: "g h", handler, description: "Go home" }]));
    fireKey("g");
    vi.advanceTimersByTime(600);
    fireKey("h");
    expect(handler).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("cleans up event listener on unmount", () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([{ keys: "/", handler, description: "Search" }]),
    );
    unmount();
    fireKey("/");
    expect(handler).not.toHaveBeenCalled();
  });
});

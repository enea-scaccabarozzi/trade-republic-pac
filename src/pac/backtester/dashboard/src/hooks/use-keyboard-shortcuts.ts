import { useEffect, useRef } from "react";

interface ShortcutHandler {
  keys: string;
  handler: () => void;
  description: string;
}

const INPUT_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function isInputTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement;
  return INPUT_TAGS.has(el.tagName) || el.isContentEditable;
}

function hasModifier(e: KeyboardEvent): boolean {
  return e.ctrlKey || e.metaKey || e.altKey;
}

function findMatch(shortcuts: ShortcutHandler[], keys: string): ShortcutHandler | undefined {
  return shortcuts.find((s) => s.keys === keys);
}

export function useKeyboardShortcuts(shortcuts: ShortcutHandler[]) {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  const sequenceRef = useRef<string[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const clearSequence = () => {
      sequenceRef.current = [];
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      const currentShortcuts = shortcutsRef.current;

      // Allow Escape through even in inputs
      if (e.key === "Escape") {
        findMatch(currentShortcuts, "Escape")?.handler();
        return;
      }

      if (isInputTarget(e.target)) return;
      if (hasModifier(e)) return;

      sequenceRef.current.push(e.key);

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => {
        sequenceRef.current = [];
      }, 500);

      const match = findMatch(currentShortcuts, sequenceRef.current.join(" "));
      if (match) {
        e.preventDefault();
        match.handler();
        clearSequence();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);
}

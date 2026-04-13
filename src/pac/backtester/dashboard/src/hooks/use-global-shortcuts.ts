import { useNavigate } from "@tanstack/react-router";
import { useShortcutsDialogStore } from "@/stores/shortcuts-dialog-store";
import { useKeyboardShortcuts } from "./use-keyboard-shortcuts";

export function useGlobalShortcuts() {
  const navigate = useNavigate();
  const openDialog = useShortcutsDialogStore((s) => s.open);

  useKeyboardShortcuts([
    {
      keys: "g h",
      handler: () => navigate({ to: "/" }),
      description: "Go to Dashboard Home",
    },
    {
      keys: "g r",
      handler: () => navigate({ to: "/run" }),
      description: "Go to Run Backtest",
    },
    {
      keys: "g c",
      handler: () => navigate({ to: "/compare" }),
      description: "Go to Compare",
    },
    {
      keys: "?",
      handler: () => openDialog(),
      description: "Open keyboard shortcuts",
    },
  ]);
}

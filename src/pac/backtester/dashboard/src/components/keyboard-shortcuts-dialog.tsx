import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useShortcutsDialogStore } from "@/stores/shortcuts-dialog-store";

interface ShortcutEntry {
  keys: string;
  description: string;
}

interface ShortcutGroup {
  title: string;
  shortcuts: ShortcutEntry[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: "Global",
    shortcuts: [
      { keys: "g h", description: "Go to Dashboard Home" },
      { keys: "g r", description: "Go to Run Backtest" },
      { keys: "g c", description: "Go to Compare" },
      { keys: "?", description: "Open keyboard shortcuts" },
    ],
  },
  {
    title: "Dashboard Home",
    shortcuts: [
      { keys: "n", description: "New backtest" },
      { keys: "/", description: "Focus search" },
      { keys: "Escape", description: "Clear search / close dialog" },
    ],
  },
];

function KeyBadge({ children }: { children: string }) {
  return (
    <kbd className="bg-muted rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">
      {children}
    </kbd>
  );
}

function renderKeys(keys: string) {
  const parts = keys.split(" ");
  return (
    <span className="flex items-center gap-1">
      {parts.map((part, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: key parts may repeat (e.g. "g g")
        <KeyBadge key={`${part}-${i}`}>{part}</KeyBadge>
      ))}
    </span>
  );
}

export function KeyboardShortcutsDialog() {
  const isOpen = useShortcutsDialogStore((s) => s.isOpen);
  const close = useShortcutsDialogStore((s) => s.close);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>Navigate the dashboard with keyboard shortcuts.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h4 className="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wider">
                {group.title}
              </h4>
              <div className="space-y-1.5">
                {group.shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.keys}
                    className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm"
                  >
                    <span>{shortcut.description}</span>
                    {renderKeys(shortcut.keys)}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <p className="text-muted-foreground mt-2 text-center text-xs">
          Press <KeyBadge>?</KeyBadge> anywhere to show this dialog
        </p>
      </DialogContent>
    </Dialog>
  );
}

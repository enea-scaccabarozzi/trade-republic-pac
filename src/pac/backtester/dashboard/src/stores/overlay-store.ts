import { create } from "zustand";
import { persist } from "zustand/middleware";

interface OverlayState {
  visibleOverlays: Record<string, boolean>;
  toggleOverlay: (key: string) => void;
  setOverlayVisible: (key: string, visible: boolean) => void;
  resetOverlays: () => void;
}

export const useOverlayStore = create<OverlayState>()(
  persist(
    (set) => ({
      visibleOverlays: {},
      toggleOverlay: (key) =>
        set((s) => ({
          visibleOverlays: {
            ...s.visibleOverlays,
            [key]: !s.visibleOverlays[key],
          },
        })),
      setOverlayVisible: (key, visible) =>
        set((s) => ({
          visibleOverlays: { ...s.visibleOverlays, [key]: visible },
        })),
      resetOverlays: () => set({ visibleOverlays: {} }),
    }),
    { name: "pac-overlay-prefs" },
  ),
);

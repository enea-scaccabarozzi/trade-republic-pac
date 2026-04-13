import { useEffect } from "react";
import { useUIStore } from "@/stores/ui-store";

export function useThemeEffect() {
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;

    function apply(resolved: "light" | "dark") {
      root.classList.toggle("dark", resolved === "dark");
    }

    if (theme !== "system") {
      apply(theme);
      return;
    }

    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    apply(mql.matches ? "dark" : "light");

    function onChange(e: MediaQueryListEvent) {
      apply(e.matches ? "dark" : "light");
    }
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [theme]);
}

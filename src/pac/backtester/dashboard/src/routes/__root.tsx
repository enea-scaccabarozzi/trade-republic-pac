import { createRootRoute, Outlet } from "@tanstack/react-router";
import { AppHeader } from "@/components/app-header";
import { AppSidebar } from "@/components/app-sidebar";
import { KeyboardShortcutsDialog } from "@/components/keyboard-shortcuts-dialog";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useGlobalShortcuts } from "@/hooks/use-global-shortcuts";
import { useThemeEffect } from "@/hooks/use-theme-effect";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  useThemeEffect();
  useGlobalShortcuts();

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AppSidebar />
        <div className="flex flex-1 flex-col">
          <AppHeader />
          <main className="flex-1 overflow-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
      <KeyboardShortcutsDialog />
    </SidebarProvider>
  );
}

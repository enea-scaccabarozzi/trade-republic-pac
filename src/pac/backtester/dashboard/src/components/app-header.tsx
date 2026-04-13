import { useRouterState } from "@tanstack/react-router";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

const routeLabels: Record<string, string> = {
  "/": "Dashboard",
  "/run": "Run Backtest",
  "/compare": "Compare",
  "/runs": "Runs",
};

function getBreadcrumbs(pathname: string): Array<{ label: string; href?: string }> {
  if (pathname === "/") {
    return [{ label: "Dashboard" }];
  }

  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Array<{ label: string; href?: string }> = [{ label: "Dashboard", href: "/" }];

  let path = "";
  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];
    if (!segment) continue;
    path += `/${segment}`;
    const isLast = i === segments.length - 1;
    const label = routeLabels[path] ?? segment;
    crumbs.push(isLast ? { label } : { label, href: path });
  }

  return crumbs;
}

export function AppHeader() {
  const routerState = useRouterState();
  const breadcrumbs = getBreadcrumbs(routerState.location.pathname);

  return (
    <header className="flex h-header shrink-0 items-center justify-between border-b px-4 bg-background">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            {breadcrumbs.map((crumb, idx) => (
              <BreadcrumbItem key={crumb.label}>
                {idx > 0 && <BreadcrumbSeparator />}
                {crumb.href ? (
                  <BreadcrumbLink href={crumb.href}>{crumb.label}</BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                )}
              </BreadcrumbItem>
            ))}
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <ThemeToggle />
    </header>
  );
}

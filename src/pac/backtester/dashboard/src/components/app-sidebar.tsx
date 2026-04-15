import { Link, useRouterState } from "@tanstack/react-router";
import {
	FlaskConical,
	GitCompareArrows,
	Keyboard,
	LayoutDashboard,
	Play,
} from "lucide-react";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useShortcutsDialogStore } from "@/stores/shortcuts-dialog-store";

const navItems = [
	{ label: "Dashboard", href: "/", icon: LayoutDashboard },
	{ label: "Research", href: "/research", icon: FlaskConical },
	{ label: "Run Backtest", href: "/run", icon: Play },
	{ label: "Compare", href: "/compare", icon: GitCompareArrows },
] as const;

export function AppSidebar() {
	const routerState = useRouterState();
	const currentPath = routerState.location.pathname;

	return (
		<Sidebar>
			<SidebarHeader className="border-b px-4 py-3">
				<span className="text-lg font-semibold tracking-tight">
					PAC Backtester
				</span>
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup>
					<SidebarGroupLabel>Navigation</SidebarGroupLabel>
					<SidebarGroupContent>
						<SidebarMenu>
							{navItems.map((item) => {
								const isActive =
									item.href === "/"
										? currentPath === "/"
										: currentPath.startsWith(item.href);
								return (
									<SidebarMenuItem key={item.href}>
										<SidebarMenuButton asChild isActive={isActive}>
											<Link to={item.href}>
												<item.icon className="size-4" />
												<span>{item.label}</span>
											</Link>
										</SidebarMenuButton>
									</SidebarMenuItem>
								);
							})}
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter className="border-t px-4 py-3">
				<button
					type="button"
					onClick={() => useShortcutsDialogStore.getState().open()}
					className="text-muted-foreground hover:text-foreground flex items-center gap-2 text-xs transition-colors"
				>
					<Keyboard className="size-3.5" />
					<span>Keyboard shortcuts</span>
					<kbd className="bg-muted ml-auto rounded border px-1.5 py-0.5 font-mono text-[10px]">
						?
					</kbd>
				</button>
			</SidebarFooter>
		</Sidebar>
	);
}

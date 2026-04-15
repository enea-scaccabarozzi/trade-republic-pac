import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const statusConfig: Record<string, { label: string; className: string }> = {
	exploring: {
		label: "Exploring",
		className:
			"border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
	},
	validated: {
		label: "Validated",
		className:
			"border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400",
	},
	rejected: {
		label: "Rejected",
		className: "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400",
	},
	published: {
		label: "Published",
		className:
			"border-purple-500/30 bg-purple-500/10 text-purple-600 dark:text-purple-400",
	},
};

interface StatusBadgeProps {
	status: string;
	className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
	const config = statusConfig[status] ?? {
		label: status,
		className: "border-border bg-muted text-muted-foreground",
	};

	return (
		<Badge variant="outline" className={cn(config.className, className)}>
			{config.label}
		</Badge>
	);
}

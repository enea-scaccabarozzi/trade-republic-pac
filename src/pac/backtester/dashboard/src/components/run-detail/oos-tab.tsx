import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDecimal } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { OOSMetadata } from "@/types/api";

const methodLabels: Record<string, string> = {
	holdout: "Temporal Holdout",
	walk_forward: "Walk-Forward",
	leave_one_event_out: "Leave-One-Event-Out",
};

function DegradationBadge({ ratio }: { ratio: number }) {
	let variant: string;
	if (ratio < 1.0) {
		variant =
			"border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400";
	} else if (ratio <= 1.5) {
		variant =
			"border-yellow-500/30 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400";
	} else {
		variant = "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400";
	}

	return (
		<Badge variant="outline" className={cn(variant)}>
			{formatDecimal(ratio, 2)}x
		</Badge>
	);
}

interface OOSTabProps {
	metadata: OOSMetadata;
}

export function OOSTab({ metadata }: OOSTabProps) {
	return (
		<div className="space-y-4">
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 text-sm">
						Out-of-Sample Validation
						<Badge variant="secondary">
							{methodLabels[metadata.method] ?? metadata.method}
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
						{metadata.holdout_date && (
							<div>
								<dt className="text-sm text-muted-foreground">Holdout Date</dt>
								<dd className="text-sm font-medium">{metadata.holdout_date}</dd>
							</div>
						)}
						{metadata.walk_forward_windows != null && (
							<div>
								<dt className="text-sm text-muted-foreground">
									Walk-Forward Windows
								</dt>
								<dd className="text-sm font-medium">
									{metadata.walk_forward_windows}
								</dd>
							</div>
						)}
						{metadata.event_calendar && (
							<div>
								<dt className="text-sm text-muted-foreground">
									Event Calendar
								</dt>
								<dd className="text-sm font-medium">
									{metadata.event_calendar}
								</dd>
							</div>
						)}
						{metadata.degradation_ratio != null && (
							<div>
								<dt className="text-sm text-muted-foreground">
									Degradation Ratio
								</dt>
								<dd className="flex items-center gap-2">
									<DegradationBadge ratio={metadata.degradation_ratio} />
								</dd>
							</div>
						)}
					</dl>
				</CardContent>
			</Card>
		</div>
	);
}

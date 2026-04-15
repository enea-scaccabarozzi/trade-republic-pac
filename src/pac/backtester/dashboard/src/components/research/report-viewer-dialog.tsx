import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";

interface ReportViewerDialogProps {
	experimentId: string;
	reportPath: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function ReportViewerDialog({
	experimentId,
	reportPath,
	open,
	onOpenChange,
}: ReportViewerDialogProps) {
	const filename = reportPath.split("/").pop() ?? reportPath;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-5xl">
				<DialogHeader>
					<DialogTitle>{filename}</DialogTitle>
				</DialogHeader>
				{open && reportPath && (
					<iframe
						title={`Report: ${filename}`}
						src={`/api/research/experiments/${experimentId}/files/${reportPath}`}
						sandbox="allow-same-origin"
						className="h-[80vh] w-full rounded-md border"
					/>
				)}
			</DialogContent>
		</Dialog>
	);
}

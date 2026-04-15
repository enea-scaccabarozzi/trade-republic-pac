import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ArtifactViewer } from "@/components/research/artifact-viewer";
import { ExperimentRuns } from "@/components/research/experiment-runs";
import { ReportViewerDialog } from "@/components/research/report-viewer-dialog";
import { StatusBadge } from "@/components/research/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useExperiment } from "@/hooks/use-research";
import { formatDate } from "@/lib/format";

export const Route = createFileRoute("/research/$id")({
  component: ExperimentDetail,
});

function ExperimentDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-10 w-80" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function groupByDirectory(paths: string[]) {
  const groups: Record<string, string[]> = {};
  for (const p of paths) {
    const parts = p.split("/");
    const dir = parts.length > 1 ? parts.slice(0, -1).join("/") : "";
    if (!groups[dir]) groups[dir] = [];
    groups[dir].push(p);
  }
  return groups;
}

export function ExperimentDetail() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const { data: experiment, isPending, isError } = useExperiment(id);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [reportDialog, setReportDialog] = useState<{
    open: boolean;
    path: string;
  }>({ open: false, path: "" });

  if (isPending) {
    return <ExperimentDetailSkeleton />;
  }

  if (isError || !experiment) {
    return (
      <EmptyState
        title="Experiment not found"
        description="This experiment may have been removed."
        action={{
          label: "Back to Research",
          onClick: () => navigate({ to: "/research" }),
        }}
      />
    );
  }

  const artifactGroups = groupByDirectory(experiment.artifacts);
  const description = `Created ${formatDate(experiment.created)}${experiment.concluded ? ` · Concluded ${formatDate(experiment.concluded)}` : ""}`;

  return (
    <div className="space-y-6">
      <PageHeader
        title={experiment.title}
        description={description}
        actions={<StatusBadge status={experiment.status} />}
      />

      {experiment.hypothesis && (
        <blockquote className="border-l-4 border-border pl-4 italic text-muted-foreground">
          {experiment.hypothesis}
        </blockquote>
      )}

      <div className="flex flex-wrap gap-2">
        {experiment.tags.map((tag) => (
          <Badge key={tag} variant="secondary">
            {tag}
          </Badge>
        ))}
        {experiment.strategy_name && (
          <Badge variant="outline">Strategy: {experiment.strategy_name}</Badge>
        )}
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs ({experiment.linked_run_ids.length})</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts ({experiment.artifacts.length})</TabsTrigger>
          <TabsTrigger value="reports">Reports ({experiment.reports.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          {experiment.readme_html ? (
            <Card>
              <CardContent className="prose prose-sm dark:prose-invert max-w-none pt-6">
                <div
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: server-sanitized HTML via nh3
                  dangerouslySetInnerHTML={{ __html: experiment.readme_html }}
                />
              </CardContent>
            </Card>
          ) : (
            <EmptyState
              title="No README"
              description="Add a README.md to the experiment directory."
            />
          )}

          {experiment.result_files.length > 0 && (
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-sm">Result Files</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>File</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {experiment.result_files.map((f) => (
                      <TableRow key={f}>
                        <TableCell className="font-mono text-sm">{f}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="runs" className="mt-6">
          {experiment.linked_run_ids.length === 0 ? (
            <EmptyState
              title="No runs linked"
              description="Run a backtest with this experiment to see results here."
            />
          ) : (
            <div className="space-y-4">
              {experiment.linked_run_ids.length > 1 && (
                <div className="flex justify-end">
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/compare" search={{ ids: experiment.linked_run_ids.join(",") }}>
                      Compare All
                    </Link>
                  </Button>
                </div>
              )}
              <ExperimentRuns runIds={experiment.linked_run_ids} />
            </div>
          )}
        </TabsContent>

        <TabsContent value="artifacts" className="mt-6">
          {experiment.artifacts.length === 0 ? (
            <EmptyState
              title="No artifacts"
              description="Artifacts will appear here when added to the experiment."
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle className="text-sm">Files</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {Object.entries(artifactGroups).map(([dir, files]) => (
                    <div key={dir}>
                      {dir && (
                        <p className="mb-1 text-xs font-medium text-muted-foreground">{dir}/</p>
                      )}
                      <ul className="space-y-0.5">
                        {files.map((f) => {
                          const filename = f.split("/").pop() ?? f;
                          return (
                            <li key={f}>
                              <Button
                                variant={selectedArtifact === f ? "secondary" : "ghost"}
                                size="sm"
                                className="w-full justify-start truncate font-mono text-xs"
                                onClick={() => setSelectedArtifact(f)}
                              >
                                {filename}
                              </Button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </CardContent>
              </Card>
              <Card className="lg:col-span-2">
                <CardContent className="pt-6">
                  {selectedArtifact ? (
                    <ArtifactViewer experimentId={id} filePath={selectedArtifact} />
                  ) : (
                    <p className="text-sm text-muted-foreground">Select a file to preview</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="reports" className="mt-6">
          {experiment.reports.length === 0 ? (
            <EmptyState
              title="No reports"
              description="Quantstats reports will appear here when generated."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {experiment.reports.map((report) => (
                <Card key={report}>
                  <CardContent className="flex items-center justify-between pt-6">
                    <span className="truncate text-sm font-mono">{report.split("/").pop()}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setReportDialog({ open: true, path: report })}
                    >
                      View
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <ReportViewerDialog
        experimentId={id}
        reportPath={reportDialog.path}
        open={reportDialog.open}
        onOpenChange={(open) => setReportDialog((prev) => ({ ...prev, open }))}
      />
    </div>
  );
}

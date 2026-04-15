import { Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { codeToHtml } from "shiki";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useExperimentFile } from "@/hooks/use-research";

interface ArtifactViewerProps {
  experimentId: string;
  filePath: string;
}

type FileType = "markdown" | "json" | "csv" | "code" | "image" | "binary";

function getFileType(filePath: string): FileType {
  const ext = filePath.split(".").pop()?.toLowerCase();
  if (ext === "md") return "markdown";
  if (ext === "json") return "json";
  if (ext === "csv") return "csv";
  if (["py", "toml", "yaml", "yml", "js", "ts", "sh"].includes(ext ?? "")) return "code";
  if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext ?? "")) return "image";
  return "binary";
}

function getShikiLang(
  filePath: string,
): "python" | "toml" | "yaml" | "javascript" | "typescript" | "bash" | "json" | "text" {
  const ext = filePath.split(".").pop()?.toLowerCase();
  const map: Record<
    string,
    "python" | "toml" | "yaml" | "javascript" | "typescript" | "bash" | "json"
  > = {
    py: "python",
    toml: "toml",
    yaml: "yaml",
    yml: "yaml",
    js: "javascript",
    ts: "typescript",
    sh: "bash",
    json: "json",
  };
  return map[ext ?? ""] ?? "text";
}

function splitCSV(text: string): string[][] {
  return text
    .trim()
    .split("\n")
    .map((line) => line.split(","));
}

function CSVTable({ content }: { content: string }) {
  const rows = useMemo(() => splitCSV(content), [content]);
  const [header, ...body] = rows;

  if (!header || header.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {header.map((cell, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: CSV header cells are positional
              <TableHead key={i}>{cell.trim()}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {body.map((row, ri) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: CSV rows are positional
            <TableRow key={ri}>
              {row.map((cell, ci) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: CSV cells are positional
                <TableCell key={ci} className="text-sm">
                  {cell.trim()}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SyntaxHighlighter({ code, lang }: { code: string; lang: string }) {
  const [html, setHtml] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    codeToHtml(code, {
      lang,
      theme: "github-dark-default",
    }).then((result) => {
      if (!cancelled) setHtml(result);
    });
    return () => {
      cancelled = true;
    };
  }, [code, lang]);

  if (!html) {
    return <pre className="overflow-x-auto rounded-md bg-muted p-4 text-xs">{code}</pre>;
  }

  return (
    <div
      className="overflow-x-auto rounded-md text-sm [&_pre]:p-4"
      // biome-ignore lint/security/noDangerouslySetInnerHtml: shiki generates safe HTML from code strings
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export function ArtifactViewer({ experimentId, filePath }: ArtifactViewerProps) {
  const fileType = getFileType(filePath);
  const { data, isPending, isError } = useExperimentFile(experimentId, filePath, {
    raw: fileType === "markdown",
  });

  // Revoke blob URLs on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (data?.type === "image" || data?.type === "binary") {
        URL.revokeObjectURL(data.content);
      }
    };
  }, [data]);

  if (isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load file: {filePath}</p>;
  }

  if (!data) return null;

  // Markdown files: use react-markdown with raw text
  if (fileType === "markdown" && data.type === "text") {
    return (
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <Markdown remarkPlugins={[remarkGfm]}>{data.content}</Markdown>
      </div>
    );
  }

  // CSV files: render as table
  if (fileType === "csv" && data.type === "text") {
    return <CSVTable content={data.content} />;
  }

  // JSON files: syntax highlighted
  if (data.type === "json") {
    return <SyntaxHighlighter code={JSON.stringify(data.content, null, 2)} lang="json" />;
  }

  // Code files: syntax highlighted
  if (fileType === "code" && data.type === "text") {
    return <SyntaxHighlighter code={data.content} lang={getShikiLang(filePath)} />;
  }

  // HTML content (server-rendered, e.g. non-raw markdown fallback)
  if (data.type === "text") {
    return (
      <div
        className="prose prose-sm dark:prose-invert max-w-none"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: server-sanitized HTML via nh3
        dangerouslySetInnerHTML={{ __html: data.content }}
      />
    );
  }

  // Images
  if (data.type === "image") {
    return <img src={data.content} alt={filePath} className="max-h-[600px] w-auto rounded-md" />;
  }

  // Binary / download fallback
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" asChild>
        <a href={`/api/research/experiments/${experimentId}/files/${filePath}`} download>
          <Download className="mr-1.5 size-3.5" />
          Download {filePath.split("/").pop()}
        </a>
      </Button>
    </div>
  );
}

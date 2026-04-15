import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from "vitest";

vi.mock("@/hooks/use-research", () => ({
  useExperimentFile: vi.fn(),
}));

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

vi.mock("remark-gfm", () => ({
  default: () => {},
}));

vi.mock("shiki", () => ({
  codeToHtml: vi.fn().mockResolvedValue("<pre><code>highlighted</code></pre>"),
}));

import { useExperimentFile } from "@/hooks/use-research";
import { ArtifactViewer } from "../artifact-viewer";

const mockUseExperimentFile = useExperimentFile as Mock;

function renderWithProviders(experimentId: string, filePath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ArtifactViewer experimentId={experimentId} filePath={filePath} />
    </QueryClientProvider>,
  );
}

describe("ArtifactViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders loading skeleton while pending", () => {
    mockUseExperimentFile.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    });
    const { container } = renderWithProviders("exp-1", "test.md");
    expect(container.querySelector("[data-slot='skeleton']")).toBeTruthy();
  });

  it("renders error message on failure", () => {
    mockUseExperimentFile.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    });
    renderWithProviders("exp-1", "test.md");
    expect(screen.getByText(/failed to load file/i)).toBeInTheDocument();
  });

  it("renders markdown content via react-markdown for .md files", () => {
    mockUseExperimentFile.mockReturnValue({
      data: { type: "text", content: "Hello World" },
      isPending: false,
      isError: false,
    });
    renderWithProviders("exp-1", "readme.md");
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("renders HTML content inline for non-markdown text type", () => {
    mockUseExperimentFile.mockReturnValue({
      data: { type: "text", content: "<p>Hello World</p>" },
      isPending: false,
      isError: false,
    });
    renderWithProviders("exp-1", "readme.html");
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("renders image with blob URL", () => {
    const blobUrl = "blob:http://localhost/test-image";
    mockUseExperimentFile.mockReturnValue({
      data: { type: "image", content: blobUrl },
      isPending: false,
      isError: false,
    });
    renderWithProviders("exp-1", "chart.png");
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", blobUrl);
  });

  it("renders JSON as pretty-printed code", () => {
    mockUseExperimentFile.mockReturnValue({
      data: { type: "json", content: { key: "value" } },
      isPending: false,
      isError: false,
    });
    renderWithProviders("exp-1", "data.json");
    expect(screen.getByText(/"key": "value"/)).toBeInTheDocument();
  });

  it("renders download link for binary type", () => {
    mockUseExperimentFile.mockReturnValue({
      data: { type: "binary", content: "blob:http://localhost/test" },
      isPending: false,
      isError: false,
    });
    renderWithProviders("exp-1", "file.bin");
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("download");
  });

  it("revokes blob URL on unmount", () => {
    const blobUrl = "blob:http://localhost/test-image";
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL");
    mockUseExperimentFile.mockReturnValue({
      data: { type: "image", content: blobUrl },
      isPending: false,
      isError: false,
    });
    const { unmount } = renderWithProviders("exp-1", "chart.png");
    unmount();
    expect(revokeObjectURL).toHaveBeenCalledWith(blobUrl);
    revokeObjectURL.mockRestore();
  });
});

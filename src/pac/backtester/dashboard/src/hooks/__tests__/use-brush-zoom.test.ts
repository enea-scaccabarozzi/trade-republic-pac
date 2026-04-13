import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useBrushZoom } from "../use-brush-zoom";

// Mock requestAnimationFrame to be synchronous for testing
vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
  cb(0);
  return 0;
});
vi.stubGlobal("cancelAnimationFrame", vi.fn());

describe("useBrushZoom", () => {
  it("initializes with full range", () => {
    const { result } = renderHook(() => useBrushZoom(100));
    expect(result.current.zoom.startIndex).toBe(0);
    expect(result.current.zoom.endIndex).toBe(99);
    expect(result.current.isZoomed).toBe(false);
  });

  it("updates zoom on brush change", () => {
    const { result } = renderHook(() => useBrushZoom(100));
    act(() => {
      result.current.handleBrushChange(10, 50);
    });
    expect(result.current.zoom.startIndex).toBe(10);
    expect(result.current.zoom.endIndex).toBe(50);
    expect(result.current.isZoomed).toBe(true);
  });

  it("resets zoom to full range", () => {
    const { result } = renderHook(() => useBrushZoom(100));
    act(() => {
      result.current.handleBrushChange(10, 50);
    });
    expect(result.current.isZoomed).toBe(true);

    act(() => {
      result.current.resetZoom();
    });
    expect(result.current.zoom.startIndex).toBe(0);
    expect(result.current.zoom.endIndex).toBe(99);
    expect(result.current.isZoomed).toBe(false);
  });

  it("resets zoom when totalPoints changes", () => {
    const { result, rerender } = renderHook(({ total }: { total: number }) => useBrushZoom(total), {
      initialProps: { total: 100 },
    });

    act(() => {
      result.current.handleBrushChange(10, 50);
    });
    expect(result.current.isZoomed).toBe(true);

    rerender({ total: 200 });
    expect(result.current.zoom.startIndex).toBe(0);
    expect(result.current.zoom.endIndex).toBe(199);
    expect(result.current.isZoomed).toBe(false);
  });

  it("handles zero points", () => {
    const { result } = renderHook(() => useBrushZoom(0));
    expect(result.current.zoom.startIndex).toBe(0);
    expect(result.current.zoom.endIndex).toBe(0);
    expect(result.current.isZoomed).toBe(false);
  });
});

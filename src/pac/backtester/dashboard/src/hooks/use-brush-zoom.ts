import { useCallback, useEffect, useRef, useState } from "react";

export interface BrushZoomState {
  startIndex: number;
  endIndex: number;
}

export function useBrushZoom(totalPoints: number) {
  const [zoom, setZoom] = useState<BrushZoomState>({
    startIndex: 0,
    endIndex: Math.max(0, totalPoints - 1),
  });

  useEffect(() => {
    setZoom({ startIndex: 0, endIndex: Math.max(0, totalPoints - 1) });
  }, [totalPoints]);

  const rafRef = useRef<number | null>(null);
  const handleBrushChange = useCallback((startIndex: number, endIndex: number) => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = requestAnimationFrame(() => {
      setZoom({ startIndex, endIndex });
      rafRef.current = null;
    });
  }, []);

  const resetZoom = useCallback(() => {
    setZoom({ startIndex: 0, endIndex: Math.max(0, totalPoints - 1) });
  }, [totalPoints]);

  const isZoomed = zoom.startIndex > 0 || zoom.endIndex < totalPoints - 1;

  return { zoom, handleBrushChange, resetZoom, isZoomed };
}

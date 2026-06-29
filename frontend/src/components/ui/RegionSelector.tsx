/**
 * RegionSelector - Canvas overlay for rectangular region selection on images.
 *
 * The operator can click-drag to define a rectangular crop area.
 * Coordinates are normalized (0.0 - 1.0) based on the image's displayed size.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

interface Region {
  x: number;   // 0.0 - 1.0
  y: number;   // 0.0 - 1.0
  width: number;  // 0.0 - 1.0
  height: number; // 0.0 - 1.0
}

interface RegionSelectorProps {
  /** URL or data URI of the image to display */
  imageUrl: string;
  /** Alt text for the image */
  alt?: string;
  /** Called whenever the selection region changes */
  onRegionChange: (region: Region | null) => void;
}

export function RegionSelector({ imageUrl, alt = 'Preview', onRegionChange }: RegionSelectorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [finalRegion, setFinalRegion] = useState<Region | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);

  const getImageElement = useCallback(() => {
    return imageRef.current;
  }, []);

  /** Convert pixel coordinates relative to the image to normalized 0-1 values */
  const normalize = useCallback((px: number, py: number) => {
    const img = getImageElement();
    if (!img || img.clientWidth === 0 || img.clientHeight === 0) return { x: 0, y: 0 };
    return {
      x: Math.max(0, Math.min(1, px / img.clientWidth)),
      y: Math.max(0, Math.min(1, py / img.clientHeight)),
    };
  }, [getImageElement]);

  /** Resize canvas to match displayed image size and redraw */
  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = getImageElement();
    if (!canvas || !img) return;

    const rect = img.getBoundingClientRect();
    const newWidth = Math.floor(rect.width);
    const newHeight = Math.floor(rect.height);

    // Only resize if dimensions changed
    if (canvas.width !== newWidth || canvas.height !== newHeight) {
      canvas.width = newWidth;
      canvas.height = newHeight;
    }

    // Redraw after resize
    drawOverlay();
  }, [getImageElement]);

  /** Draw the selection rectangle overlay on the canvas */
  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    if (w === 0 || h === 0) return;

    // Clear canvas
    ctx.clearRect(0, 0, w, h);

    const rectToDraw = currentRect ?? finalRegion
      ? currentRect ?? {
          x: (finalRegion?.x ?? 0) * w,
          y: (finalRegion?.y ?? 0) * h,
          w: (finalRegion?.width ?? 0) * w,
          h: (finalRegion?.height ?? 0) * h,
        }
      : null;

    if (!rectToDraw) return;

    // Draw semi-transparent dark overlay outside the selection
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(0, 0, w, h);

    // Cut out the selection rectangle (clear it so the image shows through)
    ctx.clearRect(rectToDraw.x, rectToDraw.y, rectToDraw.w, rectToDraw.h);

    // Draw dashed border around selection
    ctx.strokeStyle = '#60a5fa';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(
      rectToDraw.x + ctx.lineWidth / 2,
      rectToDraw.y + ctx.lineWidth / 2,
      rectToDraw.w - ctx.lineWidth,
      rectToDraw.h - ctx.lineWidth
    );
    ctx.setLineDash([]);

    // Draw corner handles for visual feedback
    const handleSize = 8;
    ctx.fillStyle = '#60a5fa';
    const corners = [
      [rectToDraw.x - handleSize / 2, rectToDraw.y - handleSize / 2],
      [rectToDraw.x + rectToDraw.w - handleSize / 2, rectToDraw.y - handleSize / 2],
      [rectToDraw.x - handleSize / 2, rectToDraw.y + rectToDraw.h - handleSize / 2],
      [rectToDraw.x + rectToDraw.w - handleSize / 2, rectToDraw.y + rectToDraw.h - handleSize / 2],
    ];
    for (const [cx, cy] of corners) {
      ctx.fillRect(cx, cy, handleSize, handleSize);
    }
  }, [currentRect, finalRegion]);

  /** Canvas drawing effect - triggered when rect changes or canvas is resized */
  useEffect(() => {
    drawOverlay();
  }, [drawOverlay]);

  /** Resize canvas on mount, window resize, and when image loads */
  useEffect(() => {
    if (!imageLoaded) return;

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, [imageLoaded, resizeCanvas]);

  /** Get pointer position relative to the image element */
  const getImageCoords = useCallback((clientX: number, clientY: number) => {
    const img = getImageElement();
    if (!img) return null;
    const rect = img.getBoundingClientRect();
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
    };
  }, [getImageElement]);

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const coords = getImageCoords(e.clientX, e.clientY);
    if (!coords) return;

    setIsDrawing(true);
    setStartPos(coords);
    setCurrentRect({ x: coords.x, y: coords.y, w: 0, h: 0 });
    // Clear any previous selection
    setFinalRegion(null);
    onRegionChange(null);
  }, [getImageCoords, onRegionChange]);

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPos) return;
    e.preventDefault();

    const coords = getImageCoords(e.clientX, e.clientY);
    if (!coords) return;

    const x = Math.min(startPos.x, coords.x);
    const y = Math.min(startPos.y, coords.y);
    const w = Math.abs(coords.x - startPos.x);
    const h = Math.abs(coords.y - startPos.y);

    setCurrentRect({ x, y, w, h });
  }, [isDrawing, startPos, getImageCoords]);

  const handlePointerUp = useCallback(() => {
    if (!isDrawing) {
      setIsDrawing(false);
      return;
    }

    setIsDrawing(false);

    if (currentRect && currentRect.w > 5 && currentRect.h > 5) {
      const img = getImageElement();
      if (img && img.clientWidth > 0 && img.clientHeight > 0) {
        const tl = normalize(currentRect.x, currentRect.y);
        const br = normalize(currentRect.x + currentRect.w, currentRect.y + currentRect.h);

        const region: Region = {
          x: tl.x,
          y: tl.y,
          width: Math.max(0, br.x - tl.x),
          height: Math.max(0, br.y - tl.y),
        };

        setFinalRegion(region);
        onRegionChange(region);
      }
    }

    setCurrentRect(null);
    setStartPos(null);
  }, [currentRect, isDrawing, getImageElement, normalize, onRegionChange]);

  const handleClear = useCallback(() => {
    setFinalRegion(null);
    setCurrentRect(null);
    onRegionChange(null);
  }, [onRegionChange]);

  const handleImageLoad = useCallback(() => {
    setImageLoaded(true);
    // Small delay to ensure layout is complete
    requestAnimationFrame(() => {
      resizeCanvas();
    });
  }, [resizeCanvas]);

  return (
    <div className="relative w-full">
      {/* Image container */}
      <div ref={containerRef} className="relative w-full rounded-lg overflow-hidden">
        <img
          ref={imageRef}
          src={imageUrl}
          alt={alt}
          className="w-full max-h-80 object-contain block"
          crossOrigin="anonymous"
          onLoad={handleImageLoad}
        />
        {/* Canvas overlay for drawing */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-crosshair touch-none"
          style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: '100%' }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
        />
      </div>

      {/* Clear button when a region is selected */}
      {finalRegion && (
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={handleClear}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Clear selection
          </button>
        </div>
      )}

      {/* Hint text */}
      {!finalRegion && !isDrawing && (
        <p className="mt-1 text-xs text-gray-400 text-center">
          Click and drag to select the region containing the name
        </p>
      )}
    </div>
  );
}

export default RegionSelector;

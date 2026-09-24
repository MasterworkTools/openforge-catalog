'use client'

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Blueprint, SpriteThumbnailData } from '@/types';
import { useDragRotation, VerticalView } from '@/hooks/use-drag-rotation';

/**
 * Helper functions to derive angle indices from sprite metadata
 */
function getAngleIndices(angles: SpriteThumbnailData['angles']) {
  const topIndex = angles.findIndex(a => a.name === 'top');
  const bottomIndex = angles.findIndex(a => a.name === 'bottom');

  // Count horizontal angles (all except top and bottom)
  const horizontalCount = angles.filter(
    a => a.name !== 'top' && a.name !== 'bottom'
  ).length;

  return {
    horizontalCount,
    topIndex: topIndex !== -1 ? topIndex : 8,  // Default fallback
    bottomIndex: bottomIndex !== -1 ? bottomIndex : 9,  // Default fallback
  };
}

/**
 * Custom hook for keyboard-based sprite rotation
 */
function useKeyboardRotation(
  currentAngle: number,
  setCurrentAngle: (angle: number | ((prev: number) => number)) => void,
  angleIndices: ReturnType<typeof getAngleIndices>
) {
  const { horizontalCount, topIndex, bottomIndex } = angleIndices;

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setCurrentAngle(prev => {
        // If we're on a vertical angle, go back to front (0)
        if (prev >= topIndex) return 0;
        // Otherwise, previous horizontal angle with wrapping
        return prev <= 0 ? horizontalCount - 1 : prev - 1;
      });
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setCurrentAngle(prev => {
        // If we're on a vertical angle, go to front (0)
        if (prev >= topIndex) return 0;
        // Otherwise, next horizontal angle with wrapping
        return prev >= horizontalCount - 1 ? 0 : prev + 1;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCurrentAngle(topIndex);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCurrentAngle(bottomIndex);
    }
  }, [setCurrentAngle, topIndex, bottomIndex, horizontalCount]);

  return { handleKeyDown };
}

/**
 * Drag to spin this sheet.
 *
 * The gesture itself — where it started, which axis won, how far
 * counts as a step — lives in `useDragRotation`, shared with the
 * guide's parts list. What is left here is the part that is about
 * *this* viewer: it thinks in frame indices within one sheet, where
 * the parts list thinks in angle names across several.
 */
function useMouseDragRotation(
  currentAngle: number,
  setCurrentAngle: (angle: number) => void,
  angleIndices: ReturnType<typeof getAngleIndices>
) {
  const { horizontalCount, topIndex, bottomIndex } = angleIndices;
  const initialAngle = useRef<number>(0);

  const onStart = useCallback(() => {
    initialAngle.current = currentAngle;
  }, [currentAngle]);

  const onHorizontal = useCallback(
    (steps: number) => {
      // Starting from a pole, a sideways drag means "come back to the
      // equator" rather than a rotation from a place that has none.
      if (
        initialAngle.current === topIndex ||
        initialAngle.current === bottomIndex
      ) {
        setCurrentAngle(0);
        return;
      }
      let next = (initialAngle.current + steps) % horizontalCount;
      if (next < 0) next += horizontalCount;
      setCurrentAngle(next);
    },
    [setCurrentAngle, horizontalCount, topIndex, bottomIndex]
  );

  const onVertical = useCallback(
    (face: VerticalView) => {
      setCurrentAngle(face === 'top' ? topIndex : bottomIndex);
    },
    [setCurrentAngle, topIndex, bottomIndex]
  );

  return useDragRotation({ onStart, onHorizontal, onVertical });
}

interface SpriteViewerProps {
  blueprint: Blueprint;
  thumbnailData: SpriteThumbnailData;
}

interface SpriteControlsProps {
  currentAngle: number;
  angles: SpriteThumbnailData['angles'];
  onAngleChange: (angle: number) => void;
}

const SpriteControls: React.FC<SpriteControlsProps> = ({ currentAngle, angles, onAngleChange }) => {
  // Build angle map dynamically from angle names to decouple from array order
  const angleMap: Record<number, { label: string; row: number; col: number }> = {};

  // Helper to find angle index by name
  const findAngleIndex = (name: string) => angles.findIndex(a => a.name === name);

  // Layout mapping: angle name -> grid position
  const layoutMap: Record<string, { label: string; row: number; col: number }> = {
    'top': { label: 'TOP', row: 0, col: 1 },
    'front-left': { label: 'FL', row: 1, col: 0 },
    'front': { label: 'F', row: 1, col: 1 },
    'front-right': { label: 'FR', row: 1, col: 2 },
    'left': { label: 'L', row: 2, col: 0 },
    'right': { label: 'R', row: 2, col: 2 },
    'back-left': { label: 'BL', row: 3, col: 0 },
    'back': { label: 'B', row: 3, col: 1 },
    'back-right': { label: 'BR', row: 3, col: 2 },
    'bottom': { label: 'BOT', row: 4, col: 1 },
  };

  // Build the dynamic angle map
  for (const [angleName, layout] of Object.entries(layoutMap)) {
    const angleIndex = findAngleIndex(angleName);
    if (angleIndex !== -1) {
      angleMap[angleIndex] = layout;
    }
  }

  return (
    <div>
      {/* Unwrapped cube layout */}
      <div className="grid grid-cols-3 gap-1" style={{ width: '120px' }}>
        {[0, 1, 2, 3, 4].map(row => (
          [0, 1, 2].map(col => {
            const angleEntry = Object.entries(angleMap).find(
              ([_, pos]) => pos.row === row && pos.col === col
            );

            if (!angleEntry) {
              // Empty cell
              return <div key={`${row}-${col}`} className="w-9 h-8" />;
            }

            const [angleIndexStr, pos] = angleEntry;
            const angleIndex = parseInt(angleIndexStr);
            const isActive = currentAngle === angleIndex;

            return (
              <button
                key={`${row}-${col}`}
                onClick={() => onAngleChange(angleIndex)}
                className={`w-9 h-8 text-xs font-medium rounded transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
                }`}
                aria-label={angles[angleIndex]?.name || pos.label}
                title={angles[angleIndex]?.name || pos.label}
                type="button"
              >
                {pos.label}
              </button>
            );
          })
        ))}
      </div>
    </div>
  );
};

const KeyboardHint: React.FC = () => (
  <div className="text-xs text-gray-500 mt-2 text-center">
    Use arrow keys or drag to rotate view
  </div>
);

/**
 * Downloads the preview image directly (CORS enabled on R2)
 */
function downloadSpriteSheet(spriteUrl: string, blueprintName: string) {
  const a = document.createElement('a');
  a.href = spriteUrl;
  a.download = `${blueprintName}-preview.png`;
  a.click();
}

const SpriteViewer: React.FC<SpriteViewerProps> = ({ blueprint, thumbnailData }) => {
  const [currentAngle, setCurrentAngle] = useState(thumbnailData.default_angle);
  const containerRef = useRef<HTMLDivElement>(null);
  const contextMenuCleanupRef = useRef<(() => void) | null>(null);

  // Derive angle indices from sprite metadata
  const angleIndices = getAngleIndices(thumbnailData.angles);

  // Use custom hooks for event handling
  const { handleKeyDown } = useKeyboardRotation(currentAngle, setCurrentAngle, angleIndices);
  const { handleMouseDown } = useMouseDragRotation(currentAngle, setCurrentAngle, angleIndices);

  // Calculate background position based on current angle
  const row = Math.floor(currentAngle / thumbnailData.grid_cols);
  const col = currentAngle % thumbnailData.grid_cols;
  const backgroundPositionX = -(col * thumbnailData.tile_size);
  const backgroundPositionY = -(row * thumbnailData.tile_size);

  // Auto-focus viewer on mount for immediate keyboard navigation
  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  // Cleanup context menu on unmount
  useEffect(() => {
    return () => {
      if (contextMenuCleanupRef.current) {
        contextMenuCleanupRef.current();
      }
    };
  }, []);

  const handleDownload = () => {
    downloadSpriteSheet(thumbnailData.sprite_url, blueprint.blueprint_name);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();

    // Clean up any existing context menu
    if (contextMenuCleanupRef.current) {
      contextMenuCleanupRef.current();
    }

    // Create a simple context menu
    const contextMenu = document.createElement('div');
    contextMenu.style.position = 'fixed';
    contextMenu.style.left = `${e.clientX}px`;
    contextMenu.style.top = `${e.clientY}px`;
    contextMenu.style.backgroundColor = 'white';
    contextMenu.style.border = '1px solid #ccc';
    contextMenu.style.borderRadius = '4px';
    contextMenu.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
    contextMenu.style.zIndex = '10000';
    contextMenu.style.padding = '4px 0';

    const downloadOption = document.createElement('div');
    downloadOption.textContent = 'Download preview image';
    downloadOption.style.padding = '8px 16px';
    downloadOption.style.cursor = 'pointer';
    downloadOption.style.fontSize = '14px';
    downloadOption.onmouseover = () => {
      downloadOption.style.backgroundColor = '#f0f0f0';
    };
    downloadOption.onmouseout = () => {
      downloadOption.style.backgroundColor = 'white';
    };
    downloadOption.onclick = () => {
      handleDownload();
      document.body.removeChild(contextMenu);
      contextMenuCleanupRef.current = null;
    };

    contextMenu.appendChild(downloadOption);
    document.body.appendChild(contextMenu);

    // Remove menu when clicking elsewhere
    const removeMenu = () => {
      if (document.body.contains(contextMenu)) {
        document.body.removeChild(contextMenu);
      }
      document.removeEventListener('click', removeMenu);
      contextMenuCleanupRef.current = null;
    };

    // Store cleanup function for component unmount
    contextMenuCleanupRef.current = removeMenu;
    setTimeout(() => document.addEventListener('click', removeMenu), 0);
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-col items-center focus:outline-none"
      data-testid="sprite-viewer-container"
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <div className="flex gap-4 items-center">
        <div className="relative">
          <div
            className="cursor-grab active:cursor-grabbing rounded"
            style={{
              backgroundImage: `url(${thumbnailData.sprite_url})`,
              backgroundPosition: `${backgroundPositionX}px ${backgroundPositionY}px`,
              width: `${thumbnailData.tile_size}px`,
              height: `${thumbnailData.tile_size}px`,
              backgroundRepeat: 'no-repeat',
              userSelect: 'none'
            }}
            onMouseDown={handleMouseDown}
            onContextMenu={handleContextMenu}
            aria-label={`${blueprint.blueprint_name} - 3D model view, current angle: ${thumbnailData.angles[currentAngle]?.name || currentAngle}`}
          />
          <button
            onClick={handleDownload}
            className="absolute bottom-2 right-2 bg-black bg-opacity-50 hover:bg-opacity-70 text-white rounded px-2 py-1 text-xs"
            title="Download preview image"
            type="button"
          >
            ⬇
          </button>
        </div>

        <SpriteControls
          currentAngle={currentAngle}
          angles={thumbnailData.angles}
          onAngleChange={setCurrentAngle}
        />
      </div>

      <KeyboardHint />
    </div>
  );
};

export default SpriteViewer;

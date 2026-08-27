/**
 * Smart Guides & Magnetic Snapping Algorithm for 2D Interactive Canvas
 * High performance, pure mathematical calculations optimized for 60 FPS.
 */

export interface SnapRect {
  id: string;
  left: number;       // Pixel X0
  top: number;        // Pixel Y0
  right: number;      // Pixel X1
  bottom: number;     // Pixel Y1
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

export interface GuideLine {
  id: string;
  type: 'vertical' | 'horizontal';
  position: number;    // X position for vertical, Y for horizontal
  start: number;       // Min Y for vertical, Min X for horizontal
  end: number;         // Max Y for vertical, Max X for horizontal
}

export interface SpacingIndicator {
  id: string;
  type: 'horizontal' | 'vertical';
  start: number;       // Start coordinate along the axis
  end: number;         // End coordinate along the axis
  crossAxisPos: number;// Position along the perpendicular axis
  distancePx: number;  // Measured pixel gap
  label: string;       // Formatted badge string e.g. "24px"
}

export interface SnapResult {
  snappedLeft: number;
  snappedTop: number;
  snappedWidth: number;
  snappedHeight: number;
  guides: GuideLine[];
  spacings: SpacingIndicator[];
}

export type ResizeDirection = 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'se' | 'sw';

/**
 * Converts percentage-based box bounds into pixel-based SnapRect
 */
export function toSnapRect(
  id: string,
  boxPct: { x0_pct: number; y0_pct: number; x1_pct: number; y1_pct: number },
  containerWidth: number,
  containerHeight: number
): SnapRect {
  const left = boxPct.x0_pct * containerWidth;
  const top = boxPct.y0_pct * containerHeight;
  const right = boxPct.x1_pct * containerWidth;
  const bottom = boxPct.y1_pct * containerHeight;
  const width = Math.max(1, right - left);
  const height = Math.max(1, bottom - top);

  return {
    id,
    left,
    top,
    right,
    bottom,
    width,
    height,
    centerX: left + width / 2,
    centerY: top + height / 2,
  };
}

/**
 * Pure function to calculate magnetic snapping and smart alignment guides.
 * Supports both whole-box Dragging and 8-handle Edge Resizing.
 */
export function calculateSnapping(
  activeRect: SnapRect,
  otherRects: SnapRect[],
  containerSize: { width: number; height: number },
  thresholdPx: number = 6,
  resizeDir?: ResizeDirection
): SnapResult {
  let deltaX = 0;
  let deltaY = 0;
  let deltaWidth = 0;
  let deltaHeight = 0;

  const guides: GuideLine[] = [];
  const spacings: SpacingIndicator[] = [];

  // If there are no other elements, snap to container bounds/center
  const targets: SnapRect[] = [
    ...otherRects,
    // Add canvas center lines as virtual targets
    {
      id: '__canvas_center',
      left: 0,
      top: 0,
      right: containerSize.width,
      bottom: containerSize.height,
      width: containerSize.width,
      height: containerSize.height,
      centerX: containerSize.width / 2,
      centerY: containerSize.height / 2,
    },
  ];

  // =========================================================================
  // 1. VERTICAL ALIGNMENT (X-AXIS SNAPPING)
  // =========================================================================
  const activeXPoints = resizeDir
    ? getResizeXPoints(activeRect, resizeDir)
    : [
        { type: 'left', pos: activeRect.left },
        { type: 'center', pos: activeRect.centerX },
        { type: 'right', pos: activeRect.right },
      ];

  let minDiffX = thresholdPx + 1;
  let bestSnapX: {
    delta: number;
    activePos: number;
    targetPos: number;
    startY: number;
    endY: number;
  } | null = null;

  for (const act of activeXPoints) {
    for (const target of targets) {
      if (target.id === activeRect.id) continue;

      const targetXPoints = [
        target.left,
        target.centerX,
        target.right,
      ];

      for (const tPos of targetXPoints) {
        const diff = tPos - act.pos;
        if (Math.abs(diff) <= thresholdPx && Math.abs(diff) < minDiffX) {
          minDiffX = Math.abs(diff);
          bestSnapX = {
            delta: diff,
            activePos: act.pos,
            targetPos: tPos,
            startY: Math.min(activeRect.top, target.top) - 15,
            endY: Math.max(activeRect.bottom, target.bottom) + 15,
          };
        }
      }
    }
  }

  if (bestSnapX) {
    if (!resizeDir) {
      deltaX = bestSnapX.delta;
    } else {
      if (resizeDir.includes('w')) {
        deltaX = bestSnapX.delta;
        deltaWidth = -bestSnapX.delta;
      } else if (resizeDir.includes('e')) {
        deltaWidth = bestSnapX.delta;
      }
    }

    guides.push({
      id: `guide-v-${bestSnapX.targetPos}`,
      type: 'vertical',
      position: bestSnapX.targetPos,
      start: Math.max(0, bestSnapX.startY),
      end: Math.min(containerSize.height, bestSnapX.endY),
    });
  }

  // =========================================================================
  // 2. HORIZONTAL ALIGNMENT (Y-AXIS SNAPPING)
  // =========================================================================
  const activeYPoints = resizeDir
    ? getResizeYPoints(activeRect, resizeDir)
    : [
        { type: 'top', pos: activeRect.top },
        { type: 'center', pos: activeRect.centerY },
        { type: 'bottom', pos: activeRect.bottom },
      ];

  let minDiffY = thresholdPx + 1;
  let bestSnapY: {
    delta: number;
    activePos: number;
    targetPos: number;
    startX: number;
    endX: number;
  } | null = null;

  for (const act of activeYPoints) {
    for (const target of targets) {
      if (target.id === activeRect.id) continue;

      const targetYPoints = [
        target.top,
        target.centerY,
        target.bottom,
      ];

      for (const tPos of targetYPoints) {
        const diff = tPos - act.pos;
        if (Math.abs(diff) <= thresholdPx && Math.abs(diff) < minDiffY) {
          minDiffY = Math.abs(diff);
          bestSnapY = {
            delta: diff,
            activePos: act.pos,
            targetPos: tPos,
            startX: Math.min(activeRect.left, target.left) - 15,
            endX: Math.max(activeRect.right, target.right) + 15,
          };
        }
      }
    }
  }

  if (bestSnapY) {
    if (!resizeDir) {
      deltaY = bestSnapY.delta;
    } else {
      if (resizeDir.includes('n')) {
        deltaY = bestSnapY.delta;
        deltaHeight = -bestSnapY.delta;
      } else if (resizeDir.includes('s')) {
        deltaHeight = bestSnapY.delta;
      }
    }

    guides.push({
      id: `guide-h-${bestSnapY.targetPos}`,
      type: 'horizontal',
      position: bestSnapY.targetPos,
      start: Math.max(0, bestSnapY.startX),
      end: Math.min(containerSize.width, bestSnapY.endX),
    });
  }

  // Adjusted active rect after edge/center snap
  const candidateRect: SnapRect = {
    ...activeRect,
    left: activeRect.left + deltaX,
    top: activeRect.top + deltaY,
    right: activeRect.right + deltaX + deltaWidth,
    bottom: activeRect.bottom + deltaY + deltaHeight,
    width: activeRect.width + deltaWidth,
    height: activeRect.height + deltaHeight,
    centerX: activeRect.left + deltaX + (activeRect.width + deltaWidth) / 2,
    centerY: activeRect.top + deltaY + (activeRect.height + deltaHeight) / 2,
  };

  // =========================================================================
  // 3. EQUIDISTANT SMART SPACING (GAP DETECTION)
  // =========================================================================
  if (!resizeDir && otherRects.length >= 2) {
    const horizontalSpacings = detectEquidistantHorizontal(candidateRect, otherRects, thresholdPx);
    if (horizontalSpacings) {
      deltaX += horizontalSpacings.deltaX;
      spacings.push(...horizontalSpacings.indicators);
    }

    const verticalSpacings = detectEquidistantVertical(candidateRect, otherRects, thresholdPx);
    if (verticalSpacings) {
      deltaY += verticalSpacings.deltaY;
      spacings.push(...verticalSpacings.indicators);
    }
  }

  return {
    snappedLeft: activeRect.left + deltaX,
    snappedTop: activeRect.top + deltaY,
    snappedWidth: Math.max(10, activeRect.width + deltaWidth),
    snappedHeight: Math.max(8, activeRect.height + deltaHeight),
    guides,
    spacings,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getResizeXPoints(rect: SnapRect, dir: ResizeDirection) {
  if (dir.includes('w')) return [{ type: 'left', pos: rect.left }];
  if (dir.includes('e')) return [{ type: 'right', pos: rect.right }];
  return [];
}

function getResizeYPoints(rect: SnapRect, dir: ResizeDirection) {
  if (dir.includes('n')) return [{ type: 'top', pos: rect.top }];
  if (dir.includes('s')) return [{ type: 'bottom', pos: rect.bottom }];
  return [];
}

/**
 * Detect equidistant gaps horizontally among boxes (e.g. Box A <gap> Box B <gap> Active Box)
 */
function detectEquidistantHorizontal(
  active: SnapRect,
  others: SnapRect[],
  thresholdPx: number
): { deltaX: number; indicators: SpacingIndicator[] } | null {
  // Sort others along X
  const sorted = [...others].sort((a, b) => a.left - b.left);

  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];

    // Reference gap between A and B
    const refGap = b.left - a.right;
    if (refGap <= 0) continue; // Overlapping or inverted

    // Case 1: Active is to the right of B (A -> B -> Active)
    const gapToRight = active.left - b.right;
    if (Math.abs(gapToRight - refGap) <= thresholdPx) {
      const deltaX = (b.right + refGap) - active.left;
      const midY = (a.centerY + b.centerY + active.centerY) / 3;

      return {
        deltaX,
        indicators: [
          {
            id: `space-h-ref-${a.id}-${b.id}`,
            type: 'horizontal',
            start: a.right,
            end: b.left,
            crossAxisPos: midY,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
          {
            id: `space-h-act-${b.id}-${active.id}`,
            type: 'horizontal',
            start: b.right,
            end: b.right + refGap,
            crossAxisPos: midY,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
        ],
      };
    }

    // Case 2: Active is to the left of A (Active -> A -> B)
    const gapToLeft = a.left - active.right;
    if (Math.abs(gapToLeft - refGap) <= thresholdPx) {
      const deltaX = (a.left - refGap - active.width) - active.left;
      const midY = (a.centerY + b.centerY + active.centerY) / 3;

      return {
        deltaX,
        indicators: [
          {
            id: `space-h-ref-${a.id}-${b.id}`,
            type: 'horizontal',
            start: a.right,
            end: b.left,
            crossAxisPos: midY,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
          {
            id: `space-h-act-${active.id}-${a.id}`,
            type: 'horizontal',
            start: a.left - refGap,
            end: a.left,
            crossAxisPos: midY,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
        ],
      };
    }
  }

  return null;
}

/**
 * Detect equidistant gaps vertically among boxes (e.g. Box A <gap> Box B <gap> Active Box)
 */
function detectEquidistantVertical(
  active: SnapRect,
  others: SnapRect[],
  thresholdPx: number
): { deltaY: number; indicators: SpacingIndicator[] } | null {
  // Sort others along Y
  const sorted = [...others].sort((a, b) => a.top - b.top);

  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];

    // Reference gap between A and B
    const refGap = b.top - a.bottom;
    if (refGap <= 0) continue;

    // Case 1: Active is below B (A -> B -> Active)
    const gapBelow = active.top - b.bottom;
    if (Math.abs(gapBelow - refGap) <= thresholdPx) {
      const deltaY = (b.bottom + refGap) - active.top;
      const midX = (a.centerX + b.centerX + active.centerX) / 3;

      return {
        deltaY,
        indicators: [
          {
            id: `space-v-ref-${a.id}-${b.id}`,
            type: 'vertical',
            start: a.bottom,
            end: b.top,
            crossAxisPos: midX,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
          {
            id: `space-v-act-${b.id}-${active.id}`,
            type: 'vertical',
            start: b.bottom,
            end: b.bottom + refGap,
            crossAxisPos: midX,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
        ],
      };
    }

    // Case 2: Active is above A (Active -> A -> B)
    const gapAbove = a.top - active.bottom;
    if (Math.abs(gapAbove - refGap) <= thresholdPx) {
      const deltaY = (a.top - refGap - active.height) - active.top;
      const midX = (a.centerX + b.centerX + active.centerX) / 3;

      return {
        deltaY,
        indicators: [
          {
            id: `space-v-ref-${a.id}-${b.id}`,
            type: 'vertical',
            start: a.bottom,
            end: b.top,
            crossAxisPos: midX,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
          {
            id: `space-v-act-${active.id}-${a.id}`,
            type: 'vertical',
            start: a.top - refGap,
            end: a.top,
            crossAxisPos: midX,
            distancePx: Math.round(refGap),
            label: `${Math.round(refGap)}px`,
          },
        ],
      };
    }
  }

  return null;
}

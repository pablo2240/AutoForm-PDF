import React from 'react';
import type { GuideLine, SpacingIndicator } from '../utils/snapping';

export interface SmartGuidesOverlayProps {
  guides: GuideLine[];
  spacings: SpacingIndicator[];
  width: number;
  height: number;
}

export const SmartGuidesOverlay: React.FC<SmartGuidesOverlayProps> = ({
  guides,
  spacings,
  width,
  height,
}) => {
  if (guides.length === 0 && spacings.length === 0) {
    return null;
  }

  return (
    <div 
      className="smart-guides-overlay"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 90,
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} 0${height}`}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          overflow: 'visible',
        }}
      >
        <defs>
          {/* Neon Purple Glow Filter */}
          <filter id="purpleGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* 1. Alignment Guide Lines (Purple / Violet) */}
        {guides.map((g) => {
          if (g.type === 'vertical') {
            return (
              <g key={g.id}>
                {/* Glow underlay */}
                <line
                  x1={g.position}
                  y1={g.start}
                  x2={g.position}
                  y2={g.end}
                  stroke="#a855f7"
                  strokeWidth="3"
                  opacity="0.4"
                  filter="url(#purpleGlow)"
                />
                {/* Main line */}
                <line
                  x1={g.position}
                  y1={g.start}
                  x2={g.position}
                  y2={g.end}
                  stroke="#c084fc"
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                />
                {/* End dots */}
                <circle cx={g.position} cy={g.start} r="2.5" fill="#f3e8ff" stroke="#9333ea" strokeWidth="1" />
                <circle cx={g.position} cy={g.end} r="2.5" fill="#f3e8ff" stroke="#9333ea" strokeWidth="1" />
              </g>
            );
          } else {
            return (
              <g key={g.id}>
                {/* Glow underlay */}
                <line
                  x1={g.start}
                  y1={g.position}
                  x2={g.end}
                  y2={g.position}
                  stroke="#a855f7"
                  strokeWidth="3"
                  opacity="0.4"
                  filter="url(#purpleGlow)"
                />
                {/* Main line */}
                <line
                  x1={g.start}
                  y1={g.position}
                  x2={g.end}
                  y2={g.position}
                  stroke="#c084fc"
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                />
                {/* End dots */}
                <circle cx={g.start} cy={g.position} r="2.5" fill="#f3e8ff" stroke="#9333ea" strokeWidth="1" />
                <circle cx={g.end} cy={g.position} r="2.5" fill="#f3e8ff" stroke="#9333ea" strokeWidth="1" />
              </g>
            );
          }
        })}

        {/* 2. Equidistant Spacing Indicators (Pink / Magenta with measurement ticks) */}
        {spacings.map((s) => {
          const isH = s.type === 'horizontal';
          const midX = isH ? (s.start + s.end) / 2 : s.crossAxisPos;
          const midY = isH ? s.crossAxisPos : (s.start + s.end) / 2;

          return (
            <g key={s.id}>
              {/* Dimension bar */}
              {isH ? (
                <>
                  <line
                    x1={s.start}
                    y1={s.crossAxisPos}
                    x2={s.end}
                    y2={s.crossAxisPos}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                  {/* Start tick */}
                  <line
                    x1={s.start}
                    y1={s.crossAxisPos - 5}
                    x2={s.start}
                    y2={s.crossAxisPos + 5}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                  {/* End tick */}
                  <line
                    x1={s.end}
                    y1={s.crossAxisPos - 5}
                    x2={s.end}
                    y2={s.crossAxisPos + 5}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                </>
              ) : (
                <>
                  <line
                    x1={s.crossAxisPos}
                    y1={s.start}
                    x2={s.crossAxisPos}
                    y2={s.end}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                  {/* Start tick */}
                  <line
                    x1={s.crossAxisPos - 5}
                    y1={s.start}
                    x2={s.crossAxisPos + 5}
                    y2={s.start}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                  {/* End tick */}
                  <line
                    x1={s.crossAxisPos - 5}
                    y1={s.end}
                    x2={s.crossAxisPos + 5}
                    y2={s.end}
                    stroke="#ec4899"
                    strokeWidth="1.5"
                  />
                </>
              )}

              {/* Distance Pill Badge */}
              <foreignObject
                x={midX - 22}
                y={midY - 10}
                width="44"
                height="20"
                style={{ overflow: 'visible' }}
              >
                <div className="smart-spacing-badge">
                  {s.label}
                </div>
              </foreignObject>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

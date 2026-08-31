import React, { useState, useRef, useEffect } from 'react';
import type { PDFPage, MappingItem, CompanyData, BoxCoords, BoxPct, ItemStyle } from '../types';
import { X, ZoomIn, ZoomOut, Maximize2, Crosshair, Image as ImageIcon } from 'lucide-react';
import { 
  calculateSnapping, 
  toSnapRect, 
  type GuideLine, 
  type SpacingIndicator,
  type ResizeDirection 
} from '../utils/snapping';
import { SmartGuidesOverlay } from './SmartGuidesOverlay';

interface PDFCanvasProps {
  page: PDFPage | null;
  selectedField: string | null;
  activeImage: { base64: string; filename: string } | null;
  currentStyle: ItemStyle;
  companyData: CompanyData;
  mappings: MappingItem[];
  currentPage: number;
  selectedBoxId: string | null;
  onSelectBox: (id: string | null) => void;
  onAddBox: (box: BoxCoords, boxPct: BoxPct, customStyle?: ItemStyle) => void;
  onUpdateMapping: (id: string, box: BoxCoords, boxPct: BoxPct) => void;
  onDeleteMapping: (id: string) => void;
}

interface DrawingRect {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

interface DragBoxState {
  id: string;
  startClientX: number;
  startClientY: number;
  initialBox: BoxCoords;
  initialBoxPct: BoxPct;
}

type ResizeDir = 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w';

interface ResizeBoxState {
  id: string;
  dir: ResizeDir;
  startClientX: number;
  startClientY: number;
  initialBox: BoxCoords;
  initialBoxPct: BoxPct;
}

export const PDFCanvas: React.FC<PDFCanvasProps> = ({
  page,
  selectedField,
  activeImage,
  currentStyle,
  companyData,
  mappings,
  currentPage,
  selectedBoxId,
  onSelectBox,
  onAddBox,
  onUpdateMapping,
  onDeleteMapping,
}) => {
  const imageRef = useRef<HTMLImageElement>(null);
  const [drawing, setDrawing] = useState<DrawingRect | null>(null);
  const [dragBoxState, setDragBoxState] = useState<DragBoxState | null>(null);
  const [resizeBoxState, setResizeBoxState] = useState<ResizeBoxState | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(100);

  // Smart Guides State
  const [activeGuides, setActiveGuides] = useState<GuideLine[]>([]);
  const [activeSpacings, setActiveSpacings] = useState<SpacingIndicator[]>([]);

  // Global mouse up for smooth dragging and resizing release
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (dragBoxState) {
        setDragBoxState(null);
        setActiveGuides([]);
        setActiveSpacings([]);
      }
      if (resizeBoxState) {
        setResizeBoxState(null);
        setActiveGuides([]);
        setActiveSpacings([]);
      }
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [dragBoxState, resizeBoxState]);

  if (!page) {
    return (
      <div className="canvas-empty-state">
        <div className="spinner"></div>
        <p>Cargando página del formulario...</p>
      </div>
    );
  }

  const currentMappings = mappings.filter((m) => m.page_number === currentPage);

  const getPointerCoords = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!imageRef.current) return { x: 0, y: 0 };
    const rect = imageRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const y = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
    return { x, y, width: rect.width, height: rect.height };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    
    // Clicking empty space deselects current box
    if (!selectedField && !activeImage) {
      onSelectBox(null);
      return;
    }

    const coords = getPointerCoords(e);
    setDrawing({
      startX: coords.x,
      startY: coords.y,
      currentX: coords.x,
      currentY: coords.y,
    });
  };

  const handleBoxMouseDown = (e: React.MouseEvent, item: MappingItem) => {
    e.stopPropagation();
    onSelectBox(item.id);

    // Left or right click drag support for repositioning
    if (imageRef.current) {
      const x0_pct = item.box_pct?.x0_pct ?? (item.box.x0 / page.page_width_pts);
      const y0_pct = item.box_pct?.y0_pct ?? (item.box.y0 / page.page_height_pts);
      const x1_pct = item.box_pct?.x1_pct ?? (item.box.x1 / page.page_width_pts);
      const y1_pct = item.box_pct?.y1_pct ?? (item.box.y1 / page.page_height_pts);

      setDragBoxState({
        id: item.id,
        startClientX: e.clientX,
        startClientY: e.clientY,
        initialBox: { ...item.box },
        initialBoxPct: { x0_pct, y0_pct, x1_pct, y1_pct },
      });
    }
  };

  const handleResizeMouseDown = (e: React.MouseEvent, item: MappingItem, dir: ResizeDir) => {
    e.stopPropagation();
    e.preventDefault();
    onSelectBox(item.id);

    const x0_pct = item.box_pct?.x0_pct ?? (item.box.x0 / page.page_width_pts);
    const y0_pct = item.box_pct?.y0_pct ?? (item.box.y0 / page.page_height_pts);
    const x1_pct = item.box_pct?.x1_pct ?? (item.box.x1 / page.page_width_pts);
    const y1_pct = item.box_pct?.y1_pct ?? (item.box.y1 / page.page_height_pts);

    setResizeBoxState({
      id: item.id,
      dir,
      startClientX: e.clientX,
      startClientY: e.clientY,
      initialBox: { ...item.box },
      initialBoxPct: { x0_pct, y0_pct, x1_pct, y1_pct },
    });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    // 1. Handle resizing box with Smart Guides & Snapping
    if (resizeBoxState && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const deltaX = (e.clientX - resizeBoxState.startClientX) / rect.width;
      const deltaY = (e.clientY - resizeBoxState.startClientY) / rect.height;

      let { x0_pct, y0_pct, x1_pct, y1_pct } = resizeBoxState.initialBoxPct;

      if (resizeBoxState.dir.includes('e')) {
        x1_pct = Math.max(x0_pct + 0.01, Math.min(1.0, resizeBoxState.initialBoxPct.x1_pct + deltaX));
      } else if (resizeBoxState.dir.includes('w')) {
        x0_pct = Math.min(x1_pct - 0.01, Math.max(0.0, resizeBoxState.initialBoxPct.x0_pct + deltaX));
      }

      if (resizeBoxState.dir.includes('s')) {
        y1_pct = Math.max(y0_pct + 0.008, Math.min(1.0, resizeBoxState.initialBoxPct.y1_pct + deltaY));
      } else if (resizeBoxState.dir.includes('n')) {
        y0_pct = Math.min(y1_pct - 0.008, Math.max(0.0, resizeBoxState.initialBoxPct.y0_pct + deltaY));
      }

      // Convert to SnapRect and apply magnetic edge snapping
      const activeSnapRect = toSnapRect(resizeBoxState.id, { x0_pct, y0_pct, x1_pct, y1_pct }, rect.width, rect.height);
      const otherSnapRects = currentMappings
        .filter((m) => m.id !== resizeBoxState.id)
        .map((m) => {
          const m_x0 = m.box_pct?.x0_pct ?? (m.box.x0 / page.page_width_pts);
          const m_y0 = m.box_pct?.y0_pct ?? (m.box.y0 / page.page_height_pts);
          const m_x1 = m.box_pct?.x1_pct ?? (m.box.x1 / page.page_width_pts);
          const m_y1 = m.box_pct?.y1_pct ?? (m.box.y1 / page.page_height_pts);
          return toSnapRect(m.id, { x0_pct: m_x0, y0_pct: m_y0, x1_pct: m_x1, y1_pct: m_y1 }, rect.width, rect.height);
        });

      const snapResult = calculateSnapping(
        activeSnapRect,
        otherSnapRects,
        { width: rect.width, height: rect.height },
        6,
        resizeBoxState.dir as ResizeDirection
      );

      setActiveGuides(snapResult.guides);
      setActiveSpacings(snapResult.spacings);

      const final_x0_pct = Math.max(0, snapResult.snappedLeft / rect.width);
      const final_y0_pct = Math.max(0, snapResult.snappedTop / rect.height);
      const final_x1_pct = Math.min(1, (snapResult.snappedLeft + snapResult.snappedWidth) / rect.width);
      const final_y1_pct = Math.min(1, (snapResult.snappedTop + snapResult.snappedHeight) / rect.height);

      const newBoxPct: BoxPct = {
        x0_pct: final_x0_pct,
        y0_pct: final_y0_pct,
        x1_pct: final_x1_pct,
        y1_pct: final_y1_pct,
      };

      const newBox: BoxCoords = {
        x0: final_x0_pct * page.page_width_pts,
        y0: final_y0_pct * page.page_height_pts,
        x1: final_x1_pct * page.page_width_pts,
        y1: final_y1_pct * page.page_height_pts,
      };

      onUpdateMapping(resizeBoxState.id, newBox, newBoxPct);
      return;
    }

    // 2. Handle dragging box position with Smart Guides & Snapping (60 FPS)
    if (dragBoxState && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const deltaX = (e.clientX - dragBoxState.startClientX) / rect.width;
      const deltaY = (e.clientY - dragBoxState.startClientY) / rect.height;

      const initPct = dragBoxState.initialBoxPct;
      const boxWidthPct = initPct.x1_pct - initPct.x0_pct;
      const boxHeightPct = initPct.y1_pct - initPct.y0_pct;

      const raw_x0_pct = Math.max(0, Math.min(1 - boxWidthPct, initPct.x0_pct + deltaX));
      const raw_y0_pct = Math.max(0, Math.min(1 - boxHeightPct, initPct.y0_pct + deltaY));
      const raw_x1_pct = raw_x0_pct + boxWidthPct;
      const raw_y1_pct = raw_y0_pct + boxHeightPct;

      // Convert to SnapRect and apply magnetic snapping
      const activeSnapRect = toSnapRect(dragBoxState.id, {
        x0_pct: raw_x0_pct,
        y0_pct: raw_y0_pct,
        x1_pct: raw_x1_pct,
        y1_pct: raw_y1_pct,
      }, rect.width, rect.height);

      const otherSnapRects = currentMappings
        .filter((m) => m.id !== dragBoxState.id)
        .map((m) => {
          const m_x0 = m.box_pct?.x0_pct ?? (m.box.x0 / page.page_width_pts);
          const m_y0 = m.box_pct?.y0_pct ?? (m.box.y0 / page.page_height_pts);
          const m_x1 = m.box_pct?.x1_pct ?? (m.box.x1 / page.page_width_pts);
          const m_y1 = m.box_pct?.y1_pct ?? (m.box.y1 / page.page_height_pts);
          return toSnapRect(m.id, { x0_pct: m_x0, y0_pct: m_y0, x1_pct: m_x1, y1_pct: m_y1 }, rect.width, rect.height);
        });

      const snapResult = calculateSnapping(
        activeSnapRect,
        otherSnapRects,
        { width: rect.width, height: rect.height },
        7
      );

      setActiveGuides(snapResult.guides);
      setActiveSpacings(snapResult.spacings);

      const final_x0_pct = Math.max(0, Math.min(1 - boxWidthPct, snapResult.snappedLeft / rect.width));
      const final_y0_pct = Math.max(0, Math.min(1 - boxHeightPct, snapResult.snappedTop / rect.height));
      const final_x1_pct = final_x0_pct + boxWidthPct;
      const final_y1_pct = final_y0_pct + boxHeightPct;

      const newBoxPct: BoxPct = {
        x0_pct: final_x0_pct,
        y0_pct: final_y0_pct,
        x1_pct: final_x1_pct,
        y1_pct: final_y1_pct,
      };

      const newBox: BoxCoords = {
        x0: final_x0_pct * page.page_width_pts,
        y0: final_y0_pct * page.page_height_pts,
        x1: final_x1_pct * page.page_width_pts,
        y1: final_y1_pct * page.page_height_pts,
      };

      onUpdateMapping(dragBoxState.id, newBox, newBoxPct);
      return;
    }

    // 3. Handle drawing new box
    if (!drawing) return;
    const coords = getPointerCoords(e);
    setDrawing((prev) => prev ? { ...prev, currentX: coords.x, currentY: coords.y } : null);
  };

  const handleMouseUp = () => {
    if (dragBoxState) {
      setDragBoxState(null);
      setActiveGuides([]);
      setActiveSpacings([]);
      return;
    }
    if (resizeBoxState) {
      setResizeBoxState(null);
      setActiveGuides([]);
      setActiveSpacings([]);
      return;
    }

    if (!drawing || (!selectedField && !activeImage) || !imageRef.current) {
      setDrawing(null);
      return;
    }

    const rect = imageRef.current.getBoundingClientRect();
    const imgWidth = rect.width;
    const imgHeight = rect.height;

    const minX = Math.min(drawing.startX, drawing.currentX);
    const maxX = Math.max(drawing.startX, drawing.currentX);
    const minY = Math.min(drawing.startY, drawing.currentY);
    const maxY = Math.max(drawing.startY, drawing.currentY);

    const widthPx = maxX - minX;
    const heightPx = maxY - minY;

    // Allow even small or narrow boxes (e.g. checkboxes, tight fields)
    if (widthPx > 3 && heightPx > 3) {
      const x0_pct = minX / imgWidth;
      const x1_pct = maxX / imgWidth;
      const y0_pct = minY / imgHeight;
      const y1_pct = maxY / imgHeight;

      const x0 = x0_pct * page.page_width_pts;
      const x1 = x1_pct * page.page_width_pts;
      const y0 = y0_pct * page.page_height_pts;
      const y1 = y1_pct * page.page_height_pts;

      const isFreeText = selectedField === 'texto_libre';
      if (activeImage) {
        onAddBox(
          { x0, y0, x1, y1 },
          { x0_pct, y0_pct, x1_pct, y1_pct },
          {
            item_type: 'image',
            image_base64: activeImage.base64,
          }
        );
      } else if (isFreeText) {
        onAddBox(
          { x0, y0, x1, y1 },
          { x0_pct, y0_pct, x1_pct, y1_pct },
          {
            ...currentStyle,
            item_type: 'text',
            custom_text: 'Nuevo texto',
          }
        );
      } else {
        onAddBox(
          { x0, y0, x1, y1 },
          { x0_pct, y0_pct, x1_pct, y1_pct },
          {
            ...currentStyle,
            item_type: 'text',
          }
        );
      }
    }

    setDrawing(null);
  };

  const formatLabel = (key: string) => {
    return key
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const isDrawingMode = !!(selectedField || activeImage);

  return (
    <div className="canvas-wrapper">
      {/* Canvas Header info & Zoom */}
      <div className="canvas-status-bar">
        {activeImage ? (
          <div className="active-field-indicator image-indicator">
            <ImageIcon size={15} className="animate-pulse" />
            <span>Dibujando área para: <strong>{activeImage.filename}</strong></span>
          </div>
        ) : selectedField ? (
          <div className={`active-field-indicator ${selectedField === 'texto_libre' ? 'text-mode-indicator' : ''}`}>
            <Crosshair size={14} className="animate-pulse" />
            <span>Dibujando: <strong>{selectedField === 'texto_libre' ? 'Texto Libre / Personalizado' : formatLabel(selectedField)}</strong></span>
          </div>
        ) : (
          <div className="active-field-indicator idle">
            <span>✨ Guías Magnéticas activas: Arrastra o redimensiona para alinear con precisión</span>
          </div>
        )}

        <div className="zoom-controls">
          <button 
            className="btn-zoom" 
            onClick={() => setZoomLevel(Math.max(50, zoomLevel - 15))}
            title="Reducir zoom"
          >
            <ZoomOut size={15} />
          </button>
          <span className="zoom-value">{zoomLevel}%</span>
          <button 
            className="btn-zoom" 
            onClick={() => setZoomLevel(Math.min(200, zoomLevel + 15))}
            title="Aumentar zoom"
          >
            <ZoomIn size={15} />
          </button>
          <button 
            className="btn-zoom" 
            onClick={() => setZoomLevel(100)}
            title="Restablecer tamaño"
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>

      {/* PDF Viewport */}
      <div className="pdf-viewport">
        <div 
          className={`pdf-sheet ${isDrawingMode ? 'is-drawing-mode' : ''} ${dragBoxState ? 'is-dragging-box' : ''} ${resizeBoxState ? 'is-resizing-box' : ''}`}
          style={{ width: `${zoomLevel}%` }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onContextMenu={(e) => e.preventDefault()}
        >
          {/* Base Page Image */}
          <img 
            ref={imageRef}
            src={page.image_base64} 
            alt={`Página ${page.page_num + 1}`}
            className="pdf-page-image"
            draggable={false}
          />

          {/* Active Drawing Box */}
          {drawing && (
            <div 
              className={`drawing-box-preview ${activeImage ? 'drawing-image-box' : ''}`}
              style={{
                left: `${Math.min(drawing.startX, drawing.currentX)}px`,
                top: `${Math.min(drawing.startY, drawing.currentY)}px`,
                width: `${Math.abs(drawing.currentX - drawing.startX)}px`,
                height: `${Math.abs(drawing.currentY - drawing.startY)}px`,
              }}
            >
              {activeImage && (
                <img 
                  src={activeImage.base64} 
                  alt="Preview" 
                  className="drawing-image-img" 
                />
              )}
              {!activeImage && Math.abs(drawing.currentY - drawing.startY) > 14 && (
                <span 
                  className="box-preview-value"
                  style={{
                    fontFamily: currentStyle.font_family || 'Arial',
                    fontWeight: currentStyle.bold ? 700 : 500,
                    color: currentStyle.color || '#000000',
                  }}
                >
                  {selectedField === 'texto_libre' ? 'Texto' : String(companyData[selectedField || ''] || '')}
                </span>
              )}
            </div>
          )}

          {/* Smart Guides & Distance Markers Overlay */}
          <SmartGuidesOverlay 
            guides={activeGuides}
            spacings={activeSpacings}
            width={imageRef.current?.clientWidth || 800}
            height={imageRef.current?.clientHeight || 1100}
          />

          {/* Existing Mapped Rectangles */}
          {currentMappings.map((item) => {
            const isBeingDragged = dragBoxState?.id === item.id;
            const isSelected = selectedBoxId === item.id;
            const isImage = item.style?.item_type === 'image';

            const x0_pct = item.box_pct?.x0_pct ?? (item.box.x0 / page.page_width_pts);
            const y0_pct = item.box_pct?.y0_pct ?? (item.box.y0 / page.page_height_pts);
            const x1_pct = item.box_pct?.x1_pct ?? (item.box.x1 / page.page_width_pts);
            const y1_pct = item.box_pct?.y1_pct ?? (item.box.y1 / page.page_height_pts);

            const leftPct = x0_pct * 100;
            const topPct = y0_pct * 100;
            const widthPct = (x1_pct - x0_pct) * 100;
            const heightPct = (y1_pct - y0_pct) * 100;

            const hasCustomText = item.style?.custom_text != null && item.style.custom_text !== '';
            const companyVal = companyData[item.field_key];
            const hasCompanyVal = companyVal != null && companyVal !== '';
            
            const textVal = hasCustomText
              ? item.style!.custom_text!
              : (hasCompanyVal ? String(companyVal) : (item.label || formatLabel(item.field_key)));

            const fontFam = item.style?.font_family || 'Arial';
            const isBold = item.style?.bold ?? false;
            const textColor = item.style?.color || '#000000';
            const fontSize = item.style?.font_size ? `${item.style.font_size}pt` : '0.85rem';

            return (
              <div 
                key={item.id}
                className={`mapped-box-overlay ${isBeingDragged ? 'is-dragging' : ''} ${isSelected ? 'is-selected-active' : ''} ${isImage ? 'is-image-box' : ''}`}
                style={{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }}
                onMouseDown={(e) => handleBoxMouseDown(e, item)}
                onContextMenu={(e) => e.preventDefault()}
                title={`${formatLabel(item.field_key)} (Clic para seleccionar/redimensionar, arrastra para mover con guías inteligentes)`}
              >
                {/* Delete Button (Only X icon, no variable name) */}
                <button 
                  type="button"
                  className="box-delete-btn-solo"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteMapping(item.id);
                  }}
                  title={`Eliminar recuadro (${item.label || formatLabel(item.field_key)})`}
                >
                  <X size={11} />
                </button>

                {isImage && item.style?.image_base64 ? (
                  <img 
                    src={item.style.image_base64} 
                    alt="Estampado"
                    className="mapped-box-image"
                  />
                ) : (
                  (() => {
                    const textAlign = item.style?.align || ((textVal === 'X' || textVal === 'x') ? 'center' : 'left');
                    const justifyVal = textAlign === 'center' ? 'center' : (textAlign === 'right' ? 'flex-end' : 'flex-start');
                    return (
                      <div 
                        className={`box-value-text align-${textAlign}`}
                        style={{
                          fontFamily: fontFam,
                          fontWeight: isBold ? 700 : 500,
                          color: textColor,
                          fontSize: fontSize,
                          justifyContent: justifyVal,
                          textAlign: textAlign,
                        }}
                      >
                        {String(textVal)}
                      </div>
                    );
                  })()
                )}

                {/* 8 RESIZE HANDLES when selected */}
                {isSelected && !isBeingDragged && (
                  <>
                    <div 
                      className="canvas-resize-handle handle-nw" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'nw')}
                      title="Redimensionar Arriba-Izquierda"
                    />
                    <div 
                      className="canvas-resize-handle handle-ne" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'ne')}
                      title="Redimensionar Arriba-Derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-se" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'se')}
                      title="Redimensionar Abajo-Derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-sw" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'sw')}
                      title="Redimensionar Abajo-Izquierda"
                    />
                    <div 
                      className="canvas-resize-handle handle-n" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'n')}
                      title="Redimensionar Arriba"
                    />
                    <div 
                      className="canvas-resize-handle handle-s" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 's')}
                      title="Redimensionar Abajo"
                    />
                    <div 
                      className="canvas-resize-handle handle-e" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'e')}
                      title="Redimensionar Derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-w" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'w')}
                      title="Redimensionar Izquierda"
                    />
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default PDFCanvas;

import React, { useState, useRef, useEffect } from 'react';
import type { PDFPage, MappingItem, CompanyData, BoxCoords, BoxPct, ItemStyle } from '../types';
import { X, ZoomIn, ZoomOut, Maximize2, Crosshair, Move, Image as ImageIcon } from 'lucide-react';

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
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [drawing, setDrawing] = useState<DrawingRect | null>(null);
  const [dragBoxState, setDragBoxState] = useState<DragBoxState | null>(null);
  const [resizeBoxState, setResizeBoxState] = useState<ResizeBoxState | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(100);

  // Global mouse up for smooth dragging and resizing release
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (dragBoxState) setDragBoxState(null);
      if (resizeBoxState) setResizeBoxState(null);
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
    
    // Deselect if clicking on empty space
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
    // 1. Handle resizing box
    if (resizeBoxState && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const deltaX = (e.clientX - resizeBoxState.startClientX) / rect.width;
      const deltaY = (e.clientY - resizeBoxState.startClientY) / rect.height;

      let { x0_pct, y0_pct, x1_pct, y1_pct } = resizeBoxState.initialBoxPct;

      if (resizeBoxState.dir.includes('e')) {
        x1_pct = Math.max(x0_pct + 0.015, Math.min(1.0, resizeBoxState.initialBoxPct.x1_pct + deltaX));
      } else if (resizeBoxState.dir.includes('w')) {
        x0_pct = Math.min(x1_pct - 0.015, Math.max(0.0, resizeBoxState.initialBoxPct.x0_pct + deltaX));
      }

      if (resizeBoxState.dir.includes('s')) {
        y1_pct = Math.max(y0_pct + 0.01, Math.min(1.0, resizeBoxState.initialBoxPct.y1_pct + deltaY));
      } else if (resizeBoxState.dir.includes('n')) {
        y0_pct = Math.min(y1_pct - 0.01, Math.max(0.0, resizeBoxState.initialBoxPct.y0_pct + deltaY));
      }

      const newBoxPct: BoxPct = { x0_pct, y0_pct, x1_pct, y1_pct };
      const newBox: BoxCoords = {
        x0: x0_pct * page.page_width_pts,
        y0: y0_pct * page.page_height_pts,
        x1: x1_pct * page.page_width_pts,
        y1: y1_pct * page.page_height_pts,
      };

      onUpdateMapping(resizeBoxState.id, newBox, newBoxPct);
      return;
    }

    // 2. Handle dragging box position
    if (dragBoxState && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const deltaX = (e.clientX - dragBoxState.startClientX) / rect.width;
      const deltaY = (e.clientY - dragBoxState.startClientY) / rect.height;

      const initPct = dragBoxState.initialBoxPct;
      const boxWidthPct = initPct.x1_pct - initPct.x0_pct;
      const boxHeightPct = initPct.y1_pct - initPct.y0_pct;

      let new_x0_pct = Math.max(0, Math.min(1 - boxWidthPct, initPct.x0_pct + deltaX));
      let new_y0_pct = Math.max(0, Math.min(1 - boxHeightPct, initPct.y0_pct + deltaY));
      let new_x1_pct = new_x0_pct + boxWidthPct;
      let new_y1_pct = new_y0_pct + boxHeightPct;

      const newBoxPct: BoxPct = {
        x0_pct: new_x0_pct,
        y0_pct: new_y0_pct,
        x1_pct: new_x1_pct,
        y1_pct: new_y1_pct,
      };

      const newBox: BoxCoords = {
        x0: new_x0_pct * page.page_width_pts,
        y0: new_y0_pct * page.page_height_pts,
        x1: new_x1_pct * page.page_width_pts,
        y1: new_y1_pct * page.page_height_pts,
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
      return;
    }
    if (resizeBoxState) {
      setResizeBoxState(null);
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

    // Ignore tiny accidental clicks (less than 8px)
    if (widthPx > 8 && heightPx > 6) {
      const x0_pct = minX / imgWidth;
      const x1_pct = maxX / imgWidth;
      const y0_pct = minY / imgHeight;
      const y1_pct = maxY / imgHeight;

      const x0 = x0_pct * page.page_width_pts;
      const x1 = x1_pct * page.page_width_pts;
      const y0 = y0_pct * page.page_height_pts;
      const y1 = y1_pct * page.page_height_pts;

      if (activeImage) {
        onAddBox(
          { x0, y0, x1, y1 },
          { x0_pct, y0_pct, x1_pct, y1_pct },
          {
            item_type: 'image',
            image_base64: activeImage.base64,
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
    <div className="pdf-canvas-container" ref={containerRef}>
      {/* Canvas Toolbar */}
      <div className="canvas-floating-bar">
        {activeImage ? (
          <div className="active-field-indicator image-indicator">
            <ImageIcon size={15} className="animate-pulse" />
            <span>Dibujando área para: <strong>{activeImage.filename}</strong></span>
          </div>
        ) : selectedField ? (
          <div className="active-field-indicator">
            <Crosshair size={14} className="animate-pulse" />
            <span>Dibujando: <strong>{formatLabel(selectedField)}</strong></span>
          </div>
        ) : (
          <div className="active-field-indicator idle">
            <span>Selecciona un dato o usa la barra superior para cambiar fuente, color, tamaño o firma</span>
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
              <span className="box-preview-label">
                {activeImage ? activeImage.filename : formatLabel(selectedField || '')}
              </span>
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
                  {String(companyData[selectedField || ''] || '')}
                </span>
              )}
            </div>
          )}

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

            const textVal = item.style?.custom_text !== undefined
              ? item.style.custom_text 
              : (companyData[item.field_key] || '');

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
                title={`${formatLabel(item.field_key)} (Clic para seleccionar/redimensionar, arrastra para mover)`}
              >
                <div className="box-header-badge">
                  <Move size={10} className="move-icon" />
                  <span className="box-key-title">
                    {isImage ? (item.label || 'Firma / Imagen') : (item.label || formatLabel(item.field_key))}
                  </span>
                  <button 
                    className="box-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteMapping(item.id);
                    }}
                    title="Eliminar este recuadro"
                  >
                    <X size={11} />
                  </button>
                </div>

                {isImage && item.style?.image_base64 ? (
                  <img 
                    src={item.style.image_base64} 
                    alt="Estampado"
                    className="mapped-box-image"
                  />
                ) : (
                  <div 
                    className="box-value-text"
                    style={{
                      fontFamily: fontFam,
                      fontWeight: isBold ? 700 : 500,
                      color: textColor,
                      fontSize: fontSize,
                    }}
                  >
                    {String(textVal)}
                  </div>
                )}

                {/* 8 RESIZE HANDLES when selected */}
                {isSelected && !isBeingDragged && (
                  <>
                    <div 
                      className="canvas-resize-handle handle-nw" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'nw')} 
                      title="Redimensionar esquina superior izquierda"
                    />
                    <div 
                      className="canvas-resize-handle handle-ne" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'ne')} 
                      title="Redimensionar esquina superior derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-se" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'se')} 
                      title="Redimensionar esquina inferior derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-sw" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'sw')} 
                      title="Redimensionar esquina inferior izquierda"
                    />
                    <div 
                      className="canvas-resize-handle handle-n" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'n')} 
                      title="Estirar arriba"
                    />
                    <div 
                      className="canvas-resize-handle handle-s" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 's')} 
                      title="Estirar abajo"
                    />
                    <div 
                      className="canvas-resize-handle handle-e" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'e')} 
                      title="Estirar derecha"
                    />
                    <div 
                      className="canvas-resize-handle handle-w" 
                      onMouseDown={(e) => handleResizeMouseDown(e, item, 'w')} 
                      title="Estirar izquierda"
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

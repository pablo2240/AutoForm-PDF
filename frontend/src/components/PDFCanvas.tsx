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
  const [zoomLevel, setZoomLevel] = useState<number>(100);

  // Global mouse up for smooth dragging release
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (dragBoxState) {
        setDragBoxState(null);
      }
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [dragBoxState]);

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
    // Left click
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

  const handleBoxMouseDown = (e: React.MouseEvent<HTMLDivElement>, item: MappingItem) => {
    // Select box on click
    onSelectBox(item.id);

    // Right click (e.button === 2) OR Left Click when not in drawing mode initiates dragging
    if (e.button === 2 || (!selectedField && !activeImage && e.button === 0)) {
      e.preventDefault();
      e.stopPropagation();

      const x0_pct = item.box_pct?.x0_pct ?? (item.box.x0 / page.page_width_pts);
      const y0_pct = item.box_pct?.y0_pct ?? (item.box.y0 / page.page_height_pts);
      const x1_pct = item.box_pct?.x1_pct ?? (item.box.x1 / page.page_width_pts);
      const y1_pct = item.box_pct?.y1_pct ?? (item.box.y1 / page.page_height_pts);

      const initialBoxPct: BoxPct = { x0_pct, y0_pct, x1_pct, y1_pct };

      setDragBoxState({
        id: item.id,
        startClientX: e.clientX,
        startClientY: e.clientY,
        initialBox: { ...item.box },
        initialBoxPct,
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    // Handle dragging/repositioning existing box
    if (dragBoxState && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const dx_px = e.clientX - dragBoxState.startClientX;
      const dy_px = e.clientY - dragBoxState.startClientY;

      const dx_pct = dx_px / rect.width;
      const dy_pct = dy_px / rect.height;

      const width_pct = dragBoxState.initialBoxPct.x1_pct - dragBoxState.initialBoxPct.x0_pct;
      const height_pct = dragBoxState.initialBoxPct.y1_pct - dragBoxState.initialBoxPct.y0_pct;

      const new_x0_pct = Math.max(0, Math.min(1 - width_pct, dragBoxState.initialBoxPct.x0_pct + dx_pct));
      const new_y0_pct = Math.max(0, Math.min(1 - height_pct, dragBoxState.initialBoxPct.y0_pct + dy_pct));
      const new_x1_pct = new_x0_pct + width_pct;
      const new_y1_pct = new_y0_pct + height_pct;

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

    // Handle drawing new box
    if (!drawing) return;
    const coords = getPointerCoords(e);
    setDrawing((prev) => prev ? { ...prev, currentX: coords.x, currentY: coords.y } : null);
  };

  const handleMouseUp = () => {
    if (dragBoxState) {
      setDragBoxState(null);
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
            <span>Selecciona un dato o usa la barra superior para cambiar fuente, color y tamaño</span>
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
          className={`pdf-sheet ${isDrawingMode ? 'is-drawing-mode' : ''} ${dragBoxState ? 'is-dragging-box' : ''}`}
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
                title={`${formatLabel(item.field_key)} (Clic para editar, Clic derecho para mover)`}
              >
                <div className="box-header-badge">
                  <Move size={10} className="move-icon" />
                  <span className="box-key-title">
                    {isImage ? 'Imagen/Firma' : (item.label || formatLabel(item.field_key))}
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
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

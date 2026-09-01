import React, { useState, useRef, useEffect, useCallback } from 'react';
import type { GlobalSignature } from '../../types';
import { 
  PenTool, 
  MoreVertical, 
  UploadCloud, 
  Save, 
  Trash2, 
  ChevronDown, 
  ChevronUp, 
  Image as ImageIcon, 
  Move, 
  Check, 
  RotateCcw, 
  Link as LinkIcon,
  Brush,
  Eraser,
  X
} from 'lucide-react';
import { UrlImageModal } from '../UrlImageModal';

interface SignatureSectionProps {
  signature: GlobalSignature | null;
  onSaveSignature: (sig: GlobalSignature | null) => void;
}

type ResizeDirection = 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w';

export const SignatureSection: React.FC<SignatureSectionProps> = ({
  signature,
  onSaveSignature,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [isDrawingMode, setIsDrawingMode] = useState<boolean>(false);
  const [isDraggingFile, setIsDraggingFile] = useState<boolean>(false);
  const [isUrlModalOpen, setIsUrlModalOpen] = useState<boolean>(false);
  
  // Position & Dimensions of signature object
  const [position, setPosition] = useState<{ x: number; y: number }>(() => 
    signature?.position || { x: 0, y: 0 }
  );
  const [size, setSize] = useState<{ width: number; height: number }>(() =>
    signature?.size || { width: 160, height: 70 }
  );

  // Position drag state
  const [isDraggingPosition, setIsDraggingPosition] = useState<boolean>(false);
  
  // Resize drag state
  const [resizingDir, setResizingDir] = useState<ResizeDirection | null>(null);
  const dragStartRef = useRef<{
    startX: number;
    startY: number;
    initX: number;
    initY: number;
    initW: number;
    initH: number;
  }>({
    startX: 0,
    startY: 0,
    initX: 0,
    initY: 0,
    initW: 160,
    initH: 70,
  });

  // Freehand Drawing Canvas State
  const drawCanvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawingStroke, setIsDrawingStroke] = useState<boolean>(false);
  const [strokeColor, setStrokeColor] = useState<string>('#000000');
  const [strokeWidth, setStrokeWidth] = useState<number>(3);
  const [hasDrawnStrokes, setHasDrawnStrokes] = useState<boolean>(false);

  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'info' } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync state with signature prop
  useEffect(() => {
    if (signature) {
      if (signature.position) setPosition(signature.position);
      if (signature.size) setSize(signature.size);
    } else {
      setPosition({ x: 0, y: 0 });
      setSize({ width: 160, height: 70 });
    }
  }, [signature]);

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  const showToast = (text: string, type: 'success' | 'info' = 'success') => {
    setNotification({ text, type });
    setTimeout(() => setNotification(null), 3000);
  };

  // ----------------- FREEHAND DRAWING PAD -----------------
  const startDrawingStroke = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = drawCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    setIsDrawingStroke(true);
    setHasDrawnStrokes(true);

    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    const x = clientX - rect.left;
    const y = clientY - rect.top;

    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = strokeWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
  };

  const drawStroke = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawingStroke) return;
    const canvas = drawCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    const x = clientX - rect.left;
    const y = clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawingStroke = () => {
    setIsDrawingStroke(false);
  };

  const clearDrawingCanvas = () => {
    const canvas = drawCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawnStrokes(false);
  };

  const handleSaveDrawnSignature = () => {
    const canvas = drawCanvasRef.current;
    if (!canvas || !hasDrawnStrokes) {
      showToast('Por favor dibuja tu firma antes de guardar.', 'info');
      return;
    }

    // Export canvas as PNG base64
    const base64 = canvas.toDataURL('image/png');
    const newSig: GlobalSignature = {
      base64,
      filename: `firma_dibujada_${Date.now().toString().slice(-4)}.png`,
      position: { x: 0, y: 0 },
      size: { width: 170, height: 75 },
      updatedAt: new Date().toISOString(),
    };

    setPosition({ x: 0, y: 0 });
    setSize({ width: 170, height: 75 });
    onSaveSignature(newSig);
    setIsDrawingMode(false);
    showToast('¡Firma a mano alzada guardada exitosamente!');
  };

  // ----------------- FILE UPLOAD / DROP -----------------
  const processImageFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      showToast('Por favor selecciona un archivo de imagen válido (PNG, JPG, WEBP, SVG).', 'info');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const base64 = e.target?.result as string;
      const newSig: GlobalSignature = {
        base64,
        filename: file.name,
        position: { x: 0, y: 0 },
        size: { width: 170, height: 75 },
        updatedAt: new Date().toISOString(),
      };
      setPosition({ x: 0, y: 0 });
      setSize({ width: 170, height: 75 });
      onSaveSignature(newSig);
      showToast(`Firma "${file.name}" cargada correctamente`);
    };
    reader.readAsDataURL(file);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processImageFile(file);
    }
    if (e.target) e.target.value = '';
    setIsMenuOpen(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      processImageFile(file);
    }
  };

  // ----------------- DRAG-TO-MOVE POSITION -----------------
  const handleMouseDownPosition = (e: React.MouseEvent) => {
    if (!signature || resizingDir) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingPosition(true);
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initX: position.x,
      initY: position.y,
      initW: size.width,
      initH: size.height,
    };
  };

  // ----------------- RESIZE HANDLERS (8 POINTS) -----------------
  const handleMouseDownResize = (dir: ResizeDirection, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setResizingDir(dir);
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initX: position.x,
      initY: position.y,
      initW: size.width,
      initH: size.height,
    };
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDraggingPosition) {
      const deltaX = e.clientX - dragStartRef.current.startX;
      const deltaY = e.clientY - dragStartRef.current.startY;
      const maxOffset = 140;
      const newX = Math.max(-maxOffset, Math.min(maxOffset, dragStartRef.current.initX + deltaX));
      const newY = Math.max(-maxOffset, Math.min(maxOffset, dragStartRef.current.initY + deltaY));
      setPosition({ x: newX, y: newY });
    } else if (resizingDir) {
      const deltaX = e.clientX - dragStartRef.current.startX;
      const deltaY = e.clientY - dragStartRef.current.startY;
      let newW = dragStartRef.current.initW;
      let newH = dragStartRef.current.initH;
      let newX = dragStartRef.current.initX;
      let newY = dragStartRef.current.initY;

      // Handle horizontal resize
      if (resizingDir.includes('e')) {
        newW = Math.max(50, Math.min(320, dragStartRef.current.initW + deltaX));
      } else if (resizingDir.includes('w')) {
        const potentialW = Math.max(50, Math.min(320, dragStartRef.current.initW - deltaX));
        newW = potentialW;
        newX = dragStartRef.current.initX + (dragStartRef.current.initW - potentialW) / 2;
      }

      // Handle vertical resize
      if (resizingDir.includes('s')) {
        newH = Math.max(25, Math.min(180, dragStartRef.current.initH + deltaY));
      } else if (resizingDir.includes('n')) {
        const potentialH = Math.max(25, Math.min(180, dragStartRef.current.initH - deltaY));
        newH = potentialH;
        newY = dragStartRef.current.initY + (dragStartRef.current.initH - potentialH) / 2;
      }

      setSize({ width: Math.round(newW), height: Math.round(newH) });
      setPosition({ x: Math.round(newX), y: Math.round(newY) });
    }
  }, [isDraggingPosition, resizingDir]);

  const handleMouseUp = useCallback(() => {
    if (isDraggingPosition || resizingDir) {
      setIsDraggingPosition(false);
      setResizingDir(null);
      if (signature) {
        onSaveSignature({
          ...signature,
          position,
          size,
          updatedAt: new Date().toISOString(),
        });
      }
    }
  }, [isDraggingPosition, resizingDir, signature, position, size, onSaveSignature]);

  useEffect(() => {
    if (isDraggingPosition || resizingDir) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDraggingPosition, resizingDir, handleMouseMove, handleMouseUp]);

  // ----------------- MENU & ACTIONS -----------------
  const handleSaveCurrentSignature = () => {
    if (!signature) {
      showToast('No hay ninguna firma cargada para guardar.', 'info');
      return;
    }
    onSaveSignature({
      ...signature,
      position,
      size,
      updatedAt: new Date().toISOString(),
    });
    setIsMenuOpen(false);
    showToast('Firma guardada en el estado del sistema');
  };

  const handleClearSignature = () => {
    onSaveSignature(null);
    setPosition({ x: 0, y: 0 });
    setSize({ width: 160, height: 70 });
    setIsMenuOpen(false);
    showToast('Firma eliminada', 'info');
  };

  const handleResetPositionAndSize = () => {
    setPosition({ x: 0, y: 0 });
    setSize({ width: 160, height: 70 });
    if (signature) {
      onSaveSignature({
        ...signature,
        position: { x: 0, y: 0 },
        size: { width: 160, height: 70 },
      });
    }
    showToast('Posición y tamaño restablecidos', 'info');
  };

  const handleOpenUrlModal = () => {
    setIsUrlModalOpen(true);
    setIsMenuOpen(false);
  };

  const handleConfirmUrl = (url: string) => {
    const newSig: GlobalSignature = {
      base64: url.trim(),
      filename: 'firma_remota.png',
      position: { x: 0, y: 0 },
      size: { width: 170, height: 75 },
      updatedAt: new Date().toISOString(),
    };
    setPosition({ x: 0, y: 0 });
    setSize({ width: 170, height: 75 });
    onSaveSignature(newSig);
    showToast('Firma cargada exitosamente desde URL');
  };

  return (
    <div className={`accordion-card signature-card ${isOpen ? 'expanded' : 'collapsed'}`}>
      {/* Hidden File Input */}
      <input 
        type="file" 
        ref={fileInputRef} 
        accept="image/*" 
        style={{ display: 'none' }} 
        onChange={handleFileInputChange} 
      />

      {/* Accordion Header */}
      <div 
        className="accordion-header signature-header"
        onClick={() => setIsOpen(prev => !prev)}
        role="button"
        tabIndex={0}
      >
        <div className="accordion-title-group">
          <div className="header-icon-box signature">
            <PenTool size={18} />
          </div>
          <div className="title-text-col">
            <h4 className="accordion-main-title">✍️ Firma</h4>
            <span className="accordion-sub-meta">
              {signature ? `Firma interactiva (${size.width}x${size.height}px)` : 'Sin firma cargada'}
            </span>
          </div>
        </div>

        <div className="accordion-header-actions" onClick={(e) => e.stopPropagation()}>
          {/* Status Badge */}
          <span className={`sig-status-badge ${signature ? 'active' : 'empty'}`}>
            {signature ? <Check size={11} /> : null}
            {signature ? 'Activa' : 'Pendiente'}
          </span>

          {/* Three-dots Menu Button */}
          <div className="sig-menu-container" ref={menuRef}>
            <button
              type="button"
              className={`btn-three-dots ${isMenuOpen ? 'active' : ''}`}
              onClick={() => setIsMenuOpen(prev => !prev)}
              title="Opciones de configuración de firma"
            >
              <MoreVertical size={16} />
            </button>

            {/* Dropdown Menu */}
            {isMenuOpen && (
              <div className="signature-dropdown-menu">
                <div className="dropdown-menu-header">
                  <span>Configuración de Firma</span>
                </div>

                <button
                  type="button"
                  className="dropdown-menu-item"
                  onClick={() => {
                    setIsDrawingMode(true);
                    setIsMenuOpen(false);
                  }}
                >
                  <Brush size={15} className="item-icon success" />
                  <span>Dibujar Firma a Mano Alzada</span>
                </button>
                
                <button
                  type="button"
                  className="dropdown-menu-item"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <UploadCloud size={15} className="item-icon" />
                  <span>Cargar Imagen de Firma</span>
                </button>

                <button
                  type="button"
                  className="dropdown-menu-item"
                  onClick={handleOpenUrlModal}
                >
                  <LinkIcon size={15} className="item-icon" />
                  <span>Cargar desde URL</span>
                </button>

                {signature && (
                  <>
                    <button
                      type="button"
                      className="dropdown-menu-item"
                      onClick={handleSaveCurrentSignature}
                    >
                      <Save size={15} className="item-icon success" />
                      <span>Guardar Firma</span>
                    </button>

                    <button
                      type="button"
                      className="dropdown-menu-item"
                      onClick={handleResetPositionAndSize}
                    >
                      <RotateCcw size={15} className="item-icon" />
                      <span>Restablecer Tamaño y Centro</span>
                    </button>

                    <div className="dropdown-divider"></div>

                    <button
                      type="button"
                      className="dropdown-menu-item danger"
                      onClick={handleClearSignature}
                    >
                      <Trash2 size={15} className="item-icon" />
                      <span>Limpiar / Restablecer Firma</span>
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="chevron-pill" onClick={() => setIsOpen(prev => !prev)}>
            {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>
      </div>

      {/* Accordion Body */}
      {isOpen && (
        <div className="accordion-body signature-body">
          {notification && (
            <div className={`signature-toast-mini ${notification.type}`}>
              <span>{notification.text}</span>
            </div>
          )}

          {/* VIEW MODE 1: FREEHAND DRAWING PAD */}
          {isDrawingMode ? (
            <div className="signature-drawing-pad-wrapper">
              <div className="pad-toolbar">
                <div className="pad-tools-left">
                  <span className="pad-label"><Brush size={14} /> Dibuja tu firma con el ratón:</span>
                  <div className="color-picker-mini">
                    <button 
                      type="button" 
                      className={`dot-color ${strokeColor === '#000000' ? 'active' : ''}`}
                      style={{ backgroundColor: '#000000' }}
                      onClick={() => setStrokeColor('#000000')}
                      title="Negro"
                    />
                    <button 
                      type="button" 
                      className={`dot-color ${strokeColor === '#002060' ? 'active' : ''}`}
                      style={{ backgroundColor: '#002060' }}
                      onClick={() => setStrokeColor('#002060')}
                      title="Azul Oscuro"
                    />
                    <button 
                      type="button" 
                      className={`dot-color ${strokeColor === '#1d4ed8' ? 'active' : ''}`}
                      style={{ backgroundColor: '#1d4ed8' }}
                      onClick={() => setStrokeColor('#1d4ed8')}
                      title="Azul Rey"
                    />
                  </div>
                  <select 
                    value={strokeWidth} 
                    onChange={(e) => setStrokeWidth(Number(e.target.value))}
                    className="pad-select-stroke"
                  >
                    <option value={2}>Grosor Fino</option>
                    <option value={3}>Grosor Normal</option>
                    <option value={5}>Grosor Grueso</option>
                  </select>
                </div>
                <div className="pad-tools-right">
                  <button 
                    type="button" 
                    className="btn-pad-tool" 
                    onClick={clearDrawingCanvas}
                    title="Limpiar trazo"
                  >
                    <Eraser size={14} />
                    <span>Limpiar</span>
                  </button>
                  <button 
                    type="button" 
                    className="btn-pad-tool cancel" 
                    onClick={() => setIsDrawingMode(false)}
                  >
                    <X size={14} />
                    <span>Cancelar</span>
                  </button>
                </div>
              </div>

              {/* HTML5 Canvas Element */}
              <div className="pad-canvas-container">
                <canvas
                  ref={drawCanvasRef}
                  width={420}
                  height={150}
                  className="signature-draw-canvas"
                  onMouseDown={startDrawingStroke}
                  onMouseMove={drawStroke}
                  onMouseUp={stopDrawingStroke}
                  onMouseLeave={stopDrawingStroke}
                  onTouchStart={startDrawingStroke}
                  onTouchMove={drawStroke}
                  onTouchEnd={stopDrawingStroke}
                />
              </div>

              <div className="pad-footer">
                <button
                  type="button"
                  className="btn-save-drawing"
                  onClick={handleSaveDrawnSignature}
                  disabled={!hasDrawnStrokes}
                >
                  <Save size={15} />
                  <span>Guardar Dibujo</span>
                </button>
              </div>
            </div>
          ) : (
            /* VIEW MODE 2: INTERACTIVE PREVIEW & RESIZABLE OBJECT */
            <div
              ref={containerRef}
              className={`signature-interactive-stage ${isDraggingFile ? 'is-file-over' : ''} ${signature ? 'has-image' : 'is-empty'}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {signature ? (
                /* Interactive Resizable Signature Object with 8 Handles */
                <div 
                  className={`signature-resizable-box ${isDraggingPosition ? 'is-dragging' : ''} ${resizingDir ? 'is-resizing' : ''}`}
                  style={{
                    width: `${size.width}px`,
                    height: `${size.height}px`,
                    transform: `translate(${position.x}px, ${position.y}px)`,
                  }}
                  onMouseDown={handleMouseDownPosition}
                  title="Arrastra para mover la firma, o estira desde las esquinas/bordes para redimensionarla"
                >
                  {/* Top Drag Indicator */}
                  <div className="sig-drag-indicator">
                    <Move size={11} />
                    <span>{size.width} × {size.height}px</span>
                  </div>

                  {/* Signature Image */}
                  <img 
                    src={signature.base64} 
                    alt="Firma Global" 
                    className="signature-preview-img-fluid" 
                    draggable={false} 
                  />

                  {/* 8 RESIZE HANDLERS */}
                  {/* Corner handles */}
                  <div 
                    className="resize-handle handle-nw" 
                    onMouseDown={(e) => handleMouseDownResize('nw', e)} 
                    title="Redimensionar esquina superior izquierda"
                  />
                  <div 
                    className="resize-handle handle-ne" 
                    onMouseDown={(e) => handleMouseDownResize('ne', e)} 
                    title="Redimensionar esquina superior derecha"
                  />
                  <div 
                    className="resize-handle handle-se" 
                    onMouseDown={(e) => handleMouseDownResize('se', e)} 
                    title="Redimensionar esquina inferior derecha"
                  />
                  <div 
                    className="resize-handle handle-sw" 
                    onMouseDown={(e) => handleMouseDownResize('sw', e)} 
                    title="Redimensionar esquina inferior izquierda"
                  />

                  {/* Edge handles */}
                  <div 
                    className="resize-handle handle-n" 
                    onMouseDown={(e) => handleMouseDownResize('n', e)} 
                    title="Estirar hacia arriba"
                  />
                  <div 
                    className="resize-handle handle-s" 
                    onMouseDown={(e) => handleMouseDownResize('s', e)} 
                    title="Estirar hacia abajo"
                  />
                  <div 
                    className="resize-handle handle-e" 
                    onMouseDown={(e) => handleMouseDownResize('e', e)} 
                    title="Estirar hacia la derecha"
                  />
                  <div 
                    className="resize-handle handle-w" 
                    onMouseDown={(e) => handleMouseDownResize('w', e)} 
                    title="Estirar hacia la izquierda"
                  />
                </div>
              ) : (
                /* Empty Dropzone Area with Direct Draw / Upload Options */
                <div 
                  className="signature-empty-dropzone"
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                >
                  <div className="dropzone-icon-circle">
                    <UploadCloud size={22} />
                  </div>
                  <p className="dropzone-prompt">
                    Arrastra aquí tu firma, dibújala o usa el menú (<strong>⋮</strong>)
                  </p>
                  <span className="dropzone-hint">Soporta dibujo a mano alzada, archivos PNG, JPG o SVG</span>
                  
                  <div className="dropzone-actions-row">
                    <button 
                      type="button" 
                      className="btn-select-file-mini primary-grad"
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsDrawingMode(true);
                      }}
                    >
                      <Brush size={13} />
                      <span>✍️ Dibujar Firma</span>
                    </button>
                    <button 
                      type="button" 
                      className="btn-select-file-mini"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                    >
                      <ImageIcon size={13} />
                      <span>Cargar Archivo</span>
                    </button>
                    <button 
                      type="button" 
                      className="btn-select-file-mini"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenUrlModal();
                      }}
                      title="Cargar firma mediante enlace web o URL directa"
                    >
                      <LinkIcon size={13} />
                      <span>Desde URL</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Footer details & quick actions */}
          {signature && !isDrawingMode && (
            <div className="signature-footer-actions">
              <span className="sig-file-info">
                📄 {signature.filename} • {size.width}×{size.height}px
              </span>
              <div className="sig-btn-row">
                <button
                  type="button"
                  className="btn-sig-action-outline"
                  onClick={() => setIsDrawingMode(true)}
                  title="Volver a dibujar a mano alzada"
                >
                  <Brush size={12} />
                  <span>Redibujar</span>
                </button>
                <button
                  type="button"
                  className="btn-sig-action-outline"
                  onClick={handleResetPositionAndSize}
                  title="Restablecer tamaño y posición original"
                >
                  <RotateCcw size={12} />
                  <span>Restablecer</span>
                </button>
                <button
                  type="button"
                  className="btn-sig-action-outline danger"
                  onClick={handleClearSignature}
                  title="Eliminar firma"
                >
                  <Trash2 size={12} />
                  <span>Eliminar</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* URL Image Modal with Brand Design */}
      <UrlImageModal
        isOpen={isUrlModalOpen}
        onClose={() => setIsUrlModalOpen(false)}
        onConfirm={handleConfirmUrl}
        title="Cargar Firma desde URL"
        subtitle="Ingresa el enlace web directo a la imagen de tu firma o estampado (PNG, JPG, SVG o WEBP)."
        confirmText="Cargar Firma"
      />
    </div>
  );
};

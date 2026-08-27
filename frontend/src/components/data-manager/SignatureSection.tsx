import React, { useState, useRef, useEffect } from 'react';
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
  Link as LinkIcon
} from 'lucide-react';

interface SignatureSectionProps {
  signature: GlobalSignature | null;
  onSaveSignature: (sig: GlobalSignature | null) => void;
}

export const SignatureSection: React.FC<SignatureSectionProps> = ({
  signature,
  onSaveSignature,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [isDraggingFile, setIsDraggingFile] = useState<boolean>(false);
  
  // Position drag state for image within canvas
  const [position, setPosition] = useState<{ x: number; y: number }>(() => 
    signature?.position || { x: 0, y: 0 }
  );
  const [isDraggingPosition, setIsDraggingPosition] = useState<boolean>(false);
  const dragStartRef = useRef<{ startX: number; startY: number; initX: number; initY: number }>({
    startX: 0,
    startY: 0,
    initX: 0,
    initY: 0,
  });

  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'info' } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Sync position when signature changes
  useEffect(() => {
    if (signature?.position) {
      setPosition(signature.position);
    } else {
      setPosition({ x: 0, y: 0 });
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

  // 1. Handle file upload (from input or drop)
  const processImageFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('Por favor selecciona un archivo de imagen válido (PNG, JPG, WEBP, SVG).');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const base64 = e.target?.result as string;
      const newSig: GlobalSignature = {
        base64,
        filename: file.name,
        position: { x: 0, y: 0 },
        updatedAt: new Date().toISOString(),
      };
      setPosition({ x: 0, y: 0 });
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

  // 2. Drag and drop files from OS
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

  // 3. Position Dragging (Drag to Move image inside canvas)
  const handleMouseDownPosition = (e: React.MouseEvent) => {
    if (!signature) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingPosition(true);
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initX: position.x,
      initY: position.y,
    };
  };

  const handleMouseMovePosition = (e: React.MouseEvent) => {
    if (!isDraggingPosition) return;
    const deltaX = e.clientX - dragStartRef.current.startX;
    const deltaY = e.clientY - dragStartRef.current.startY;
    
    // Constrain position within canvas limits
    const maxOffset = 120;
    const newX = Math.max(-maxOffset, Math.min(maxOffset, dragStartRef.current.initX + deltaX));
    const newY = Math.max(-maxOffset, Math.min(maxOffset, dragStartRef.current.initY + deltaY));
    
    setPosition({ x: newX, y: newY });
  };

  const handleMouseUpPosition = () => {
    if (isDraggingPosition && signature) {
      setIsDraggingPosition(false);
      onSaveSignature({
        ...signature,
        position,
      });
    }
  };

  // 4. Menu Actions
  const handleSaveCurrentSignature = () => {
    if (!signature) {
      alert('No hay ninguna firma cargada para guardar.');
      return;
    }
    onSaveSignature({
      ...signature,
      position,
      updatedAt: new Date().toISOString(),
    });
    setIsMenuOpen(false);
    showToast('Firma guardada en el estado del sistema');
  };

  const handleClearSignature = () => {
    if (window.confirm('¿Estás seguro de que deseas limpiar y restablecer la firma actual?')) {
      onSaveSignature(null);
      setPosition({ x: 0, y: 0 });
      setIsMenuOpen(false);
      showToast('Firma eliminada', 'info');
    }
  };

  const handleResetPosition = () => {
    setPosition({ x: 0, y: 0 });
    if (signature) {
      onSaveSignature({
        ...signature,
        position: { x: 0, y: 0 },
      });
    }
    showToast('Posición centrada', 'info');
  };

  const handleLoadFromUrl = () => {
    const url = window.prompt('Pega la URL directa de la imagen de la firma:');
    if (url && url.trim().startsWith('http')) {
      const newSig: GlobalSignature = {
        base64: url.trim(),
        filename: 'firma_remota.png',
        position: { x: 0, y: 0 },
        updatedAt: new Date().toISOString(),
      };
      setPosition({ x: 0, y: 0 });
      onSaveSignature(newSig);
      setIsMenuOpen(false);
      showToast('Firma cargada desde URL');
    }
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
              {signature ? `Firma cargada (${signature.filename})` : 'Sin firma cargada'}
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
                  onClick={() => fileInputRef.current?.click()}
                >
                  <UploadCloud size={15} className="item-icon" />
                  <span>Cargar Imagen de Firma</span>
                </button>

                <button
                  type="button"
                  className="dropdown-menu-item"
                  onClick={handleLoadFromUrl}
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
                      onClick={handleResetPosition}
                    >
                      <RotateCcw size={15} className="item-icon" />
                      <span>Centrar Posición</span>
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

          {/* Interactive Drag & Drop Area */}
          <div
            ref={canvasRef}
            className={`signature-interactive-stage ${isDraggingFile ? 'is-file-over' : ''} ${signature ? 'has-image' : 'is-empty'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onMouseMove={handleMouseMovePosition}
            onMouseUp={handleMouseUpPosition}
            onMouseLeave={handleMouseUpPosition}
          >
            {signature ? (
              /* Loaded Signature Container with Drag-to-Position */
              <div 
                className={`signature-draggable-item ${isDraggingPosition ? 'is-dragging' : ''}`}
                style={{
                  transform: `translate(${position.x}px, ${position.y}px)`,
                }}
                onMouseDown={handleMouseDownPosition}
                title="Haz clic y arrastra para ajustar la posición de la firma dentro del recuadro"
              >
                <div className="sig-drag-indicator">
                  <Move size={12} />
                  <span>Arrastrar para centrar</span>
                </div>
                <img 
                  src={signature.base64} 
                  alt="Firma Global" 
                  className="signature-preview-img" 
                  draggable={false} 
                />
              </div>
            ) : (
              /* Empty Dropzone Area */
              <div 
                className="signature-empty-dropzone"
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
              >
                <div className="dropzone-icon-circle">
                  <UploadCloud size={24} />
                </div>
                <p className="dropzone-prompt">
                  Arrastra aquí tu firma o usa el menú (<strong>⋮</strong>) para cargar un archivo
                </p>
                <span className="dropzone-hint">Formatos soportados: PNG, JPG, SVG con fondo transparente</span>
                <button 
                  type="button" 
                  className="btn-select-file-mini"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  <ImageIcon size={13} />
                  <span>Seleccionar Archivo</span>
                </button>
              </div>
            )}
          </div>

          {/* Footer details & quick actions */}
          {signature && (
            <div className="signature-footer-actions">
              <span className="sig-file-info">
                📄 {signature.filename} {signature.position && (signature.position.x !== 0 || signature.position.y !== 0) ? `(Pos: ${signature.position.x}px, ${signature.position.y}px)` : ''}
              </span>
              <div className="sig-btn-row">
                <button
                  type="button"
                  className="btn-sig-action-outline"
                  onClick={handleResetPosition}
                  title="Restablecer posición al centro"
                >
                  <RotateCcw size={12} />
                  <span>Centrar</span>
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
    </div>
  );
};

import React, { useState, useEffect, useRef } from 'react';
import { Link as LinkIcon, X, CheckCircle2, AlertCircle, Loader2, Image as ImageIcon } from 'lucide-react';

export interface UrlImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (url: string) => void;
  title?: string;
  subtitle?: string;
  confirmText?: string;
}

export const UrlImageModal: React.FC<UrlImageModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title = 'Cargar Firma desde URL',
  subtitle = 'Ingresa el enlace web directo a la imagen de tu firma o estampado (PNG, JPG, SVG o WEBP).',
  confirmText = 'Cargar Imagen',
}) => {
  const [url, setUrl] = useState<string>('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'valid' | 'invalid'>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setUrl('');
      setStatus('idle');
      setErrorMessage('');
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [isOpen]);

  // Validate image URL live
  useEffect(() => {
    const trimmed = url.trim();
    if (!trimmed) {
      setStatus('idle');
      setErrorMessage('');
      return;
    }

    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://') && !trimmed.startsWith('data:image/')) {
      setStatus('invalid');
      setErrorMessage('La URL debe comenzar con http://, https:// o data:image/');
      return;
    }

    setStatus('loading');
    setErrorMessage('');

    const img = new Image();
    let isCancelled = false;

    img.onload = () => {
      if (!isCancelled) {
        setStatus('valid');
        setErrorMessage('');
      }
    };

    img.onerror = () => {
      if (!isCancelled) {
        setStatus('invalid');
        setErrorMessage('No se pudo cargar la imagen desde este enlace. Verifica que sea una URL directa y accesible.');
      }
    };

    img.src = trimmed;

    return () => {
      isCancelled = true;
    };
  }, [url]);

  if (!isOpen) return null;

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (status === 'valid' || url.trim().startsWith('http')) {
      onConfirm(url.trim());
      onClose();
    }
  };

  return (
    <div className="modal-backdrop url-modal-backdrop" onClick={onClose}>
      <div 
        className="modal-dialog url-modal-dialog" 
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="modal-header url-modal-header">
          <div className="modal-title-group">
            <div className="url-modal-icon-badge">
              <LinkIcon size={18} />
            </div>
            <div>
              <h3 className="url-modal-title">{title}</h3>
              <p className="url-modal-sub">{subtitle}</p>
            </div>
          </div>
          <button 
            type="button" 
            className="btn-close" 
            onClick={onClose}
            aria-label="Cerrar modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="modal-body url-modal-body">
          <div className="form-group">
            <label className="form-label" htmlFor="signature-url-input">
              Enlace directo de la imagen:
            </label>
            <div className="url-input-container">
              <LinkIcon size={16} className="url-input-icon" />
              <input
                id="signature-url-input"
                ref={inputRef}
                type="url"
                className={`form-input url-input-field ${status === 'invalid' ? 'is-invalid' : ''} ${status === 'valid' ? 'is-valid' : ''}`}
                placeholder="https://ejemplo.com/imagenes/mi_firma.png"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              {url && (
                <button
                  type="button"
                  className="url-clear-btn"
                  onClick={() => setUrl('')}
                  title="Limpiar campo"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Validation Feedback & Preview */}
          {status === 'loading' && (
            <div className="url-status-message loading">
              <Loader2 size={15} className="animate-spin" />
              <span>Verificando enlace y cargando imagen...</span>
            </div>
          )}

          {status === 'invalid' && (
            <div className="url-status-message error">
              <AlertCircle size={15} />
              <span>{errorMessage || 'Enlace no válido o imagen inaccesible.'}</span>
            </div>
          )}

          {status === 'valid' && (
            <div className="url-preview-card">
              <div className="url-preview-header">
                <CheckCircle2 size={15} className="text-success" />
                <span>Imagen detectada correctamente</span>
              </div>
              <div className="url-preview-box">
                <img 
                  src={url.trim()} 
                  alt="Previsualización de firma" 
                  className="url-preview-img" 
                />
              </div>
            </div>
          )}

          {status === 'idle' && (
            <div className="url-hint-box">
              <ImageIcon size={16} className="url-hint-icon" />
              <span>Recomendación: Utiliza imágenes en formato PNG con fondo transparente para un resultado óptimo en los PDFs.</span>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="modal-footer url-modal-footer">
          <button 
            type="button" 
            className="btn btn-secondary" 
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleSubmit()}
            disabled={status !== 'valid' && (!url.trim().startsWith('http'))}
          >
            <LinkIcon size={15} />
            <span>{confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

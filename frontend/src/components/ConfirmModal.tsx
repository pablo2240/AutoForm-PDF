import React from 'react';
import { AlertTriangle, Trash2, X, AlertCircle } from 'lucide-react';

export interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  subtitle?: string;
  itemName?: string;
  itemMeta?: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'danger' | 'warning' | 'info';
  isLoading?: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  subtitle,
  itemName,
  itemMeta,
  confirmText = 'Eliminar',
  cancelText = 'Cancelar',
  type = 'danger',
  isLoading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop confirm-backdrop" onClick={onClose}>
      <div 
        className={`modal-dialog confirm-dialog confirm-${type}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="confirm-modal-header">
          <div className={`confirm-icon-box ${type}`}>
            {type === 'danger' ? (
              <Trash2 size={24} />
            ) : type === 'warning' ? (
              <AlertTriangle size={24} />
            ) : (
              <AlertCircle size={24} />
            )}
          </div>
          <button 
            type="button" 
            className="btn-close confirm-close" 
            onClick={onClose}
            aria-label="Cerrar modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body Content */}
        <div className="confirm-modal-body">
          <h3 className="confirm-title">{title}</h3>
          
          {itemName && (
            <div className="confirm-item-badge">
              <span className="confirm-item-name">{itemName}</span>
              {itemMeta && <span className="confirm-item-meta">{itemMeta}</span>}
            </div>
          )}

          <p className="confirm-message">
            {subtitle || 'Esta acción eliminará el archivo del sistema y no se podrá deshacer.'}
          </p>

          <div className="confirm-warning-notice">
            <AlertTriangle size={14} className="notice-icon" />
            <span>Se borrarán el archivo PDF físico y todos los mapeos de coordenadas asociados.</span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="confirm-modal-footer">
          <button
            type="button"
            className="btn btn-secondary confirm-btn-cancel"
            onClick={onClose}
            disabled={isLoading}
          >
            {cancelText}
          </button>

          <button
            type="button"
            className={`btn ${type === 'danger' ? 'btn-danger-gradient' : 'btn-primary'} confirm-btn-action`}
            onClick={() => {
              onConfirm();
              onClose();
            }}
            disabled={isLoading}
          >
            {type === 'danger' ? <Trash2 size={16} /> : null}
            <span>{isLoading ? 'Eliminando...' : confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

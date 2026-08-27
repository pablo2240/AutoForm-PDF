import React from 'react';
import { X, Download, CheckCircle, FileText, ExternalLink, Trash2, Zap } from 'lucide-react';
import { getDownloadUrl } from '../api';

interface ResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: {
    filename: string;
    total_placed: number;
    is_temporary?: boolean;
  } | null;
  onDownloadAndCleanup?: () => void;
}

export const ResultModal: React.FC<ResultModalProps> = ({
  isOpen,
  onClose,
  result,
  onDownloadAndCleanup,
}) => {
  if (!isOpen || !result) return null;

  const downloadUrl = getDownloadUrl(result.filename);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog result-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header success-header">
          <div className="modal-title-group">
            <CheckCircle className="icon-success" size={22} />
            <h3>¡Formulario Generado con Éxito!</h3>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body text-center">
          <div className="result-icon-box">
            <FileText size={48} className="text-primary" />
          </div>

          <h4>{result.filename}</h4>
          <p className="result-stats">
            Se estamparon <strong>{result.total_placed}</strong> campos con auto-ajuste tipográfico sobre el formulario original.
          </p>

          {result.is_temporary && (
            <div className="temp-cleaned-badge">
              <Zap size={14} />
              <span>Plantilla temporal de 1 solo uso procesada y lista para descargar</span>
            </div>
          )}

          <div className="result-actions">
            <a 
              href={downloadUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="btn btn-secondary btn-large"
            >
              <ExternalLink size={18} />
              <span>Ver en Nueva Pestaña</span>
            </a>

            <a 
              href={downloadUrl} 
              download={result.filename}
              className="btn btn-primary btn-large"
            >
              <Download size={18} />
              <span>Descargar PDF Lleno</span>
            </a>
          </div>

          {onDownloadAndCleanup && (
            <div className="cleanup-action-box">
              <button
                type="button"
                className="btn btn-outline-warning btn-large w-full"
                onClick={onDownloadAndCleanup}
                title="Descarga el PDF y elimina la plantilla temporal del servidor"
              >
                <Trash2 size={16} />
                <span>⚡ Descargar y Limpiar Plantilla de la Sesión</span>
              </button>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary w-full" onClick={onClose}>
            Cerrar y Continuar Editando
          </button>
        </div>
      </div>
    </div>
  );
};

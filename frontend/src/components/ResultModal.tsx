import React from 'react';
import { X, Download, CheckCircle, FileText, ExternalLink } from 'lucide-react';
import { getDownloadUrl } from '../api';

interface ResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: {
    filename: string;
    total_placed: number;
  } | null;
}

export const ResultModal: React.FC<ResultModalProps> = ({
  isOpen,
  onClose,
  result,
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

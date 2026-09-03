import React, { useState } from 'react';
import { X, Download, CheckCircle, FileText, Zap, AlertTriangle, ShieldCheck, ChevronDown, ChevronUp, PlusCircle } from 'lucide-react';
import { getDownloadUrl } from '../api';
import type { FillResultData } from '../types';

interface ResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: FillResultData | null;
}

export const ResultModal: React.FC<ResultModalProps> = ({
  isOpen,
  onClose,
  result,
}) => {
  const [showAuditDetails, setShowAuditDetails] = useState(false);
  if (!isOpen || !result) return null;

  const downloadUrl = getDownloadUrl(result.filename);
  const audit = result.audit_report;

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
            Se completaron y validaron <strong>{result.total_placed > 0 ? result.total_placed : (audit?.filled || 0)}</strong> campos requeridos sobre el formulario.
          </p>

          {/* Audit Report Summary Banner */}
          {audit && (audit.unfilled.length > 0 || audit.blocked.length > 0) && (
            <div className="audit-summary-container">
              <button 
                type="button" 
                className="btn-audit-toggle"
                onClick={() => setShowAuditDetails(!showAuditDetails)}
              >
                <div className="audit-toggle-left">
                  <ShieldCheck size={16} className="text-emerald" />
                  <span>Auditoría de Campos ({audit.filled} llenos · {audit.unfilled.length} por enriquecer · {audit.blocked.length} bloqueados)</span>
                </div>
                {showAuditDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {showAuditDetails && (
                <div className="audit-details-card">
                  {audit.unfilled.length > 0 && (
                    <div className="audit-section-group">
                      <div className="audit-section-title">
                        <AlertTriangle size={14} className="text-amber" />
                        <strong>Campos Omitidos por Falta de Dato en Perfil ({audit.unfilled.length})</strong>
                      </div>
                      <p className="audit-section-desc">Estos campos son válidos pero no tienen dato exacto en <code>company_data.json</code>:</p>
                      <div className="audit-list">
                        {audit.unfilled.slice(0, 10).map((u, i) => (
                          <div key={i} className="audit-item unfilled-item">
                            <div className="audit-item-header">
                              <span className="audit-item-label">{u.label || u.field}</span>
                              <span className="badge-audit badge-unfilled">Sin dato</span>
                            </div>
                            {u.suggestion && (
                              <div className="audit-suggestion">
                                <PlusCircle size={12} />
                                <span>{u.suggestion}</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {audit.blocked.length > 0 && (
                    <div className="audit-section-group">
                      <div className="audit-section-title">
                        <ShieldCheck size={14} className="text-muted" />
                        <strong>Protegidos por Lista Negra / Cumplimiento ({audit.blocked.length})</strong>
                      </div>
                      <p className="audit-section-desc">Campos omitidos deliberadamente (PEP, uso exclusivo entidad, clientes o doble nacionalidad):</p>
                      <div className="audit-list">
                        {audit.blocked.slice(0, 6).map((b, i) => (
                          <div key={i} className="audit-item blocked-item">
                            <span className="audit-item-label">{b.label || b.field}</span>
                            <span className="badge-audit badge-blocked">Bloqueado {b.rule || 'Tier 1'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {result.is_temporary && (
            <div className="temp-cleaned-badge">
              <Zap size={14} />
              <span>Plantilla temporal de 1 solo uso procesada y lista para descargar</span>
            </div>
          )}

          <div className="result-actions">
            <a 
              href={downloadUrl} 
              download={result.filename}
              className="btn btn-primary btn-large w-full"
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


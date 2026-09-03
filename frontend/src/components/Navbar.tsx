import React, { useRef } from 'react';
import type { TemplateInfo } from '../types';
import logoIac from '../assets/logo_iac.png';
import { 
  FileText, 
  Upload, 
  Save, 
  Play, 
  ChevronLeft, 
  ChevronRight, 
  RotateCcw,
  Building2,
  Trash2,
  Zap,
  Sparkles
} from 'lucide-react';

interface NavbarProps {
  templates: TemplateInfo[];
  selectedTemplate: string;
  onSelectTemplate: (templateId: string) => void;
  onUploadTemplate: (file: File, isTemporary?: boolean) => void;
  onDeleteTemplate: (templateId: string) => void;
  currentPage: number;
  totalPages: number;
  onChangePage: (page: number) => void;
  onSaveMapping: () => void;
  onGeneratePdf: (isTemporary?: boolean) => void;
  onAiFill: () => void;
  onClearMappings: () => void;
  onOpenCompanyData: () => void;
  isSaving: boolean;
  isGenerating: boolean;
  isAiFilling: boolean;
  mappingsCount: number;
  isTemporarySession?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  templates,
  selectedTemplate,
  onSelectTemplate,
  onUploadTemplate,
  onDeleteTemplate,
  currentPage,
  totalPages,
  onChangePage,
  onSaveMapping,
  onGeneratePdf,
  onAiFill,
  onClearMappings,
  onOpenCompanyData,
  isSaving,
  isGenerating,
  isAiFilling,
  mappingsCount,
  isTemporarySession = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const tempFileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, isTemp: boolean = false) => {
    if (e.target.files && e.target.files[0]) {
      onUploadTemplate(e.target.files[0], isTemp);
    }
    if (e.target) e.target.value = '';
  };

  const handleDeleteCurrentTemplate = () => {
    if (!selectedTemplate) return;
    onDeleteTemplate(selectedTemplate);
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="logo-badge logo-iac-badge" title="IAC - Ingeniería Asistida Por Computador">
          <img src={logoIac} alt="IAC" className="navbar-iac-logo" />
        </div>
        <div className="brand-text">
          <h1 className="app-title">AutoForm PDF</h1>
        </div>
      </div>

      <div className="navbar-controls">
        {/* Template Selector & Action Buttons */}
        <div className="control-group">
          <FileText className="control-icon" size={16} />
          <select 
            className="select-input"
            value={selectedTemplate} 
            onChange={(e) => onSelectTemplate(e.target.value)}
          >
            {templates.length === 0 && (
              <option value="" disabled>No hay plantillas disponibles</option>
            )}
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.filename} ({t.size_kb} KB)
              </option>
            ))}
          </select>

          {/* Delete Template Button */}
          {selectedTemplate && (
            <button
              type="button"
              className="btn btn-icon-only btn-delete-template"
              onClick={handleDeleteCurrentTemplate}
              title={`Eliminar plantilla "${templates.find(t => t.id === selectedTemplate)?.filename || selectedTemplate}"`}
            >
              <Trash2 size={15} />
            </button>
          )}

          {/* Hidden Regular Upload */}
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            accept="application/pdf" 
            onChange={(e) => handleFileChange(e, false)}
          />

          {/* Hidden Quick/Temporary Upload */}
          <input 
            type="file" 
            ref={tempFileInputRef} 
            style={{ display: 'none' }} 
            accept="application/pdf" 
            onChange={(e) => handleFileChange(e, true)}
          />

          <button 
            className="btn btn-secondary btn-icon"
            onClick={() => fileInputRef.current?.click()}
            title="Subir PDF como plantilla permanente"
          >
            <Upload size={15} />
            <span className="btn-label-responsive">Subir PDF</span>
          </button>

          <button 
            className="btn btn-secondary btn-icon btn-ai-fill"
            onClick={onAiFill}
            disabled={isAiFilling}
            title="Autollenar inteligentemente este PDF con IA (Soporta PDF planos y AcroForms con datos de empresa, contacto y banco)"
          >
            <Sparkles size={14} className={`sparkles-icon ${isAiFilling ? 'spinning-sparkle' : ''}`} />
            <span>{isAiFilling ? 'Autollenando IA...' : 'Autollenado IA'}</span>
          </button>
        </div>


        {/* Temporary Session Badge */}
        {isTemporarySession && (
          <div className="quick-fill-badge-indicator" title="Esta plantilla es temporal y se limpiará al descargar">
            <Zap size={12} />
            <span>Sesión Temporal (1 solo uso)</span>
          </div>
        )}

        {/* Page Switcher */}
        {totalPages > 1 && (
          <div className="pagination-group">
            <button 
              className="btn btn-icon-only" 
              disabled={currentPage <= 0}
              onClick={() => onChangePage(currentPage - 1)}
              title="Página anterior"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="page-indicator">
              Página <strong>{currentPage + 1}</strong> de {totalPages}
            </span>
            <button 
              className="btn btn-icon-only" 
              disabled={currentPage >= totalPages - 1}
              onClick={() => onChangePage(currentPage + 1)}
              title="Página siguiente"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        )}
      </div>

      <div className="navbar-actions">
        <button 
          className="btn btn-secondary btn-company-data" 
          onClick={onOpenCompanyData}
          title="Editar datos de la empresa y perfiles"
        >
          <Building2 size={16} />
          <span className="btn-label-responsive">Datos Empresa</span>
        </button>

        <button 
          className="btn btn-secondary" 
          onClick={onClearMappings}
          disabled={mappingsCount === 0}
          title="Borrar todos los cuadros dibujados"
        >
          <RotateCcw size={16} />
          <span className="btn-label-responsive">Limpiar</span>
        </button>

        <button 
          className="btn btn-secondary" 
          onClick={onSaveMapping}
          disabled={isSaving || !selectedTemplate}
          title="Guardar coordenadas en JSON"
        >
          <Save size={16} />
          <span className="btn-label-responsive">{isSaving ? 'Guardando...' : 'Guardar Mapeo'}</span>
        </button>

        <button 
          className={`btn btn-generate-primary ${isTemporarySession ? 'btn-warning-gradient' : 'btn-primary'}`} 
          onClick={() => onGeneratePdf(isTemporarySession)}
          disabled={isGenerating || mappingsCount === 0}
          title={isTemporarySession ? "Generar, descargar y limpiar plantilla temporal" : "Generar PDF estampado"}
        >
          {isTemporarySession ? <Zap size={16} /> : <Play size={16} />}
          <span className="btn-label-always-visible">
            {isGenerating 
              ? 'Generando...' 
              : isTemporarySession 
                ? `Descargar y Limpiar (${mappingsCount})` 
                : `Generar PDF (${mappingsCount})`}
          </span>
        </button>
      </div>
    </header>
  );
};

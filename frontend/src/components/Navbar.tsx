import React, { useRef } from 'react';
import type { TemplateInfo } from '../types';
import { 
  FileText, 
  Upload, 
  Save, 
  Play, 
  ChevronLeft, 
  ChevronRight, 
  RotateCcw,
  Building2,
  FileCheck
} from 'lucide-react';

interface NavbarProps {
  templates: TemplateInfo[];
  selectedTemplate: string;
  onSelectTemplate: (templateId: string) => void;
  onUploadTemplate: (file: File) => void;
  currentPage: number;
  totalPages: number;
  onChangePage: (page: number) => void;
  onSaveMapping: () => void;
  onGeneratePdf: () => void;
  onClearMappings: () => void;
  onOpenCompanyData: () => void;
  isSaving: boolean;
  isGenerating: boolean;
  mappingsCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  templates,
  selectedTemplate,
  onSelectTemplate,
  onUploadTemplate,
  currentPage,
  totalPages,
  onChangePage,
  onSaveMapping,
  onGeneratePdf,
  onClearMappings,
  onOpenCompanyData,
  isSaving,
  isGenerating,
  mappingsCount,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUploadTemplate(e.target.files[0]);
    }
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="logo-badge">
          <FileCheck className="icon-main" />
        </div>
        <div className="brand-text">
          <h1 className="app-title">AutoForm PDF</h1>
          <span className="app-subtitle">WYSIWYG PDF Form Mapper</span>
        </div>
      </div>

      <div className="navbar-controls">
        {/* Template Selector */}
        <div className="control-group">
          <FileText className="control-icon" size={16} />
          <select 
            className="select-input"
            value={selectedTemplate} 
            onChange={(e) => onSelectTemplate(e.target.value)}
          >
            <option value="" disabled>Selecciona una plantilla PDF</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.filename} ({t.size_kb} KB)
              </option>
            ))}
          </select>

          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            accept="application/pdf" 
            onChange={handleFileChange}
          />
          <button 
            className="btn btn-secondary btn-icon"
            onClick={() => fileInputRef.current?.click()}
            title="Subir nuevo PDF"
          >
            <Upload size={16} />
            <span>Subir PDF</span>
          </button>
        </div>

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
          className="btn btn-secondary" 
          onClick={onOpenCompanyData}
          title="Editar datos de la empresa"
        >
          <Building2 size={16} />
          <span>Datos Empresa</span>
        </button>

        <button 
          className="btn btn-secondary" 
          onClick={onClearMappings}
          disabled={mappingsCount === 0}
          title="Borrar todos los cuadros dibujados"
        >
          <RotateCcw size={16} />
          <span>Limpiar</span>
        </button>

        <button 
          className="btn btn-secondary" 
          onClick={onSaveMapping}
          disabled={isSaving || !selectedTemplate}
          title="Guardar coordenadas en JSON"
        >
          <Save size={16} />
          <span>{isSaving ? 'Guardando...' : 'Guardar Mapeo'}</span>
        </button>

        <button 
          className="btn btn-primary" 
          onClick={onGeneratePdf}
          disabled={isGenerating || mappingsCount === 0}
          title="Generar PDF estampado"
        >
          <Play size={16} />
          <span>{isGenerating ? 'Generando...' : `Generar PDF (${mappingsCount})`}</span>
        </button>
      </div>
    </header>
  );
};

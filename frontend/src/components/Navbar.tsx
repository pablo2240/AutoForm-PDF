import React, { useRef } from 'react';
import type { TemplateInfo, CommercialProfilePublic, AdminSessionUser } from '../types';
import { CommercialProfileSelector } from './CommercialProfileSelector';
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
  Sparkles,
  LogOut
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
  commercialProfiles: CommercialProfilePublic[];
  activeCommercialProfileId: string;
  onSelectCommercialProfile: (id: string) => void;
  onOpenCommercialProfileAdmin: () => void;
  isLoadingCommercialProfiles?: boolean;
  currentUser?: AdminSessionUser | null;
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  templates,
  selectedTemplate,
  onSelectTemplate: _onSelectTemplate,
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
  commercialProfiles,
  activeCommercialProfileId,
  onSelectCommercialProfile,
  onOpenCommercialProfileAdmin,
  isLoadingCommercialProfiles = false,
  currentUser = null,
  onLogout,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, isTemp: boolean = false) => {
    if (e.target.files && e.target.files[0]) {
      onUploadTemplate(e.target.files[0], isTemp);
    }
    if (e.target) e.target.value = '';
  };

  const currentTemplateObj = templates.find((t) => t.id === selectedTemplate) || (templates.length > 0 ? templates[0] : null);

  const handleDeleteCurrentTemplate = () => {
    const targetId = selectedTemplate || (currentTemplateObj ? currentTemplateObj.id : '');
    if (!targetId) return;
    onDeleteTemplate(targetId);
  };

  const getUserInitials = (user?: AdminSessionUser | null) => {
    if (!user) return 'U';
    if (user.nombre && user.apellido) {
      return `${user.nombre[0]}${user.apellido[0]}`.toUpperCase();
    }
    if (user.profile_name) {
      const parts = user.profile_name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      }
      return parts[0].substring(0, 2).toUpperCase();
    }
    if (user.email) {
      return user.email.substring(0, 2).toUpperCase();
    }
    return 'U';
  };

  const getUserDisplayName = (user?: AdminSessionUser | null) => {
    if (!user) return '';
    if (user.profile_name && user.profile_name.trim()) return user.profile_name.trim();
    if (user.nombre && user.apellido) return `${user.nombre} ${user.apellido}`.trim();
    if (user.nombre) return user.nombre.trim();
    return user.email || '';
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="logo-badge logo-iac-badge" title="IAC - Ingeniería Asistida Por Computador">
          <img src={logoIac} alt="IAC" className="navbar-iac-logo" />
        </div>
        <div className="brand-text">
          <h1 className="app-title">
            <span className="app-title-main">AutoForm</span>
            <span className="app-title-suffix"> PDF</span>
          </h1>
        </div>
      </div>

      <div className="navbar-controls">
        {/* Single-file Slot: Mantiene un único documento activo con reemplazo atómico */}
        <div className="control-group single-file-slot-group">
          {/* Hidden File Input */}
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            accept="application/pdf" 
            onChange={(e) => handleFileChange(e, false)}
          />

          {currentTemplateObj ? (
            <div className="single-file-slot-pill" title={`Documento activo: ${currentTemplateObj.filename}`}>
              <FileText className="control-icon text-amber" size={15} />
              <span className="single-file-name" title={currentTemplateObj.filename}>
                {currentTemplateObj.filename}
              </span>
              <span className="single-file-badge">
                {currentTemplateObj.size_kb} KB
              </span>
              <button
                type="button"
                className="btn btn-icon-only btn-delete-template"
                onClick={handleDeleteCurrentTemplate}
                title={`Eliminar "${currentTemplateObj.filename}"`}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ) : (
            <div className="single-file-empty-pill">
              <FileText className="control-icon text-muted" size={15} />
              <span className="single-file-empty-label">Sin documento activo</span>
            </div>
          )}

          <button 
            className="btn btn-secondary btn-icon"
            onClick={() => fileInputRef.current?.click()}
            title={currentTemplateObj ? "Subir nuevo PDF y reemplazar el actual automáticamente" : "Subir archivo PDF"}
          >
            <Upload size={14} />
            <span className="btn-label-responsive">
              {currentTemplateObj ? "Reemplazar PDF" : "Subir PDF"}
            </span>
          </button>

          <button 
            className="btn btn-secondary btn-icon btn-ai-fill"
            onClick={onAiFill}
            disabled={isAiFilling || !currentTemplateObj || !activeCommercialProfileId}
            title={!currentTemplateObj
              ? "⚠️ Sube un PDF antes de autollenar con IA"
              : (!activeCommercialProfileId
                  ? "⚠️ Debes seleccionar un responsable comercial o 'Solo Representante Legal' antes de autollenar con IA"
                  : "Autollenar inteligentemente este PDF con IA (Soporta PDF planos y AcroForms con datos de empresa, contacto y banco)")}
          >
            <Sparkles size={13} className={`sparkles-icon ${isAiFilling ? 'spinning-sparkle' : ''}`} />
            <span className="ai-fill-text-full">{isAiFilling ? 'Autollenando IA...' : 'Autollenado IA'}</span>
            <span className="ai-fill-text-short">{isAiFilling ? 'IA...' : 'IA'}</span>
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
              <ChevronLeft size={15} />
            </button>
            <span className="page-indicator page-indicator-full">
              Página <strong>{currentPage + 1}</strong> de {totalPages}
            </span>
            <span className="page-indicator page-indicator-short">
              <strong>{currentPage + 1}</strong>/{totalPages}
            </span>
            <button 
              className="btn btn-icon-only" 
              disabled={currentPage >= totalPages - 1}
              onClick={() => onChangePage(currentPage + 1)}
              title="Página siguiente"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        )}
      </div>

      <div className="navbar-actions">
        {/* Commercial Profile Selector (ADR-0008) */}
        <CommercialProfileSelector
          profiles={commercialProfiles}
          selectedProfileId={activeCommercialProfileId}
          onSelectProfile={onSelectCommercialProfile}
          onOpenAdminModal={onOpenCommercialProfileAdmin}
          isLoading={isLoadingCommercialProfiles}
          isAdmin={currentUser?.role === 'admin'}
        />

        {/* Action Buttons Cluster */}
        <div className="navbar-action-buttons-cluster">
          <button 
            className="btn btn-secondary btn-icon-only btn-company-data" 
            onClick={onOpenCompanyData}
            title="Datos Empresa: Editar datos corporativos y perfiles"
          >
            <Building2 size={15} />
            <span className="btn-label-responsive">Empresa</span>
          </button>

          <button 
            className="btn btn-secondary btn-icon-only" 
            onClick={onClearMappings}
            disabled={mappingsCount === 0}
            title="Limpiar: Borrar todos los cuadros dibujados"
          >
            <RotateCcw size={15} />
            <span className="btn-label-responsive">Limpiar</span>
          </button>

          <button 
            className="btn btn-secondary btn-icon-only" 
            onClick={onSaveMapping}
            disabled={isSaving || !selectedTemplate}
            title="Guardar Mapeo: Guardar coordenadas en JSON"
          >
            <Save size={15} />
            <span className="btn-label-responsive">{isSaving ? 'Guardando...' : 'Guardar'}</span>
          </button>
        </div>

        {/* Primary CTA: Generar PDF */}
        <button 
          className={`btn btn-generate-primary ${isTemporarySession ? 'btn-warning-gradient' : 'btn-primary'}`} 
          onClick={() => onGeneratePdf(isTemporarySession)}
          disabled={isGenerating || mappingsCount === 0 || !activeCommercialProfileId}
          title={!activeCommercialProfileId 
            ? "⚠️ Debes seleccionar un responsable comercial o 'Solo Representante Legal' antes de generar el PDF" 
            : isTemporarySession 
              ? "Generar, descargar y limpiar plantilla temporal" 
              : "Generar PDF estampado"}
        >
          {isTemporarySession ? <Zap size={15} /> : <Play size={15} />}
          <span className="btn-label-always-visible btn-cta-text-full">
            {isGenerating 
              ? 'Generando...' 
              : isTemporarySession 
                ? `Descargar (${mappingsCount})` 
                : `Generar PDF (${mappingsCount})`}
          </span>
          <span className="btn-label-always-visible btn-cta-text-short">
            {isGenerating ? 'Generando...' : `PDF (${mappingsCount})`}
          </span>
        </button>

        {/* Current User Session & Logout */}
        {currentUser && onLogout && (
          <div 
            className="navbar-session-user"
            title={`Conectado como: ${getUserDisplayName(currentUser)} (${currentUser.email})`}
          >
            <div className="navbar-avatar-badge" aria-hidden="true">
              {getUserInitials(currentUser)}
            </div>
            <div className="navbar-user-info">
              <span className="navbar-user-name">
                {getUserDisplayName(currentUser)}
              </span>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-icon-only btn-navbar-logout"
              onClick={onLogout}
              title="Cerrar sesión y salir al portal de acceso"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

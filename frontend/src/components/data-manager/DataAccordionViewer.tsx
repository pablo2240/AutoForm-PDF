import React, { useState } from 'react';
import type { CompanyCategory, CategorizedCompanyData, EmployerProfile, GlobalSignature } from '../../types';
import { SignatureSection } from './SignatureSection';
import { 
  Building2, 
  User, 
  ChevronDown, 
  ChevronUp, 
  Trash2, 
  Mail, 
  Phone, 
  Hash, 
  Inbox
} from 'lucide-react';

interface DataAccordionViewerProps {
  companyData: CategorizedCompanyData;
  profiles: EmployerProfile[];
  signature: GlobalSignature | null;
  onDeleteCompanyField: (category: CompanyCategory, id: string) => void;
  onDeleteProfile: (id: string) => void;
  onSaveSignature: (sig: GlobalSignature | null) => void;
}

const TABS: { id: CompanyCategory; label: string; icon: string }[] = [
  { id: 'id', label: 'ID', icon: '🪪' },
  { id: 'contacto', label: 'Contacto', icon: '📍' },
  { id: 'banco', label: 'Banco', icon: '🏦' },
  { id: 'otros', label: 'Otros', icon: '❓' },
];

export const DataAccordionViewer: React.FC<DataAccordionViewerProps> = ({
  companyData,
  profiles,
  signature,
  onDeleteCompanyField,
  onDeleteProfile,
  onSaveSignature,
}) => {
  // Accordion state
  const [isCompanyOpen, setIsCompanyOpen] = useState<boolean>(true);
  const [openProfileIds, setOpenProfileIds] = useState<Record<string, boolean>>({});

  // Active tab inside Company Accordion
  const [activeCompanyTab, setActiveCompanyTab] = useState<CompanyCategory>('id');

  const toggleProfile = (id: string) => {
    setOpenProfileIds(prev => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const totalCompanyFields = Object.values(companyData).reduce(
    (acc, items) => acc + items.length,
    0
  );

  const currentTabFields = companyData[activeCompanyTab] || [];

  return (
    <div className="data-accordion-viewer">
      <div className="viewer-header-section">
        <h3 className="viewer-title">Estructura de Datos</h3>
        <span className="viewer-badge-total">
          {totalCompanyFields} datos de empresa • {profiles.length} perfiles
        </span>
      </div>

      <div className="accordion-stack">
        {/* 1. ACORDEÓN PRINCIPAL: DATOS DE LA EMPRESA */}
        <div className={`accordion-card company-card ${isCompanyOpen ? 'expanded' : 'collapsed'}`}>
          <div
            className="accordion-header"
            onClick={() => setIsCompanyOpen(prev => !prev)}
            role="button"
            tabIndex={0}
          >
            <div className="accordion-title-group">
              <div className="header-icon-box company">
                <Building2 size={18} />
              </div>
              <div className="title-text-col">
                <h4 className="accordion-main-title">🏢 Datos de la Empresa</h4>
                <span className="accordion-sub-meta">
                  {totalCompanyFields} campo{totalCompanyFields !== 1 ? 's' : ''} registrado{totalCompanyFields !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
            <div className="accordion-header-actions">
              <div className="chevron-pill">
                {isCompanyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>
          </div>

          {/* Internal Tabs & Content */}
          {isCompanyOpen && (
            <div className="accordion-body company-body">
              {/* Internal Category Tabs */}
              <div className="internal-category-tabs">
                {TABS.map((tab) => {
                  const count = (companyData[tab.id] || []).length;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      className={`cat-tab-btn ${activeCompanyTab === tab.id ? 'active' : ''}`}
                      onClick={() => setActiveCompanyTab(tab.id)}
                    >
                      <span className="tab-emoji">{tab.icon}</span>
                      <span className="tab-text">{tab.label}</span>
                      <span className="tab-count-bubble">{count}</span>
                    </button>
                  );
                })}
              </div>

              {/* Tab Content List */}
              <div className="category-items-container">
                {currentTabFields.length === 0 ? (
                  <div className="empty-category-notice">
                    <Inbox size={22} className="empty-icon" />
                    <p>No hay campos registrados en la categoría {TABS.find(t => t.id === activeCompanyTab)?.label}.</p>
                    <span className="empty-helper">Usa el panel de la izquierda para agregar datos aquí.</span>
                  </div>
                ) : (
                  <div className="items-list-grid">
                    {currentTabFields.map((field) => (
                      <div key={field.id} className="field-entry-card">
                        <div className="field-meta-col">
                          <span className="field-item-label">{field.label}</span>
                          <span className="field-item-key">#{field.key}</span>
                        </div>
                        <div className="field-val-col">
                          <span className="field-item-val" title={field.value}>
                            {field.value}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="btn-item-delete"
                          onClick={() => onDeleteCompanyField(activeCompanyTab, field.id)}
                          title="Eliminar este dato"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 2. ACORDEONES DINÁMICOS: PERFILES DE EMPLEADOR */}
        <div className="profiles-section-divider">
          <span className="divider-label">
            👤 Perfiles de Empleador ({profiles.length})
          </span>
        </div>

        {profiles.length === 0 ? (
          <div className="no-profiles-placeholder">
            <User size={26} className="placeholder-icon" />
            <h5>No hay perfiles creados todavía</h5>
            <p>Selecciona "Perfil Empleador" a la izquierda para agregar datos específicos de personas o representantes.</p>
          </div>
        ) : (
          profiles.map((profile) => {
            const isOpen = openProfileIds[profile.id] ?? true; // default open
            return (
              <div
                key={profile.id}
                className={`accordion-card profile-card ${isOpen ? 'expanded' : 'collapsed'}`}
              >
                <div
                  className="accordion-header"
                  onClick={() => toggleProfile(profile.id)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="accordion-title-group">
                    <div className="header-icon-box profile">
                      <User size={18} />
                    </div>
                    <div className="title-text-col">
                      <h4 className="accordion-main-title">👤 {profile.profileName}</h4>
                      <span className="accordion-sub-meta">
                        {[profile.nombre, profile.apellido].filter(Boolean).join(' ') || 'Sin nombre completo'}
                        {profile.email ? ` • ${profile.email}` : ''}
                      </span>
                    </div>
                  </div>

                  <div className="accordion-header-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn-delete-profile-header"
                      onClick={() => onDeleteProfile(profile.id)}
                      title={`Eliminar perfil ${profile.profileName}`}
                    >
                      <Trash2 size={14} />
                    </button>
                    <div className="chevron-pill" onClick={() => toggleProfile(profile.id)}>
                      {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>
                  </div>
                </div>

                {isOpen && (
                  <div className="accordion-body profile-body">
                    <div className="profile-details-grid">
                      {profile.nombre && (
                        <div className="profile-detail-cell">
                          <span className="detail-label">Nombre</span>
                          <span className="detail-value">{profile.nombre}</span>
                        </div>
                      )}
                      {profile.apellido && (
                        <div className="profile-detail-cell">
                          <span className="detail-label">Apellido</span>
                          <span className="detail-value">{profile.apellido}</span>
                        </div>
                      )}
                      {profile.email && (
                        <div className="profile-detail-cell">
                          <span className="detail-label"><Mail size={12} /> Correo / Gmail</span>
                          <span className="detail-value">{profile.email}</span>
                        </div>
                      )}
                      {profile.celular && (
                        <div className="profile-detail-cell">
                          <span className="detail-label"><Phone size={12} /> Celular</span>
                          <span className="detail-value">{profile.celular}</span>
                        </div>
                      )}
                    </div>

                    {/* Custom Fields */}
                    {profile.customFields && profile.customFields.length > 0 && (
                      <div className="profile-custom-fields-wrapper">
                        <span className="custom-fields-title">
                          <Hash size={13} /> Campos Adicionales:
                        </span>
                        <div className="custom-chips-grid">
                          {profile.customFields.map((cf) => (
                            <div key={cf.id} className="custom-chip-badge">
                              <span className="chip-key">{cf.key}:</span>
                              <span className="chip-val">{cf.value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* 3. SECCIÓN FINAL: FIRMA GLOBAL (DRAG & DROP + CONFIGURACIÓN) */}
        <div className="profiles-section-divider">
          <span className="divider-label">
            ✍️ Firma del Sistema
          </span>
        </div>

        <SignatureSection 
          signature={signature}
          onSaveSignature={onSaveSignature}
        />
      </div>
    </div>
  );
};

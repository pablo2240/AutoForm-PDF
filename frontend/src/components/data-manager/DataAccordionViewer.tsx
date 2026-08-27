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
  Inbox,
  Pencil,
  Check,
  X
} from 'lucide-react';

interface DataAccordionViewerProps {
  companyData: CategorizedCompanyData;
  profiles: EmployerProfile[];
  signature: GlobalSignature | null;
  onDeleteCompanyField: (category: CompanyCategory, id: string) => void;
  onUpdateCompanyField: (category: CompanyCategory, id: string, newLabel: string, newValue: string) => void;
  onDeleteProfile: (id: string) => void;
  onUpdateProfile: (id: string, updatedProfile: EmployerProfile) => void;
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
  onUpdateCompanyField,
  onDeleteProfile,
  onUpdateProfile,
  onSaveSignature,
}) => {
  // Accordion state
  const [isCompanyOpen, setIsCompanyOpen] = useState<boolean>(true);
  const [openProfileIds, setOpenProfileIds] = useState<Record<string, boolean>>({});

  // Active tab inside Company Accordion
  const [activeCompanyTab, setActiveCompanyTab] = useState<CompanyCategory>('id');

  // In-line editing state for Company Fields
  const [editingCompanyFieldId, setEditingCompanyFieldId] = useState<string | null>(null);
  const [editCompanyLabel, setEditCompanyLabel] = useState<string>('');
  const [editCompanyValue, setEditCompanyValue] = useState<string>('');

  // In-line editing state for Employer Profiles
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [editProfileForm, setEditProfileForm] = useState<EmployerProfile | null>(null);

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

  // Start editing company field
  const startEditCompanyField = (id: string, label: string, val: string) => {
    setEditingCompanyFieldId(id);
    setEditCompanyLabel(label);
    setEditCompanyValue(val);
  };

  const handleSaveEditCompanyField = (id: string) => {
    if (!editCompanyLabel.trim() || !editCompanyValue.trim()) {
      alert('El nombre del campo y el valor no pueden estar vacíos.');
      return;
    }
    onUpdateCompanyField(activeCompanyTab, id, editCompanyLabel.trim(), editCompanyValue.trim());
    setEditingCompanyFieldId(null);
  };

  const handleCancelEditCompanyField = () => {
    setEditingCompanyFieldId(null);
  };

  // Start editing employer profile
  const startEditProfile = (profile: EmployerProfile) => {
    setEditingProfileId(profile.id);
    setEditProfileForm({ ...profile, customFields: [...profile.customFields] });
  };

  const handleSaveEditProfile = (id: string) => {
    if (!editProfileForm || !editProfileForm.profileName.trim()) {
      alert('El nombre del perfil es obligatorio.');
      return;
    }
    onUpdateProfile(id, editProfileForm);
    setEditingProfileId(null);
    setEditProfileForm(null);
  };

  const handleCancelEditProfile = () => {
    setEditingProfileId(null);
    setEditProfileForm(null);
  };

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
                    {currentTabFields.map((field) => {
                      const isEditing = editingCompanyFieldId === field.id;

                      if (isEditing) {
                        return (
                          /* IN-LINE EDITING FORM */
                          <div key={field.id} className="field-entry-card is-editing">
                            <div className="inline-edit-fields-row">
                              <input
                                type="text"
                                className="inline-edit-input label-input"
                                value={editCompanyLabel}
                                onChange={(e) => setEditCompanyLabel(e.target.value)}
                                placeholder="Nombre del campo"
                                autoFocus
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSaveEditCompanyField(field.id);
                                  if (e.key === 'Escape') handleCancelEditCompanyField();
                                }}
                              />
                              <input
                                type="text"
                                className="inline-edit-input val-input"
                                value={editCompanyValue}
                                onChange={(e) => setEditCompanyValue(e.target.value)}
                                placeholder="Valor"
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSaveEditCompanyField(field.id);
                                  if (e.key === 'Escape') handleCancelEditCompanyField();
                                }}
                              />
                            </div>
                            <div className="inline-actions-group">
                              <button
                                type="button"
                                className="btn-action-inline confirm"
                                onClick={() => handleSaveEditCompanyField(field.id)}
                                title="Guardar cambios (Enter)"
                              >
                                <Check size={14} />
                              </button>
                              <button
                                type="button"
                                className="btn-action-inline cancel"
                                onClick={handleCancelEditCompanyField}
                                title="Cancelar edición (Esc)"
                              >
                                <X size={14} />
                              </button>
                            </div>
                          </div>
                        );
                      }

                      return (
                        /* NORMAL VIEW ROW WITH PENCIL & TRASH */
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
                          <div className="field-row-actions">
                            <button
                              type="button"
                              className="btn-item-action edit"
                              onClick={() => startEditCompanyField(field.id, field.label, field.value)}
                              title="Editar este dato"
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              type="button"
                              className="btn-item-action delete"
                              onClick={() => onDeleteCompanyField(activeCompanyTab, field.id)}
                              title="Eliminar este dato"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
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
            const isOpen = openProfileIds[profile.id] ?? true;
            const isEditing = editingProfileId === profile.id;

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
                      className="btn-item-action edit-header"
                      onClick={() => {
                        if (!isOpen) toggleProfile(profile.id);
                        startEditProfile(profile);
                      }}
                      title={`Editar perfil ${profile.profileName}`}
                    >
                      <Pencil size={14} />
                    </button>
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
                    {isEditing && editProfileForm ? (
                      /* IN-LINE EDITING PROFILE FORM */
                      <div className="profile-edit-inline-container">
                        <div className="profile-edit-grid">
                          <div className="form-group">
                            <label className="form-label subtle">Nombre del Perfil</label>
                            <input
                              type="text"
                              className="form-input mini"
                              value={editProfileForm.profileName}
                              onChange={(e) => setEditProfileForm(prev => prev ? ({ ...prev, profileName: e.target.value }) : null)}
                              placeholder="Nombre Perfil"
                            />
                          </div>
                          <div className="form-group">
                            <label className="form-label subtle">Nombre</label>
                            <input
                              type="text"
                              className="form-input mini"
                              value={editProfileForm.nombre}
                              onChange={(e) => setEditProfileForm(prev => prev ? ({ ...prev, nombre: e.target.value }) : null)}
                              placeholder="Nombre"
                            />
                          </div>
                          <div className="form-group">
                            <label className="form-label subtle">Apellido</label>
                            <input
                              type="text"
                              className="form-input mini"
                              value={editProfileForm.apellido}
                              onChange={(e) => setEditProfileForm(prev => prev ? ({ ...prev, apellido: e.target.value }) : null)}
                              placeholder="Apellido"
                            />
                          </div>
                          <div className="form-group">
                            <label className="form-label subtle">Correo / Gmail</label>
                            <input
                              type="email"
                              className="form-input mini"
                              value={editProfileForm.email}
                              onChange={(e) => setEditProfileForm(prev => prev ? ({ ...prev, email: e.target.value }) : null)}
                              placeholder="Correo"
                            />
                          </div>
                          <div className="form-group">
                            <label className="form-label subtle">Celular</label>
                            <input
                              type="tel"
                              className="form-input mini"
                              value={editProfileForm.celular}
                              onChange={(e) => setEditProfileForm(prev => prev ? ({ ...prev, celular: e.target.value }) : null)}
                              placeholder="Celular"
                            />
                          </div>
                        </div>

                        <div className="profile-edit-actions-footer">
                          <button
                            type="button"
                            className="btn-action-inline confirm with-text"
                            onClick={() => handleSaveEditProfile(profile.id)}
                          >
                            <Check size={14} />
                            <span>Guardar Perfil</span>
                          </button>
                          <button
                            type="button"
                            className="btn-action-inline cancel with-text"
                            onClick={handleCancelEditProfile}
                          >
                            <X size={14} />
                            <span>Cancelar</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* NORMAL PROFILE VIEW */
                      <>
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
                      </>
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

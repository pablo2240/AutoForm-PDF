import React, { useState } from 'react';
import type { CompanyCategory, CompanyFieldItem, EmployerProfile, CustomFieldItem } from '../../types';
import { 
  Building2, 
  UserPlus, 
  Plus, 
  Trash2, 
  Save, 
  Sparkles, 
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

interface DataEntryPanelProps {
  onSaveCompanyField: (field: Omit<CompanyFieldItem, 'id'>) => void;
  onSaveEmployerProfile: (profile: Omit<EmployerProfile, 'id'>) => void;
}

const CATEGORY_OPTIONS: { id: CompanyCategory; label: string; icon: string }[] = [
  { id: 'id', label: 'ID', icon: '🪪' },
  { id: 'contacto', label: 'Contacto', icon: '📍' },
  { id: 'banco', label: 'Banco', icon: '🏦' },
  { id: 'otros', label: 'Otros', icon: '❓' },
];

const SUGGESTED_COMPANY_FIELDS: Record<CompanyCategory, string[]> = {
  id: ['NIT', 'Razón Social', 'Matrícula Mercantil', 'Cámara de Comercio', 'RUT'],
  contacto: ['Dirección Principal', 'Teléfono / PBX', 'Correo Electrónico', 'Ciudad / Municipio', 'Página Web'],
  banco: ['Nombre del Banco', 'Tipo de Cuenta', 'Número de Cuenta', 'Titular de Cuenta', 'Certificación Bancaria'],
  otros: ['Actividad Económica (CIIU)', 'Régimen Tributario', 'Representante Legal', 'Fecha de Constitución'],
};

export const DataEntryPanel: React.FC<DataEntryPanelProps> = ({
  onSaveCompanyField,
  onSaveEmployerProfile,
}) => {
  // Mode: 'company' | 'profile'
  const [recordType, setRecordType] = useState<'company' | 'profile'>('company');

  // State for Option A: Company Field
  const [companyCategory, setCompanyCategory] = useState<CompanyCategory>('id');
  const [companyFieldName, setCompanyFieldName] = useState<string>('');
  const [companyFieldValue, setCompanyFieldValue] = useState<string>('');

  // State for Option B: Employer Profile
  const [profileName, setProfileName] = useState<string>('');
  const [nombre, setNombre] = useState<string>('');
  const [apellido, setApellido] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [celular, setCelular] = useState<string>('');
  const [customFields, setCustomFields] = useState<{ key: string; value: string }[]>([]);

  // Feedback banner
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setFeedback({ message, type });
    setTimeout(() => setFeedback(null), 3000);
  };

  // Handle Submit Option A (Company)
  const handleCompanySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanLabel = companyFieldName.trim();
    const cleanValue = companyFieldValue.trim();

    if (!cleanLabel || !cleanValue) {
      showNotification('Por favor ingresa tanto el nombre del campo como su valor.', 'error');
      return;
    }

    const key = cleanLabel.toLowerCase().replace(/\s+/g, '_').normalize('NFD').replace(/[\u0300-\u036f]/g, '');

    onSaveCompanyField({
      key,
      label: cleanLabel,
      value: cleanValue,
      category: companyCategory,
    });

    setCompanyFieldName('');
    setCompanyFieldValue('');
    showNotification(`Dato "${cleanLabel}" guardado exitosamente en ${CATEGORY_OPTIONS.find(c => c.id === companyCategory)?.label}.`);
  };

  // Handle Submit Option B (Employer Profile)
  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanProfileName = profileName.trim();

    if (!cleanProfileName) {
      showNotification('Por favor ingresa el Nombre del Perfil (ej. Fernando Gozo).', 'error');
      return;
    }

    if (!nombre.trim() && !apellido.trim() && !email.trim() && !celular.trim()) {
      showNotification('Ingresa al menos uno de los datos personales (Nombre, Apellido, Email o Celular).', 'error');
      return;
    }

    const filteredCustomFields: CustomFieldItem[] = customFields
      .filter(f => f.key.trim() && f.value.trim())
      .map(f => ({
        id: `cf-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        key: f.key.trim(),
        value: f.value.trim(),
      }));

    onSaveEmployerProfile({
      profileName: cleanProfileName,
      nombre: nombre.trim(),
      apellido: apellido.trim(),
      email: email.trim(),
      celular: celular.trim(),
      customFields: filteredCustomFields,
    });

    // Reset Form
    setProfileName('');
    setNombre('');
    setApellido('');
    setEmail('');
    setCelular('');
    setCustomFields([]);
    showNotification(`Perfil "${cleanProfileName}" creado exitosamente.`);
  };

  const handleAddCustomField = () => {
    setCustomFields(prev => [...prev, { key: '', value: '' }]);
  };

  const handleCustomFieldChange = (index: number, field: 'key' | 'value', value: string) => {
    setCustomFields(prev => {
      const copy = [...prev];
      copy[index][field] = value;
      return copy;
    });
  };

  const handleRemoveCustomField = (index: number) => {
    setCustomFields(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="data-entry-panel">
      <div className="panel-header-section">
        <h3 className="panel-title">Agregar Datos</h3>
        <p className="panel-subtitle">
          Elige qué tipo de registro deseas ingresar y completa los campos.
        </p>
      </div>

      {/* Record Type Selector (Progressive Disclosure) */}
      <div className="record-type-selector">
        <button
          type="button"
          className={`type-toggle-btn ${recordType === 'company' ? 'active' : ''}`}
          onClick={() => setRecordType('company')}
        >
          <Building2 size={16} />
          <span>Nuevo Dato Empresa</span>
        </button>
        <button
          type="button"
          className={`type-toggle-btn ${recordType === 'profile' ? 'active' : ''}`}
          onClick={() => setRecordType('profile')}
        >
          <UserPlus size={16} />
          <span>Perfil Empleador</span>
        </button>
      </div>

      {feedback && (
        <div className={`entry-feedback-banner feedback-${feedback.type}`}>
          {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* OPTION A: Empresa Form */}
      {recordType === 'company' ? (
        <form onSubmit={handleCompanySubmit} className="entry-form-container">
          <div className="form-group">
            <label className="form-label">Categoría del Dato</label>
            <div className="category-chips-grid">
              {CATEGORY_OPTIONS.map((cat) => (
                <button
                  type="button"
                  key={cat.id}
                  className={`category-chip ${companyCategory === cat.id ? 'active' : ''}`}
                  onClick={() => setCompanyCategory(cat.id)}
                >
                  <span className="cat-icon">{cat.icon}</span>
                  <span className="cat-label">{cat.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Quick Suggestions */}
          <div className="form-group">
            <label className="form-label subtle">Sugerencias frecuentes:</label>
            <div className="suggestions-flex">
              {SUGGESTED_COMPANY_FIELDS[companyCategory].map((sug) => (
                <button
                  type="button"
                  key={sug}
                  className="suggestion-tag"
                  onClick={() => setCompanyFieldName(sug)}
                >
                  + {sug}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="company-field-name">
              Nombre del Campo <span className="req">*</span>
            </label>
            <input
              id="company-field-name"
              type="text"
              className="form-input"
              placeholder="ej. NIT, Teléfono, Tipo de cuenta..."
              value={companyFieldName}
              onChange={(e) => setCompanyFieldName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="company-field-val">
              Valor <span className="req">*</span>
            </label>
            <input
              id="company-field-val"
              type="text"
              className="form-input"
              placeholder="ej. 900.123.456-7, info@empresa.com..."
              value={companyFieldValue}
              onChange={(e) => setCompanyFieldValue(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn-submit-entry primary"
            disabled={!companyFieldName.trim() || !companyFieldValue.trim()}
          >
            <Save size={16} />
            <span>Guardar en Empresa</span>
          </button>
        </form>
      ) : (
        /* OPTION B: Employer Profile Form */
        <form onSubmit={handleProfileSubmit} className="entry-form-container">
          <div className="form-group">
            <label className="form-label" htmlFor="profile-name">
              Nombre del Perfil <span className="req">*</span>
            </label>
            <input
              id="profile-name"
              type="text"
              className="form-input highlight"
              placeholder="ej. Fernando Gozo, Representante Legal..."
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
            />
            <span className="form-help-text">Este nombre identificará el bloque del empleador en el visualizador.</span>
          </div>

          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="emp-nombre">Nombre</label>
              <input
                id="emp-nombre"
                type="text"
                className="form-input"
                placeholder="ej. Fernando"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="emp-apellido">Apellido</label>
              <input
                id="emp-apellido"
                type="text"
                className="form-input"
                placeholder="ej. Gozo"
                value={apellido}
                onChange={(e) => setApellido(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="emp-email">Correo / Gmail</label>
            <input
              id="emp-email"
              type="email"
              className="form-input"
              placeholder="ej. fernando.gozo@gmail.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="emp-celular">Celular</label>
            <input
              id="emp-celular"
              type="tel"
              className="form-input"
              placeholder="ej. +57 300 123 4567"
              value={celular}
              onChange={(e) => setCelular(e.target.value)}
            />
          </div>

          {/* Dynamic Custom Fields */}
          <div className="custom-fields-block">
            <div className="custom-fields-header">
              <label className="form-label">Campos Personalizados</label>
              <button
                type="button"
                className="btn-add-mini"
                onClick={handleAddCustomField}
              >
                <Plus size={13} />
                <span>Agregar campo</span>
              </button>
            </div>

            {customFields.map((cf, idx) => (
              <div key={idx} className="custom-field-row">
                <input
                  type="text"
                  className="form-input mini"
                  placeholder="Etiqueta (ej. Cargo)"
                  value={cf.key}
                  onChange={(e) => handleCustomFieldChange(idx, 'key', e.target.value)}
                />
                <input
                  type="text"
                  className="form-input mini"
                  placeholder="Valor (ej. Director)"
                  value={cf.value}
                  onChange={(e) => handleCustomFieldChange(idx, 'value', e.target.value)}
                />
                <button
                  type="button"
                  className="btn-remove-row"
                  onClick={() => handleRemoveCustomField(idx)}
                  title="Eliminar campo"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <button
            type="submit"
            className="btn-submit-entry secondary-gradient"
            disabled={!profileName.trim()}
          >
            <Sparkles size={16} />
            <span>Crear / Actualizar Perfil</span>
          </button>
        </form>
      )}
    </div>
  );
};

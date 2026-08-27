import React, { useState } from 'react';
import type { CompanyData } from '../types';
import { X, Plus, Trash2, Save, Building2 } from 'lucide-react';

interface CompanyDataModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: CompanyData;
  onSave: (updatedData: CompanyData) => void;
}

export const CompanyDataModal: React.FC<CompanyDataModalProps> = ({
  isOpen,
  onClose,
  data,
  onSave,
}) => {
  const [formData, setFormData] = useState<CompanyData>({ ...data });
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  if (!isOpen) return null;

  const handleChange = (key: string, val: string) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
  };

  const handleDelete = (key: string) => {
    setFormData((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleAddField = () => {
    const formattedKey = newKey.trim().toLowerCase().replace(/\s+/g, '_');
    if (!formattedKey) return;
    setFormData((prev) => ({ ...prev, [formattedKey]: newValue.trim() }));
    setNewKey('');
    setNewValue('');
  };

  const handleSave = () => {
    onSave(formData);
    onClose();
  };

  const formatLabel = (key: string) => {
    return key
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <Building2 className="modal-icon" size={20} />
            <h3>Perfil y Variables de la Empresa</h3>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            Estos son los valores que se estamparán automáticamente en las celdas del formulario PDF cuando crees los mapeos.
          </p>

          <div className="form-fields-scroll">
            {Object.keys(formData).map((key) => (
              <div key={key} className="form-row">
                <div className="form-field-info">
                  <label className="field-label">{formatLabel(key)}</label>
                  <span className="field-key-badge">{key}</span>
                </div>
                <input 
                  type="text" 
                  className="field-input" 
                  value={String(formData[key] || '')}
                  onChange={(e) => handleChange(key, e.target.value)}
                />
                <button 
                  className="btn-delete-field" 
                  onClick={() => handleDelete(key)}
                  title="Eliminar variable"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>

          <div className="add-field-card">
            <h4>Agregar Nueva Variable</h4>
            <div className="add-field-row">
              <input 
                type="text"
                placeholder="Nombre (ej. numero_matricula)"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                className="input-new-key"
              />
              <input 
                type="text"
                placeholder="Valor (ej. 00293812)"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                className="input-new-value"
              />
              <button 
                className="btn btn-secondary btn-icon"
                onClick={handleAddField}
                disabled={!newKey.trim()}
              >
                <Plus size={16} />
                <span>Agregar</span>
              </button>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            <Save size={16} />
            <span>Guardar Cambios</span>
          </button>
        </div>
      </div>
    </div>
  );
};

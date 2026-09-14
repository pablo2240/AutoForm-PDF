import React from 'react';
import { UserCheck, Settings, AlertCircle } from 'lucide-react';
import type { CommercialProfilePublic } from '../types';

interface CommercialProfileSelectorProps {
  profiles: CommercialProfilePublic[];
  selectedProfileId: string;
  onSelectProfile: (id: string) => void;
  onOpenAdminModal: () => void;
  isLoading?: boolean;
}

export const CommercialProfileSelector: React.FC<CommercialProfileSelectorProps> = ({
  profiles,
  selectedProfileId,
  onSelectProfile,
  onOpenAdminModal,
  isLoading = false,
}) => {
  const isUnselected = !selectedProfileId;

  return (
    <div className="commercial-profile-selector-container">
      <div className={`commercial-selector-wrapper ${isUnselected ? 'unselected-attention' : ''}`}>
        <UserCheck size={16} className={`selector-icon ${isUnselected ? 'icon-warning' : 'icon-active'}`} />
        <select
          className="commercial-select"
          value={selectedProfileId}
          onChange={(e) => onSelectProfile(e.target.value)}
          disabled={isLoading}
          title="Responsable comercial asignado para diligenciar campos de contacto en el formulario"
        >
          <option value="" disabled>
            {isLoading ? 'Cargando...' : '⚠️ Selecciona responsable...'}
          </option>
          <option value="legal_rep_only">
            ⚖️ Sin comercial (Solo Rep. Legal)
          </option>
          <optgroup label="Perfiles Comerciales">
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                👤 {p.profile_name} ({p.cargo || 'Comercial'})
              </option>
            ))}
          </optgroup>
        </select>
        {isUnselected && (
          <span className="selector-required-badge" title="Requerido para generar o autollenar PDF">
            <AlertCircle size={13} />
            <span className="badge-text">Requerido</span>
          </span>
        )}
      </div>

      <button
        type="button"
        className="btn btn-secondary btn-icon-only btn-manage-profiles"
        onClick={onOpenAdminModal}
        title="Gestionar perfiles comerciales (Administración)"
      >
        <Settings size={15} />
      </button>
    </div>
  );
};

import React, { useState } from 'react';
import type { CompanyData, MappingItem, GlobalSignature } from '../types';
import { 
  Search, 
  CheckCircle2, 
  Circle, 
  Trash2, 
  Layers, 
  MousePointerClick,
  Info,
  Tag,
  PenTool
} from 'lucide-react';

interface SidebarProps {
  companyData: CompanyData;
  selectedField: string | null;
  onSelectField: (fieldKey: string) => void;
  mappings: MappingItem[];
  currentPage: number;
  onDeleteMapping: (id: string) => void;
  globalSignature?: GlobalSignature | null;
  onSelectSignature?: () => void;
  isSignatureActive?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  companyData,
  selectedField,
  onSelectField,
  mappings,
  currentPage,
  onDeleteMapping,
  globalSignature,
  onSelectSignature,
  isSignatureActive,
}) => {
  const [activeTab, setActiveTab] = useState<'variables' | 'mapped'>('variables');
  const [searchTerm, setSearchTerm] = useState('');

  const keys = Object.keys(companyData).filter(k => k !== 'firma_global');
  const filteredKeys = keys.filter((key) => {
    const val = String(companyData[key] || '');
    return key.toLowerCase().includes(searchTerm.toLowerCase()) || 
           val.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const getMappingForField = (fieldKey: string) => {
    return mappings.filter((m) => m.field_key === fieldKey);
  };

  const currentMappingsOnPage = mappings.filter((m) => m.page_number === currentPage);
  const signatureMappings = mappings.filter((m) => m.field_key === 'firma_o_imagen' || m.field_key === 'firma_global');

  const formatLabel = (key: string) => {
    return key
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <aside className="sidebar">
      {/* Tabs */}
      <div className="sidebar-tabs">
        <button 
          className={`sidebar-tab ${activeTab === 'variables' ? 'active' : ''}`}
          onClick={() => setActiveTab('variables')}
        >
          <Tag size={15} />
          <span>Variables ({keys.length + (globalSignature ? 1 : 0)})</span>
        </button>
        <button 
          className={`sidebar-tab ${activeTab === 'mapped' ? 'active' : ''}`}
          onClick={() => setActiveTab('mapped')}
        >
          <Layers size={15} />
          <span>Mapeados ({mappings.length})</span>
        </button>
      </div>

      {activeTab === 'variables' ? (
        <div className="tab-content">
          {/* Instructions Box */}
          <div className="instruction-box">
            <MousePointerClick size={16} className="instruction-icon" />
            <p>
              {isSignatureActive ? (
                <>
                  Seleccionaste <strong>Firma Global</strong>. Haz clic y dibuja el recuadro donde deseas estampar la firma en el PDF.
                </>
              ) : selectedField ? (
                <>
                  Seleccionaste <strong>{formatLabel(selectedField)}</strong>. Haz clic y arrastra sobre el PDF para dibujar el recuadro.
                </>
              ) : (
                'Selecciona una variable o la firma y dibuja su cuadro en el formulario.'
              )}
            </p>
          </div>

          {/* Search Bar */}
          <div className="search-box">
            <Search size={14} className="search-icon" />
            <input 
              type="text" 
              placeholder="Buscar variable o valor..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          {/* Special Global Signature Card */}
          {globalSignature && (!searchTerm || 'firma global'.includes(searchTerm.toLowerCase())) && (
            <div 
              className={`variable-card signature-highlight-card ${isSignatureActive ? 'selected' : ''} ${signatureMappings.length > 0 ? 'mapped' : ''}`}
              onClick={onSelectSignature}
            >
              <div className="variable-header">
                <div className="variable-title-row">
                  <PenTool size={15} className="status-icon sig-icon" />
                  <span className="variable-name">✍️ Firma Global</span>
                </div>
                {signatureMappings.length > 0 && (
                  <span className="badge-page">
                    {signatureMappings.length > 1 ? `${signatureMappings.length} estampados` : `Pág ${signatureMappings[0].page_number + 1}`}
                  </span>
                )}
              </div>
              <div className="signature-preview-row">
                <img 
                  src={globalSignature.base64} 
                  alt="Firma" 
                  className="sidebar-sig-thumb" 
                />
                <span className="sig-click-hint">
                  {isSignatureActive ? '🎯 Listo para dibujar en PDF' : 'Clic para estampar'}
                </span>
              </div>
            </div>
          )}

          {/* Variables List */}
          <div className="variables-list">
            {filteredKeys.map((key) => {
              const value = companyData[key];
              const fieldMappings = getMappingForField(key);
              const isSelected = selectedField === key;
              const isMapped = fieldMappings.length > 0;

              return (
                <div 
                  key={key}
                  className={`variable-card ${isSelected ? 'selected' : ''} ${isMapped ? 'mapped' : ''}`}
                  onClick={() => onSelectField(key)}
                >
                  <div className="variable-header">
                    <div className="variable-title-row">
                      {isMapped ? (
                        <CheckCircle2 size={15} className="status-icon mapped" />
                      ) : (
                        <Circle size={15} className="status-icon unmapped" />
                      )}
                      <span className="variable-name">{formatLabel(key)}</span>
                    </div>
                    {isMapped && (
                      <span className="badge-page">
                        {fieldMappings.length > 1 ? `${fieldMappings.length} asignaciones` : `Pág ${fieldMappings[0].page_number + 1}`}
                      </span>
                    )}
                  </div>
                  <div className="variable-value" title={String(value)}>
                    {String(value) || <span className="empty-val">(Sin valor)</span>}
                  </div>
                </div>
              );
            })}

            {filteredKeys.length === 0 && !globalSignature && (
              <div className="empty-state">
                <Info size={24} />
                <p>No se encontraron variables con "{searchTerm}"</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Mapped Fields Tab */
        <div className="tab-content">
          <div className="mapped-tab-header">
            <h4>Campos en Página Actual ({currentMappingsOnPage.length})</h4>
          </div>

          <div className="mapped-list">
            {currentMappingsOnPage.map((item) => (
              <div key={item.id} className="mapped-item-card">
                <div className="mapped-item-info">
                  <span className="mapped-item-key">{formatLabel(item.label || item.field_key)}</span>
                  <span className="mapped-item-coords">
                    X: {Math.round(item.box.x0)}, Y: {Math.round(item.box.y0)} | Ancho: {Math.round(item.box.x1 - item.box.x0)}
                  </span>
                </div>
                <button 
                  className="btn-delete-mapping"
                  onClick={() => onDeleteMapping(item.id)}
                  title="Eliminar mapeo"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}

            {currentMappingsOnPage.length === 0 && (
              <div className="empty-state">
                <Layers size={24} />
                <p>Aún no has mapeado ningún campo en esta página.</p>
                <span className="sub-text">Selecciona una variable de la pestaña izquierda y dibuja un recuadro.</span>
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
};

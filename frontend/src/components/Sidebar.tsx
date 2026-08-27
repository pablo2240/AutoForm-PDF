import React, { useState } from 'react';
import type { CompanyData, MappingItem } from '../types';
import { 
  Search, 
  CheckCircle2, 
  Circle, 
  Trash2, 
  Layers, 
  MousePointerClick,
  Info,
  Tag
} from 'lucide-react';

interface SidebarProps {
  companyData: CompanyData;
  selectedField: string | null;
  onSelectField: (fieldKey: string) => void;
  mappings: MappingItem[];
  currentPage: number;
  onDeleteMapping: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  companyData,
  selectedField,
  onSelectField,
  mappings,
  currentPage,
  onDeleteMapping,
}) => {
  const [activeTab, setActiveTab] = useState<'variables' | 'mapped'>('variables');
  const [searchTerm, setSearchTerm] = useState('');

  const keys = Object.keys(companyData);
  const filteredKeys = keys.filter((key) => {
    const val = String(companyData[key] || '');
    return key.toLowerCase().includes(searchTerm.toLowerCase()) || 
           val.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const getMappingForField = (fieldKey: string) => {
    return mappings.filter((m) => m.field_key === fieldKey);
  };

  const currentMappingsOnPage = mappings.filter((m) => m.page_number === currentPage);

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
          <span>Variables ({keys.length})</span>
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
              {selectedField ? (
                <>
                  Seleccionaste <strong>{formatLabel(selectedField)}</strong>. Haz clic y arrastra sobre el PDF para dibujar el recuadro.
                </>
              ) : (
                'Selecciona una variable de abajo y dibuja su cuadro en el formulario.'
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

            {filteredKeys.length === 0 && (
              <div className="empty-state">
                <Info size={24} />
                <p>No se encontraron variables con "{searchTerm}"</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="tab-content">
          <div className="mapped-header">
            <h4>Campos en esta Página ({currentMappingsOnPage.length})</h4>
          </div>

          <div className="mapped-list">
            {currentMappingsOnPage.length === 0 ? (
              <div className="empty-state">
                <Info size={24} />
                <p>No hay campos mapeados en la página {currentPage + 1}.</p>
                <span className="helper-text">Selecciona una variable y dibújala en el visor.</span>
              </div>
            ) : (
              currentMappingsOnPage.map((item) => (
                <div key={item.id} className="mapped-item-card">
                  <div className="mapped-info">
                    <span className="mapped-label">{formatLabel(item.field_key)}</span>
                    <span className="mapped-val-preview">
                      Valor: {String(companyData[item.field_key] || '')}
                    </span>
                    <span className="mapped-coords">
                      X: {Math.round(item.box.x0)}, Y: {Math.round(item.box.y0)} | Ancho: {Math.round(item.box.x1 - item.box.x0)}px
                    </span>
                  </div>
                  <button 
                    className="btn-delete"
                    onClick={() => onDeleteMapping(item.id)}
                    title="Eliminar mapeo"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))
            )}
          </div>

          {mappings.length > currentMappingsOnPage.length && (
            <div className="mapped-other-pages">
              <h5>En otras páginas ({mappings.length - currentMappingsOnPage.length})</h5>
              {mappings
                .filter((m) => m.page_number !== currentPage)
                .map((item) => (
                  <div key={item.id} className="mapped-mini-item">
                    <span>{formatLabel(item.field_key)}</span>
                    <span className="badge-page">Pág {item.page_number + 1}</span>
                    <button 
                      className="btn-delete-mini"
                      onClick={() => onDeleteMapping(item.id)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </aside>
  );
};

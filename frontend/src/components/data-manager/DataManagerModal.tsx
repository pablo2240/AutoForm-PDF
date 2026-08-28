import React, { useState, useEffect } from 'react';
import type { 
  CompanyData, 
  CompanyCategory, 
  CategorizedCompanyData, 
  CompanyFieldItem, 
  EmployerProfile,
  GlobalSignature 
} from '../../types';
import { DataEntryPanel } from './DataEntryPanel';
import { DataAccordionViewer } from './DataAccordionViewer';
import { X, Save, Layers } from 'lucide-react';

interface DataManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialCompanyData: CompanyData;
  globalSignature: GlobalSignature | null;
  onSaveData: (flatData: CompanyData, profiles: EmployerProfile[], signature: GlobalSignature | null) => void;
}

// Initial fallback categorization helper
function categorizeFlatCompanyData(data: CompanyData): CategorizedCompanyData {
  const result: CategorizedCompanyData = {
    id: [],
    contacto: [],
    banco: [],
    otros: [],
  };

  const idKeys = ['nit', 'rut', 'razon_social', 'matricula', 'cedula', 'cedula_representante', 'empresa_id'];
  const contactoKeys = ['direccion', 'telefono', 'email', 'correo', 'ciudad', 'pais', 'web'];
  const bancoKeys = ['banco', 'cuenta', 'tipo_cuenta', 'titular'];

  Object.entries(data).forEach(([key, val]) => {
    const valueStr = String(val || '').trim();
    if (!valueStr) return;

    const lowerKey = key.toLowerCase();
    const label = key
      .split('_')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');

    let category: CompanyCategory = 'otros';
    if (idKeys.some(k => lowerKey.includes(k))) {
      category = 'id';
    } else if (contactoKeys.some(k => lowerKey.includes(k))) {
      category = 'contacto';
    } else if (bancoKeys.some(k => lowerKey.includes(k))) {
      category = 'banco';
    }

    result[category].push({
      id: `cf-${key}-${Math.random().toString(36).substring(2, 6)}`,
      key,
      label,
      value: valueStr,
      category,
    });
  });

  return result;
}

// Flatten back to key-value record for form stamping
export function flattenToCompanyData(
  categorized: CategorizedCompanyData,
  profiles: EmployerProfile[],
  signature: GlobalSignature | null
): CompanyData {
  const flat: CompanyData = {};

  // Add all company fields
  Object.values(categorized).forEach((fields: CompanyFieldItem[]) => {
    fields.forEach((f: CompanyFieldItem) => {
      flat[f.key] = f.value;
    });
  });

  // Add employer profile fields so they can be mapped to PDF forms too!
  profiles.forEach((p) => {
    const prefix = p.profileName.toLowerCase().replace(/\s+/g, '_').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (p.nombre) flat[`${prefix}_nombre`] = p.nombre;
    if (p.apellido) flat[`${prefix}_apellido`] = p.apellido;
    if (p.nombre && p.apellido) flat[`${prefix}_nombre_completo`] = `${p.nombre} ${p.apellido}`;
    if (p.email) flat[`${prefix}_email`] = p.email;
    if (p.celular) flat[`${prefix}_celular`] = p.celular;

    if (p.customFields) {
      p.customFields.forEach(cf => {
        const cfKey = cf.key.toLowerCase().replace(/\s+/g, '_').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        flat[`${prefix}_${cfKey}`] = cf.value;
      });
    }
  });

  // Add global signature reference
  if (signature) {
    flat['firma_global'] = signature.filename;
  }

  return flat;
}

export const DEFAULT_INITIAL_COMPANY_CATEGORIES: CategorizedCompanyData = {
  id: [
    { id: 'f-id-1', key: 'razon_social', label: 'Razón Social', value: 'Ingeniería Asistida Por Computador S.A.S', category: 'id' },
    { id: 'f-id-2', key: 'nit', label: 'NIT', value: '8110047212', category: 'id' },
    { id: 'f-id-3', key: 'representante_legal', label: 'Representante Legal', value: 'Guillermo Humberto Cañón Sarria', category: 'id' },
    { id: 'f-id-4', key: 'representante_nombre', label: 'Representante Nombre', value: 'Guillermo Humberto', category: 'id' },
    { id: 'f-id-5', key: 'representante_apellido', label: 'Representante Apellido', value: 'Cañón Sarria', category: 'id' },
    { id: 'f-id-6', key: 'tipo_documento', label: 'Tipo de Documento', value: 'C.C', category: 'id' },
    { id: 'f-id-7', key: 'numero_cedula', label: 'Número de Cédula', value: '98555384', category: 'id' },
    { id: 'f-id-8', key: 'lugar_expedicion_rep', label: 'Lugar de Expedición Rep', value: 'Envigado', category: 'id' },
    { id: 'f-id-9', key: 'correo_rep', label: 'Correo Rep', value: 'guillermo.canon@iaclatam.com', category: 'id' },
    { id: 'f-id-10', key: 'celular_rep', label: 'Celular Rep', value: '3104120217', category: 'id' },
    { id: 'f-id-11', key: 'ciudad', label: 'Ciudad', value: 'Medellin', category: 'id' },
    { id: 'f-id-12', key: 'departamento', label: 'Departamento', value: 'Antioquia', category: 'id' },
    { id: 'f-id-13', key: 'pais', label: 'País', value: 'Colombia', category: 'id' },
  ],
  contacto: [
    { id: 'f-con-1', key: 'telefono', label: 'Teléfono', value: '2656868', category: 'contacto' },
    { id: 'f-con-2', key: 'direccion_principal', label: 'Dirección Principal', value: 'Carrera 63 B # 32 E -25 OFC 206', category: 'contacto' },
    { id: 'f-con-3', key: 'pagina_web', label: 'Página Web', value: 'iaclatam.com', category: 'contacto' },
  ],
  banco: [
    { id: 'f-ban-1', key: 'entidad_bancaria', label: 'Entidad Bancaria', value: 'BANCOLOMBIA', category: 'banco' },
    { id: 'f-ban-2', key: 'numero_cuenta', label: 'Número de Cuenta', value: '00300833888', category: 'banco' },
    { id: 'f-ban-3', key: 'tipo_cuenta', label: 'Tipo de Cuenta', value: 'Ahorros', category: 'banco' },
  ],
  otros: [],
};

export const DEFAULT_INITIAL_EMPLOYER_PROFILES: EmployerProfile[] = [];

const STORAGE_PROFILES_KEY = 'autoform_employer_profiles_v3';
const STORAGE_COMPANY_KEY = 'autoform_categorized_company_v3';
const STORAGE_SIGNATURE_KEY = 'autoform_global_signature_v1';

export const DataManagerModal: React.FC<DataManagerModalProps> = ({
  isOpen,
  onClose,
  initialCompanyData,
  globalSignature,
  onSaveData,
}) => {
  const [categorizedCompany, setCategorizedCompany] = useState<CategorizedCompanyData>(() => {
    const saved = localStorage.getItem(STORAGE_COMPANY_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    if (initialCompanyData && Object.keys(initialCompanyData).length > 0) {
      return categorizeFlatCompanyData(initialCompanyData);
    }
    return DEFAULT_INITIAL_COMPANY_CATEGORIES;
  });

  const [profiles, setProfiles] = useState<EmployerProfile[]>(() => {
    const saved = localStorage.getItem(STORAGE_PROFILES_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return DEFAULT_INITIAL_EMPLOYER_PROFILES;
  });

  const [signature, setSignature] = useState<GlobalSignature | null>(() => {
    if (globalSignature) return globalSignature;
    const saved = localStorage.getItem(STORAGE_SIGNATURE_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return null;
  });

  // Real-time synchronization helper
  const syncAndPersist = (
    nextCat: CategorizedCompanyData,
    nextProfiles: EmployerProfile[],
    nextSig: GlobalSignature | null
  ) => {
    const flat = flattenToCompanyData(nextCat, nextProfiles, nextSig);
    localStorage.setItem(STORAGE_COMPANY_KEY, JSON.stringify(nextCat));
    localStorage.setItem(STORAGE_PROFILES_KEY, JSON.stringify(nextProfiles));
    if (nextSig) {
      localStorage.setItem(STORAGE_SIGNATURE_KEY, JSON.stringify(nextSig));
    } else {
      localStorage.removeItem(STORAGE_SIGNATURE_KEY);
    }
    onSaveData(flat, nextProfiles, nextSig);
  };

  // Sync if initial data changes
  useEffect(() => {
    if (initialCompanyData && Object.keys(initialCompanyData).length > 0) {
      const saved = localStorage.getItem(STORAGE_COMPANY_KEY);
      if (!saved) {
        setCategorizedCompany(categorizeFlatCompanyData(initialCompanyData));
      }
    }
  }, [initialCompanyData]);

  useEffect(() => {
    if (globalSignature !== undefined) {
      setSignature(globalSignature);
    }
  }, [globalSignature]);

  if (!isOpen) return null;

  // Add/Update Company Field
  const handleSaveCompanyField = (field: Omit<CompanyFieldItem, 'id'>) => {
    setCategorizedCompany(prev => {
      const list = prev[field.category] || [];
      const existingIdx = list.findIndex(item => item.key === field.key);
      let updatedList: CompanyFieldItem[];

      if (existingIdx >= 0) {
        // Update
        updatedList = [...list];
        updatedList[existingIdx] = {
          ...updatedList[existingIdx],
          label: field.label,
          value: field.value,
        };
      } else {
        // Add
        const newItem: CompanyFieldItem = {
          id: `f-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          ...field,
        };
        updatedList = [...list, newItem];
      }

      const next = {
        ...prev,
        [field.category]: updatedList,
      };

      syncAndPersist(next, profiles, signature);
      return next;
    });
  };

  // Update Company Field (In-line Edit)
  const handleUpdateCompanyField = (
    category: CompanyCategory,
    id: string,
    newLabel: string,
    newValue: string
  ) => {
    setCategorizedCompany(prev => {
      const list = prev[category] || [];
      const updatedList = list.map(item => {
        if (item.id === id) {
          return {
            ...item,
            label: newLabel,
            value: newValue,
          };
        }
        return item;
      });
      const next = {
        ...prev,
        [category]: updatedList,
      };
      syncAndPersist(next, profiles, signature);
      return next;
    });
  };

  // Delete Company Field
  const handleDeleteCompanyField = (category: CompanyCategory, id: string) => {
    setCategorizedCompany(prev => {
      const next = {
        ...prev,
        [category]: (prev[category] || []).filter(item => item.id !== id),
      };
      syncAndPersist(next, profiles, signature);
      return next;
    });
  };

  // Add/Update Employer Profile
  const handleSaveEmployerProfile = (profile: Omit<EmployerProfile, 'id'>) => {
    setProfiles(prev => {
      const existingIdx = prev.findIndex(
        p => p.profileName.toLowerCase() === profile.profileName.toLowerCase()
      );
      let updated: EmployerProfile[];

      if (existingIdx >= 0) {
        updated = [...prev];
        updated[existingIdx] = {
          ...updated[existingIdx],
          ...profile,
        };
      } else {
        const newProf: EmployerProfile = {
          id: `prof-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          ...profile,
        };
        updated = [...prev, newProf];
      }

      syncAndPersist(categorizedCompany, updated, signature);
      return updated;
    });
  };

  // Update Employer Profile (In-line Edit)
  const handleUpdateProfile = (id: string, updatedProfile: EmployerProfile) => {
    setProfiles(prev => {
      const updated = prev.map(p => (p.id === id ? updatedProfile : p));
      syncAndPersist(categorizedCompany, updated, signature);
      return updated;
    });
  };

  // Delete Employer Profile
  const handleDeleteProfile = (id: string) => {
    setProfiles(prev => {
      const updated = prev.filter(p => p.id !== id);
      syncAndPersist(categorizedCompany, updated, signature);
      return updated;
    });
  };

  // Save Signature
  const handleSaveSignature = (sig: GlobalSignature | null) => {
    setSignature(sig);
    syncAndPersist(categorizedCompany, profiles, sig);
  };

  // Save everything and sync
  const handleFinalSaveAndClose = () => {
    syncAndPersist(categorizedCompany, profiles, signature);
    onClose();
  };

  const handleClose = () => {
    syncAndPersist(categorizedCompany, profiles, signature);
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={handleClose}>
      <div className="modal-dialog data-manager-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header dm-header">
          <div className="modal-title-group">
            <div className="dm-title-badge">
              <Layers size={18} />
            </div>
            <div>
              <h3 className="dm-modal-title">Gestor de Datos, Perfiles y Firma</h3>
              <p className="dm-modal-sub">
                Interfaz modular con revelación progresiva para alimentar formularios y estampados automáticamente.
              </p>
            </div>
          </div>
          <button className="btn-close" onClick={handleClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body: Two-Column Layout */}
        <div className="modal-body dm-two-columns-layout">
          {/* Columna Izquierda: Panel de Entrada */}
          <div className="dm-left-col">
            <DataEntryPanel
              onSaveCompanyField={handleSaveCompanyField}
              onSaveEmployerProfile={handleSaveEmployerProfile}
            />
          </div>

          {/* Columna Derecha: Visualizador en Acordeón */}
          <div className="dm-right-col">
            <DataAccordionViewer
              companyData={categorizedCompany}
              profiles={profiles}
              signature={signature}
              onDeleteCompanyField={handleDeleteCompanyField}
              onUpdateCompanyField={handleUpdateCompanyField}
              onDeleteProfile={handleDeleteProfile}
              onUpdateProfile={handleUpdateProfile}
              onSaveSignature={handleSaveSignature}
            />
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer dm-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={handleFinalSaveAndClose}>
            <Save size={16} />
            <span>Guardar y Aplicar a Formularios</span>
          </button>
        </div>
      </div>
    </div>
  );
};

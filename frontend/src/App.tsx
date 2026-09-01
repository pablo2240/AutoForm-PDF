import React, { useState, useEffect } from 'react';
import type { 
  TemplateInfo, 
  PDFPage, 
  CompanyData, 
  MappingItem, 
  TemplateMapping,
  BoxCoords,
  BoxPct,
  ItemStyle,
  GlobalSignature 
} from './types';
import { 
  fetchTemplates, 
  uploadPdfTemplate, 
  deleteTemplate,
  fetchPdfPages, 
  fetchCompanyData, 
  saveCompanyData, 
  fetchTemplateMapping, 
  saveTemplateMapping, 
  generateFilledPdf,
  aiFillPdf
} from './api';
import { Navbar } from './components/Navbar';
import { Toolbar } from './components/Toolbar';
import { Sidebar } from './components/Sidebar';
import { PDFCanvas } from './components/PDFCanvas';
import { DataManagerModal } from './components/data-manager/DataManagerModal';
import { ResultModal } from './components/ResultModal';
import { ConfirmModal } from './components/ConfirmModal';

interface ConfirmModalState {
  isOpen: boolean;
  title: string;
  subtitle?: string;
  itemName?: string;
  itemMeta?: string;
  confirmText?: string;
  type?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
}

export const App: React.FC = () => {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [pages, setPages] = useState<PDFPage[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [companyData, setCompanyData] = useState<CompanyData>({});
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [isTemporarySession, setIsTemporarySession] = useState<boolean>(false);

  // Custom Confirm Dialog State
  const [confirmModalData, setConfirmModalData] = useState<ConfirmModalState | null>(null);
  
  // Global Signature State
  const [globalSignature, setGlobalSignature] = useState<GlobalSignature | null>(() => {
    const saved = localStorage.getItem('autoform_global_signature_v1');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return null;
  });

  // Style and editing states
  const [currentStyle, setCurrentStyle] = useState<ItemStyle>({
    font_family: 'Arial',
    font_size: 10,
    bold: false,
    color: '#000000',
    item_type: 'text',
  });
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null);
  const [activeImage, setActiveImage] = useState<{ base64: string; filename: string } | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isAiFilling, setIsAiFilling] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState<boolean>(false);
  const [resultModalData, setResultModalData] = useState<{ filename: string; total_placed: number; is_temporary?: boolean } | null>(null);

  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToastMessage({ text, type });
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  // Initial load
  useEffect(() => {
    async function init() {
      try {
        setIsLoading(true);
        const [tplList, compData] = await Promise.all([
          fetchTemplates(),
          fetchCompanyData(),
        ]);

        let hasNewVariables = false;

        // 1. Merge categorized company data from localStorage if exists
        try {
          const savedCatStr = localStorage.getItem('autoform_categorized_company_v3');
          if (savedCatStr) {
            const savedCat = JSON.parse(savedCatStr);
            if (savedCat && typeof savedCat === 'object') {
              Object.values(savedCat).forEach((fields: any) => {
                if (Array.isArray(fields)) {
                  fields.forEach((f: any) => {
                    if (f && f.key && f.value) {
                      if (compData[f.key] !== f.value) {
                        compData[f.key] = f.value;
                        hasNewVariables = true;
                      }
                    }
                  });
                }
              });
            }
          }
        } catch (e) {
          console.warn('Error merging categorized company data on init:', e);
        }

        // 2. Merge employer profiles from localStorage so their variables are always available
        try {
          const savedProfilesStr = localStorage.getItem('autoform_employer_profiles_v3');
          if (savedProfilesStr) {
            const savedProfiles = JSON.parse(savedProfilesStr);
            if (Array.isArray(savedProfiles) && savedProfiles.length > 0) {
              savedProfiles.forEach((p: any) => {
                if (!p || !p.profileName) return;
                const prefix = p.profileName.toLowerCase().replace(/\s+/g, '_').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
                if (p.nombre) { compData[`${prefix}_nombre`] = p.nombre; hasNewVariables = true; }
                if (p.apellido) { compData[`${prefix}_apellido`] = p.apellido; hasNewVariables = true; }
                if (p.nombre && p.apellido) { compData[`${prefix}_nombre_completo`] = `${p.nombre} ${p.apellido}`; hasNewVariables = true; }
                if (p.email) { compData[`${prefix}_email`] = p.email; hasNewVariables = true; }
                if (p.celular) { compData[`${prefix}_celular`] = p.celular; hasNewVariables = true; }

                if (p.customFields && Array.isArray(p.customFields)) {
                  p.customFields.forEach((cf: any) => {
                    if (cf && cf.key && cf.value) {
                      const cfKey = cf.key.toLowerCase().replace(/\s+/g, '_').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
                      compData[`${prefix}_${cfKey}`] = cf.value;
                      hasNewVariables = true;
                    }
                  });
                }
              });
            }
          }
        } catch (e) {
          console.warn('Error merging profiles on init:', e);
        }

        setTemplates(tplList);
        setCompanyData({ ...compData });

        // If local storage had extra variables not yet in backend, sync them
        if (hasNewVariables) {
          saveCompanyData(compData).catch(() => {});
        }

        if (tplList.length > 0) {
          setSelectedTemplate(tplList[0].id);
        }
      } catch (err: any) {
        showToast(`Error al inicializar: ${err.message}`, 'error');
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, []);

  // When selected template changes
  useEffect(() => {
    if (!selectedTemplate) {
      setPages([]);
      setMappings([]);
      return;
    }

    async function loadTemplateData() {
      try {
        setIsLoading(true);
        setSelectedField(null);
        setSelectedBoxId(null);
        setActiveImage(null);
        setCurrentPage(0);

        const [pagesRes, mappingRes] = await Promise.all([
          fetchPdfPages(selectedTemplate),
          fetchTemplateMapping(selectedTemplate).catch(() => ({
            template_id: selectedTemplate,
            page_width: 0,
            page_height: 0,
            mappings: [],
          })),
        ]);

        setPages(pagesRes.pages);
        setMappings(mappingRes.mappings || []);
      } catch (err: any) {
        showToast(`Error al cargar plantilla: ${err.message}`, 'error');
      } finally {
        setIsLoading(false);
      }
    }

    loadTemplateData();
  }, [selectedTemplate]);

  // When selected box changes, sync its style into currentStyle
  useEffect(() => {
    if (selectedBoxId) {
      const box = mappings.find((m) => m.id === selectedBoxId);
      if (box && box.style) {
        setCurrentStyle((prev) => ({
          ...prev,
          font_family: box.style?.font_family || prev.font_family,
          font_size: box.style?.font_size || prev.font_size,
          bold: box.style?.bold ?? prev.bold,
          color: box.style?.color || prev.color,
        }));
      }
    }
  }, [selectedBoxId, mappings]);

  const handleUploadTemplate = async (file: File, isTemp: boolean = false) => {
    try {
      setIsLoading(true);
      const res = await uploadPdfTemplate(file);
      setIsTemporarySession(isTemp);
      
      const updatedTemplates = await fetchTemplates();
      setTemplates(updatedTemplates);
      setSelectedTemplate(res.template_id);

      if (isTemp) {
        showToast(`⚡ Llenado Rápido: "${res.filename}" listo para estampar`, 'info');
      } else {
        showToast(`Plantilla "${res.filename}" subida exitosamente`, 'success');
      }
    } catch (err: any) {
      showToast(`Error al subir archivo: ${err.message}`, 'error');
      setIsLoading(false);
    }
  };

  const executeDeleteTemplate = async (templateId: string) => {
    try {
      setIsLoading(true);
      await deleteTemplate(templateId);
      
      const remaining = templates.filter((t) => t.id !== templateId);
      setTemplates(remaining);

      if (selectedTemplate === templateId) {
        if (remaining.length > 0) {
          setSelectedTemplate(remaining[0].id);
        } else {
          setSelectedTemplate('');
          setPages([]);
          setMappings([]);
        }
      }
      setIsTemporarySession(false);
      showToast('Plantilla y mapeos eliminados exitosamente', 'info');
    } catch (err: any) {
      showToast(`Error al eliminar plantilla: ${err.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Open sleek confirmation dialog for deleting template
  const handleRequestDeleteTemplate = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    const filename = tpl?.filename || templateId;

    setConfirmModalData({
      isOpen: true,
      title: '¿Eliminar plantilla PDF?',
      subtitle: 'Esta acción borrará el documento y sus coordenadas mapeadas.',
      itemName: filename,
      itemMeta: tpl?.size_kb ? `${tpl.size_kb} KB` : undefined,
      confirmText: 'Sí, Eliminar Plantilla',
      type: 'danger',
      onConfirm: () => executeDeleteTemplate(templateId),
    });
  };

  const handleToggleAddText = () => {
    if (selectedField === 'texto_libre') {
      setSelectedField(null);
      showToast('Modo texto desactivado', 'info');
    } else {
      setSelectedField('texto_libre');
      setActiveImage(null);
      setSelectedBoxId(null);
      showToast('✏️ Modo Añadir Texto activo: Haz clic y dibuja un recuadro en el PDF', 'info');
    }
  };

  const handleAddBox = (box: BoxCoords, boxPct: BoxPct, customStyle?: ItemStyle) => {
    const isImage = customStyle?.item_type === 'image';
    const isGlobalSig = isImage && activeImage?.filename === (globalSignature?.filename || 'Firma Global');
    const isFreeText = selectedField === 'texto_libre';
    const fieldKey = isGlobalSig ? 'firma_global' : (isImage ? 'firma_o_imagen' : (isFreeText ? 'texto_personalizado' : (selectedField || 'campo_personalizado')));
    const label = isGlobalSig ? '✍️ Firma Global' : (isImage ? (activeImage?.filename || 'Imagen') : (isFreeText ? 'Texto' : (selectedField || 'Campo')));

    const finalStyle: ItemStyle = {
      ...(customStyle || currentStyle),
      item_type: isImage ? 'image' : 'text',
      custom_text: isFreeText ? (customStyle?.custom_text || 'Nuevo texto') : customStyle?.custom_text,
    };

    const newItem: MappingItem = {
      id: `box-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      field_key: fieldKey,
      label,
      page_number: currentPage,
      box,
      box_pct: boxPct,
      style: finalStyle,
    };

    setMappings((prev) => [...prev, newItem]);
    setSelectedBoxId(newItem.id);

    if (activeImage) {
      showToast(`Estampado "${label}" colocado`, 'success');
      setActiveImage(null);
    } else if (isFreeText) {
      showToast('Texto añadido: edita su contenido en la barra superior', 'success');
      setSelectedField(null);
    } else {
      showToast(`Campo "${fieldKey}" asignado`, 'success');
    }
  };

  const handleUpdateMapping = (id: string, updatedBox: BoxCoords, updatedBoxPct: BoxPct) => {
    setMappings((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, box: updatedBox, box_pct: updatedBoxPct } : m
      )
    );
  };

  const handleDeleteMapping = (id: string) => {
    setMappings((prev) => prev.filter((m) => m.id !== id));
    if (selectedBoxId === id) {
      setSelectedBoxId(null);
    }
  };

  const handleStyleChange = (updates: Partial<ItemStyle>) => {
    setCurrentStyle((prev) => ({ ...prev, ...updates }));
    
    // If a box is selected, apply style directly to it
    if (selectedBoxId) {
      setMappings((prev) =>
        prev.map((m) =>
          m.id === selectedBoxId
            ? { ...m, style: { ...(m.style || {}), ...updates } }
            : m
        )
      );
    }
  };

  const handleTextChange = (newText: string) => {
    if (!selectedBoxId) return;
    setMappings((prev) =>
      prev.map((m) =>
        m.id === selectedBoxId
          ? { ...m, style: { ...(m.style || {}), custom_text: newText } }
          : m
      )
    );
  };

  const handleAddImage = (base64: string, filename: string) => {
    setActiveImage({ base64, filename });
    setSelectedField(null);
    setSelectedBoxId(null);
    showToast(`Imagen "${filename}" lista. Dibuja el marco en el PDF para colocarla`, 'info');
  };

  const handleSelectSignatureToStamp = () => {
    if (!globalSignature) return;
    if (activeImage && activeImage.filename === globalSignature.filename) {
      setActiveImage(null);
      showToast('Modo firma desactivado', 'info');
    } else {
      setActiveImage({
        base64: globalSignature.base64,
        filename: globalSignature.filename,
      });
      setSelectedField(null);
      setSelectedBoxId(null);
      showToast('✍️ Firma Global activa: Dibuja el recuadro sobre el PDF para estamparla', 'info');
    }
  };

  // Open sleek confirmation dialog for clearing mappings
  const handleClearMappings = () => {
    if (mappings.length === 0) return;
    setConfirmModalData({
      isOpen: true,
      title: '¿Borrar todos los recuadros?',
      subtitle: 'Se limpiarán todos los cuadros dibujados para la plantilla actual.',
      confirmText: 'Sí, Limpiar Lienzo',
      type: 'warning',
      onConfirm: () => {
        setMappings([]);
        setSelectedBoxId(null);
        showToast('Mapeos eliminados', 'info');
      },
    });
  };

  const handleSaveMapping = async () => {
    if (!selectedTemplate || pages.length === 0) return;
    try {
      setIsSaving(true);
      const currentPageData = pages[0];
      const payload: TemplateMapping = {
        template_id: selectedTemplate,
        page_width: currentPageData.page_width_pts,
        page_height: currentPageData.page_height_pts,
        mappings,
      };
      await saveTemplateMapping(payload);
      showToast('¡Mapeo guardado correctamente en JSON!', 'success');
    } catch (err: any) {
      showToast(`Error al guardar mapeo: ${err.message}`, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleGeneratePdf = async (isTemp: boolean = false) => {
    if (!selectedTemplate) return;
    try {
      setIsGenerating(true);
      if (pages.length > 0 && !isTemp) {
        const pageData = pages[0];
        const payload: TemplateMapping = {
          template_id: selectedTemplate,
          page_width: pageData.page_width_pts,
          page_height: pageData.page_height_pts,
          mappings,
        };
        await saveTemplateMapping(payload).catch(() => {});
      }

      const res = await generateFilledPdf(selectedTemplate, mappings, isTemp);
      
      setResultModalData({
        filename: res.filename,
        total_placed: res.total_placed,
        is_temporary: isTemp,
      });

      if (isTemp) {
        // Remove from templates list as it was deleted in backend
        setTemplates((prev) => prev.filter((t) => t.id !== selectedTemplate));
        setIsTemporarySession(false);
        showToast('⚡ PDF generado y plantilla temporal eliminada del almacenamiento', 'success');
      } else {
        showToast('¡PDF generado exitosamente!', 'success');
      }
    } catch (err: any) {
      showToast(`Error al generar PDF: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAiFill = async () => {
    if (!selectedTemplate) {
      showToast('Por favor selecciona o sube un PDF primero', 'info');
      return;
    }
    try {
      setIsAiFilling(true);
      showToast('✨ Procesando Autollenado IA con OpenAI / LLM...', 'info');

      const res = await aiFillPdf(selectedTemplate);

      setResultModalData({
        filename: res.filename,
        total_placed: res.total_placed ?? 0,
        is_temporary: false,
      });

      showToast('✨ ¡PDF autollenado con IA exitosamente!', 'success');
    } catch (err: any) {
      showToast(`Error en Autollenado IA: ${err.message}`, 'error');
    } finally {
      setIsAiFilling(false);
    }
  };

  const handleSaveCompanyData = async (
    updatedData: CompanyData, 
    _profiles?: any, 
    signature?: GlobalSignature | null
  ) => {
    try {
      await saveCompanyData(updatedData);
      setCompanyData(updatedData);
      
      if (signature !== undefined) {
        setGlobalSignature(signature);
        if (signature) {
          localStorage.setItem('autoform_global_signature_v1', JSON.stringify(signature));
        } else {
          localStorage.removeItem('autoform_global_signature_v1');
        }
      }
      
      setIsCompanyModalOpen(false);
      showToast('Datos de la empresa guardados correctamente', 'success');
    } catch (err: any) {
      showToast(`Error al guardar datos: ${err.message}`, 'error');
    }
  };

  const activePage = pages[currentPage] || null;
  const selectedBox = mappings.find((m) => m.id === selectedBoxId);
  const selectedBoxText = selectedBox
    ? (selectedBox.style?.custom_text != null && selectedBox.style.custom_text !== ''
        ? selectedBox.style.custom_text 
        : (companyData[selectedBox.field_key] != null ? String(companyData[selectedBox.field_key]) : ''))
    : '';

  const isSignatureActive = !!(
    activeImage && 
    globalSignature && 
    activeImage.filename === globalSignature.filename
  );

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <Navbar 
        templates={templates}
        selectedTemplate={selectedTemplate}
        onSelectTemplate={setSelectedTemplate}
        onUploadTemplate={handleUploadTemplate}
        onDeleteTemplate={handleRequestDeleteTemplate}
        currentPage={currentPage}
        totalPages={pages.length}
        onChangePage={setCurrentPage}
        onSaveMapping={handleSaveMapping}
        onGeneratePdf={handleGeneratePdf}
        onAiFill={handleAiFill}
        onClearMappings={handleClearMappings}
        onOpenCompanyData={() => setIsCompanyModalOpen(true)}
        isSaving={isSaving}
        isGenerating={isGenerating}
        isAiFilling={isAiFilling}
        mappingsCount={mappings.length}
        isTemporarySession={isTemporarySession}
      />

      {/* Secondary Toolbar (Font, Size, Bold, Color, Text Edit, Add Text, Add Image) */}
      <Toolbar 
        currentStyle={currentStyle}
        onStyleChange={handleStyleChange}
        selectedBoxId={selectedBoxId}
        selectedBoxLabel={selectedBox ? (selectedBox.label || selectedBox.field_key) : null}
        selectedBoxText={selectedBoxText}
        onTextChange={handleTextChange}
        onAddText={handleToggleAddText}
        isTextMode={selectedField === 'texto_libre'}
        onAddImage={handleAddImage}
        isImageMode={!!activeImage}
      />

      {/* Toast Alert */}
      {toastMessage && (
        <div className={`toast-notification toast-${toastMessage.type}`}>
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Main Workspace */}
      <div className="workspace-main">
        {/* Left Sidebar (Variables + Global Signature) */}
        <Sidebar 
          companyData={companyData}
          selectedField={selectedField}
          onSelectField={(key) => {
            setActiveImage(null);
            setSelectedField((prev) => (prev === key ? null : key));
          }}
          mappings={mappings}
          currentPage={currentPage}
          onDeleteMapping={handleDeleteMapping}
          globalSignature={globalSignature}
          onSelectSignature={handleSelectSignatureToStamp}
          isSignatureActive={isSignatureActive}
        />

        {/* Center Canvas */}
        <main className="editor-stage">
          {isLoading ? (
            <div className="stage-loading">
              <div className="spinner-large"></div>
              <p>Cargando documento y mapeos...</p>
            </div>
          ) : !activePage ? (
            <div className="canvas-empty-state">
              <p>No hay ninguna plantilla seleccionada. Sube un PDF o selecciona uno en la barra superior.</p>
            </div>
          ) : (
            <PDFCanvas 
              page={activePage}
              selectedField={selectedField}
              activeImage={activeImage}
              currentStyle={currentStyle}
              companyData={companyData}
              mappings={mappings}
              currentPage={currentPage}
              selectedBoxId={selectedBoxId}
              onSelectBox={setSelectedBoxId}
              onAddBox={handleAddBox}
              onUpdateMapping={handleUpdateMapping}
              onDeleteMapping={handleDeleteMapping}
            />
          )}
        </main>
      </div>

      {/* Progressive Disclosure Data Manager Modal (Company, Employer Profiles & Global Signature) */}
      <DataManagerModal 
        isOpen={isCompanyModalOpen}
        onClose={() => setIsCompanyModalOpen(false)}
        initialCompanyData={companyData}
        globalSignature={globalSignature}
        onSaveData={handleSaveCompanyData}
      />

      {/* Generation Result Modal */}
      <ResultModal 
        isOpen={!!resultModalData}
        onClose={() => setResultModalData(null)}
        result={resultModalData}
      />

      {/* Custom Modern Confirmation Modal */}
      {confirmModalData && (
        <ConfirmModal 
          isOpen={confirmModalData.isOpen}
          onClose={() => setConfirmModalData(null)}
          onConfirm={confirmModalData.onConfirm}
          title={confirmModalData.title}
          subtitle={confirmModalData.subtitle}
          itemName={confirmModalData.itemName}
          itemMeta={confirmModalData.itemMeta}
          confirmText={confirmModalData.confirmText}
          type={confirmModalData.type}
        />
      )}
    </div>
  );
};

export default App;

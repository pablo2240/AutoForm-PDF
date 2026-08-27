import React, { useState, useEffect } from 'react';
import type { 
  TemplateInfo, 
  PDFPage, 
  CompanyData, 
  MappingItem, 
  TemplateMapping,
  BoxCoords,
  BoxPct,
  ItemStyle 
} from './types';
import { 
  fetchTemplates, 
  uploadPdfTemplate, 
  fetchPdfPages, 
  fetchCompanyData, 
  saveCompanyData, 
  fetchTemplateMapping, 
  saveTemplateMapping, 
  generateFilledPdf 
} from './api';
import { Navbar } from './components/Navbar';
import { Toolbar } from './components/Toolbar';
import { Sidebar } from './components/Sidebar';
import { PDFCanvas } from './components/PDFCanvas';
import { DataManagerModal } from './components/data-manager/DataManagerModal';
import { ResultModal } from './components/ResultModal';

export const App: React.FC = () => {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [pages, setPages] = useState<PDFPage[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [companyData, setCompanyData] = useState<CompanyData>({});
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  
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
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState<boolean>(false);
  const [resultModalData, setResultModalData] = useState<{ filename: string; total_placed: number } | null>(null);

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
        setTemplates(tplList);
        setCompanyData(compData);

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
    if (!selectedTemplate) return;

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

  const handleUploadTemplate = async (file: File) => {
    try {
      setIsLoading(true);
      const res = await uploadPdfTemplate(file);
      showToast(`Archivo "${res.filename}" subido exitosamente`, 'success');
      const updatedTemplates = await fetchTemplates();
      setTemplates(updatedTemplates);
      setSelectedTemplate(res.template_id);
    } catch (err: any) {
      showToast(`Error al subir archivo: ${err.message}`, 'error');
      setIsLoading(false);
    }
  };

  const handleAddBox = (box: BoxCoords, boxPct: BoxPct, customStyle?: ItemStyle) => {
    const isImage = customStyle?.item_type === 'image';
    const fieldKey = isImage ? 'firma_o_imagen' : (selectedField || 'campo_personalizado');
    const label = isImage ? (activeImage?.filename || 'Imagen / Firma') : (selectedField || 'Campo');

    const newItem: MappingItem = {
      id: `box-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      field_key: fieldKey,
      label,
      page_number: currentPage,
      box,
      box_pct: boxPct,
      style: customStyle || { ...currentStyle },
    };

    setMappings((prev) => [...prev, newItem]);
    setSelectedBoxId(newItem.id);

    if (activeImage) {
      showToast(`Imagen "${activeImage.filename}" estampada`, 'success');
      setActiveImage(null);
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
    showToast(`Imagen cargada. Haz clic y arrastra sobre el PDF para colocarla`, 'info');
  };

  const handleClearMappings = () => {
    if (window.confirm('¿Estás seguro de que deseas borrar todos los cuadros dibujados para esta plantilla?')) {
      setMappings([]);
      setSelectedBoxId(null);
      showToast('Mapeos eliminados', 'info');
    }
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

  const handleGeneratePdf = async () => {
    if (!selectedTemplate) return;
    try {
      setIsGenerating(true);
      if (pages.length > 0) {
        const pageData = pages[0];
        const payload: TemplateMapping = {
          template_id: selectedTemplate,
          page_width: pageData.page_width_pts,
          page_height: pageData.page_height_pts,
          mappings,
        };
        await saveTemplateMapping(payload).catch(() => {});
      }
      const res = await generateFilledPdf(selectedTemplate, mappings);
      setResultModalData({
        filename: res.filename,
        total_placed: res.total_placed,
      });
      showToast('¡PDF generado exitosamente!', 'success');
    } catch (err: any) {
      showToast(`Error al generar PDF: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveCompanyData = async (updatedData: CompanyData, _profiles?: any) => {
    try {
      await saveCompanyData(updatedData);
      setCompanyData(updatedData);
      showToast('Datos de empresa y perfiles actualizados', 'success');
    } catch (err: any) {
      showToast(`Error al guardar datos: ${err.message}`, 'error');
    }
  };

  const activePage = pages[currentPage] || null;
  const selectedBox = mappings.find((m) => m.id === selectedBoxId);
  const selectedBoxText = selectedBox
    ? (selectedBox.style?.custom_text !== undefined 
        ? selectedBox.style.custom_text 
        : String(companyData[selectedBox.field_key] || ''))
    : '';

  return (
    <div className="app-layout">
      {/* Top Navbar */}
      <Navbar 
        templates={templates}
        selectedTemplate={selectedTemplate}
        onSelectTemplate={setSelectedTemplate}
        onUploadTemplate={handleUploadTemplate}
        currentPage={currentPage}
        totalPages={pages.length}
        onChangePage={setCurrentPage}
        onSaveMapping={handleSaveMapping}
        onGeneratePdf={handleGeneratePdf}
        onClearMappings={handleClearMappings}
        onOpenCompanyData={() => setIsCompanyModalOpen(true)}
        isSaving={isSaving}
        isGenerating={isGenerating}
        mappingsCount={mappings.length}
      />

      {/* Secondary Toolbar (Font, Size, Bold, Color, Text Edit, Add Image) */}
      <Toolbar 
        currentStyle={currentStyle}
        onStyleChange={handleStyleChange}
        selectedBoxId={selectedBoxId}
        selectedBoxLabel={selectedBox ? (selectedBox.label || selectedBox.field_key) : null}
        selectedBoxText={selectedBoxText}
        onTextChange={handleTextChange}
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
        {/* Left Sidebar */}
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
        />

        {/* Center Canvas */}
        <main className="editor-stage">
          {isLoading ? (
            <div className="stage-loading">
              <div className="spinner-large"></div>
              <p>Cargando documento y mapeos...</p>
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

      {/* Progressive Disclosure Data Manager Modal (Company & Employer Profiles) */}
      <DataManagerModal 
        isOpen={isCompanyModalOpen}
        onClose={() => setIsCompanyModalOpen(false)}
        initialCompanyData={companyData}
        onSaveData={handleSaveCompanyData}
      />

      {/* Generation Result Modal */}
      <ResultModal 
        isOpen={!!resultModalData}
        onClose={() => setResultModalData(null)}
        result={resultModalData}
      />
    </div>
  );
};

export default App;

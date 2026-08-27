import type { CompanyData, TemplateInfo, PDFPage, TemplateMapping, MappingItem } from './types';

const API_BASE = 'http://localhost:8000';

export async function fetchTemplates(): Promise<TemplateInfo[]> {
  const res = await fetch(`${API_BASE}/api/templates`);
  if (!res.ok) throw new Error('Error al obtener plantillas');
  const data = await res.json();
  return data.templates;
}

export async function uploadPdfTemplate(file: File): Promise<{ template_id: string; filename: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/upload-pdf`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Error al subir PDF');
  return res.json();
}

export async function deleteTemplate(templateId: string): Promise<{ status: string; message: string; deleted: string[] }> {
  const res = await fetch(`${API_BASE}/api/templates/${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar la plantilla');
  }
  return res.json();
}

export async function fetchPdfPages(templateId: string): Promise<{ template_id: string; total_pages: number; pages: PDFPage[] }> {
  const res = await fetch(`${API_BASE}/api/pdf/${encodeURIComponent(templateId)}/pages`);
  if (!res.ok) throw new Error(`Error al renderizar páginas del PDF: ${res.statusText}`);
  return res.json();
}

export async function fetchCompanyData(): Promise<CompanyData> {
  const res = await fetch(`${API_BASE}/api/company-data`);
  if (!res.ok) throw new Error('Error al obtener datos de la empresa');
  return res.json();
}

export async function saveCompanyData(data: CompanyData): Promise<void> {
  const res = await fetch(`${API_BASE}/api/company-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al guardar datos de la empresa');
}

export async function fetchTemplateMapping(templateId: string): Promise<TemplateMapping> {
  const res = await fetch(`${API_BASE}/api/mapping/${encodeURIComponent(templateId)}`);
  if (!res.ok) throw new Error('Error al obtener mapeo');
  return res.json();
}

export async function saveTemplateMapping(mapping: TemplateMapping): Promise<void> {
  const res = await fetch(`${API_BASE}/api/mapping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mapping),
  });
  if (!res.ok) throw new Error('Error al guardar mapeo');
}

export async function generateFilledPdf(
  templateId: string,
  mappings?: MappingItem[],
  isTemporary: boolean = false
): Promise<{ status: string; filename: string; download_url: string; total_placed: number; is_temporary?: boolean }> {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_id: templateId,
      mappings: mappings && mappings.length > 0 ? mappings : undefined,
      is_temporary: isTemporary,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Error al generar el PDF');
  }
  return res.json();
}

export function getDownloadUrl(filename: string): string {
  return `${API_BASE}/api/download/${encodeURIComponent(filename)}`;
}

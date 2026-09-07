import type { CompanyData, TemplateInfo, PDFPage, TemplateMapping, MappingItem } from './types';

//const API_BASE = 'http://localhost:8000';
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

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

export async function aiFillPdf(
  templateId: string
): Promise<{ status: string; filename: string; download_url: string; message: string; total_placed?: number; audit_report?: any }> {
  const res = await fetch(`${API_BASE}/api/ai-fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id: templateId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Error en Autollenado IA');
  }
  return res.json();
}

export function getDownloadUrl(filename: string): string {
  return `${API_BASE}/api/download/${encodeURIComponent(filename)}`;
}

export async function fetchGlobalSignature(): Promise<import('./types').GlobalSignature | null> {
  const res = await fetch(`${API_BASE}/api/signature`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.signature || null;
}

export async function saveGlobalSignature(signature: import('./types').GlobalSignature): Promise<void> {
  const res = await fetch(`${API_BASE}/api/signature`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: signature.base64,
      filename: signature.filename || 'global_signature.png',
      position: signature.position,
      size: signature.size,
    }),
  });
  if (!res.ok) throw new Error('Error al guardar la firma global en el servidor');
}

export async function deleteGlobalSignature(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/signature`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Error al eliminar la firma global');
}

export async function fetchCategorizedCompany(): Promise<import('./types').CategorizedCompanyData> {
  const res = await fetch(`${API_BASE}/api/categorized-company`);
  if (!res.ok) throw new Error('Error al obtener datos categorizados de la empresa');
  return res.json();
}

export async function saveCategorizedCompany(data: import('./types').CategorizedCompanyData): Promise<void> {
  const res = await fetch(`${API_BASE}/api/categorized-company`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al guardar datos categorizados en el servidor');
}

export async function fetchEmployerProfiles(): Promise<import('./types').EmployerProfile[]> {
  const res = await fetch(`${API_BASE}/api/employer-profiles`);
  if (!res.ok) throw new Error('Error al obtener perfiles de empleados');
  return res.json();
}

export async function saveEmployerProfiles(profiles: import('./types').EmployerProfile[]): Promise<void> {
  const res = await fetch(`${API_BASE}/api/employer-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profiles),
  });
  if (!res.ok) throw new Error('Error al guardar perfiles de empleados en el servidor');
}



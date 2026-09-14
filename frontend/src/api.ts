import type { 
  CompanyData, 
  TemplateInfo, 
  PDFPage, 
  TemplateMapping, 
  MappingItem,
  CommercialProfilePublic,
  CommercialProfileAdmin,
  AdminSessionUser,
  CommercialRegisterPayload
} from './types';

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
  isTemporary: boolean = false,
  commercialProfileId?: string
): Promise<{ status: string; filename: string; download_url: string; total_placed: number; is_temporary?: boolean }> {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_id: templateId,
      mappings: mappings && mappings.length > 0 ? mappings : undefined,
      is_temporary: isTemporary,
      commercial_profile_id: commercialProfileId || undefined,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Error al generar el PDF');
  }
  return res.json();
}

export async function aiFillPdf(
  templateId: string,
  commercialProfileId?: string
): Promise<{ status: string; filename: string; download_url: string; message: string; total_placed?: number; audit_report?: any }> {
  const res = await fetch(`${API_BASE}/api/ai-fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      template_id: templateId,
      commercial_profile_id: commercialProfileId || undefined,
    }),
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

// ==========================================
// Commercial Profiles & Admin Auth (ADR-0008)
// ==========================================

export async function fetchPublicCommercialProfiles(): Promise<CommercialProfilePublic[]> {
  const res = await fetch(`${API_BASE}/api/commercial-profiles`);
  if (!res.ok) throw new Error('Error al obtener perfiles comerciales');
  return res.json();
}

export async function adminLogin(
  email: string, 
  password: string
): Promise<AdminSessionUser & { status: string; token: string }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al iniciar sesión');
  }
  return res.json();
}

export async function registerCommercial(
  payload: CommercialRegisterPayload
): Promise<AdminSessionUser & { status: string; token: string }> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al registrar el perfil comercial');
  }
  return res.json();
}

export async function adminCheck(): Promise<AdminSessionUser> {
  const res = await fetch(`${API_BASE}/api/auth/check`, {
    credentials: 'include',
  });
  if (!res.ok) {
    return { authenticated: false };
  }
  return res.json();
}

export async function adminLogout(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Error al cerrar sesión');
}

export async function fetchAdminCommercialProfiles(): Promise<CommercialProfileAdmin[]> {
  const res = await fetch(`${API_BASE}/api/admin/commercial-profiles`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al obtener perfiles administrativos');
  }
  return res.json();
}

export async function createCommercialProfile(
  data: Partial<CommercialProfileAdmin> & { password?: string }
): Promise<CommercialProfileAdmin> {
  const res = await fetch(`${API_BASE}/api/admin/commercial-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear perfil comercial');
  }
  return res.json();
}

export async function updateCommercialProfile(
  id: string,
  data: Partial<CommercialProfileAdmin> & { password?: string }
): Promise<CommercialProfileAdmin> {
  const res = await fetch(`${API_BASE}/api/admin/commercial-profiles/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al actualizar perfil comercial');
  }
  return res.json();
}

export async function deleteCommercialProfile(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/commercial-profiles/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar perfil comercial');
  }
}



export interface CompanyData {
  [key: string]: string | number;
}

export type CompanyCategory = 'id' | 'contacto' | 'banco' | 'otros';

export interface CompanyFieldItem {
  id: string;
  key: string;
  label: string;
  value: string;
  category: CompanyCategory;
}

export interface CustomFieldItem {
  id: string;
  key: string;
  value: string;
}

export interface EmployerProfile {
  id: string;
  profileName: string;
  nombre: string;
  apellido: string;
  email: string;
  celular: string;
  customFields: CustomFieldItem[];
}

export interface CategorizedCompanyData {
  id: CompanyFieldItem[];
  contacto: CompanyFieldItem[];
  banco: CompanyFieldItem[];
  otros: CompanyFieldItem[];
}

export interface TemplateInfo {
  id: string;
  filename: string;
  size_kb: number;
}

export interface PDFPage {
  page_num: number;
  width_px: number;
  height_px: number;
  page_width_pts: number;
  page_height_pts: number;
  image_base64: string;
}

export interface BoxCoords {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface BoxPct {
  x0_pct: number;
  y0_pct: number;
  x1_pct: number;
  y1_pct: number;
}

export interface ItemStyle {
  font_family?: string;
  font_size?: number;
  bold?: boolean;
  color?: string;
  custom_text?: string;
  image_base64?: string;
  item_type?: 'text' | 'image';
}

export interface MappingItem {
  id: string;
  field_key: string;
  label?: string;
  page_number: number;
  box: BoxCoords;
  box_pct?: BoxPct;
  style?: ItemStyle;
}

export interface TemplateMapping {
  template_id: string;
  page_width: number;
  page_height: number;
  mappings: MappingItem[];
}

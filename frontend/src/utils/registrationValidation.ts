/**
 * Pure validation rules for commercial user registration.
 *
 * Rules:
 * - Nombre & Apellido: Letters, accents, spaces only; minimum 4 characters.
 * - Cargo: Alphanumeric and spaces; minimum 5 characters.
 * - Celular: Numeric only; exactly 10 digits.
 * - Cédula: Numeric only; between 8 and 11 digits.
 * - Ciudad: Letters, accents, spaces, dot and hyphen; minimum 3 characters.
 * - Email: Corporate domains @iaclatam.com or @iac.com.co only.
 * - Password: Minimum 6 characters.
 */

export const CORPORATE_EMAIL_REGEX = /^[^@\s]+@(iaclatam\.com|iac\.com\.co)$/i;
export const NAME_REGEX = /^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$/;
export const CARGO_REGEX = /^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$/;
export const CIUDAD_REGEX = /^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$/;

export interface ValidationResult {
  isValid: boolean;
  error?: string;
}

export function validateName(val: string, fieldLabel = 'El nombre'): ValidationResult {
  const trimmed = val.trim();
  if (!trimmed) {
    return { isValid: false, error: `${fieldLabel} es obligatorio.` };
  }
  if (trimmed.length < 4) {
    return { isValid: false, error: `${fieldLabel} debe tener al menos 4 caracteres.` };
  }
  if (!NAME_REGEX.test(trimmed)) {
    return { isValid: false, error: `${fieldLabel} debe contener únicamente letras y espacios.` };
  }
  return { isValid: true };
}

export function validateCargo(val: string): ValidationResult {
  const trimmed = val.trim();
  if (!trimmed) {
    return { isValid: false, error: 'El cargo es obligatorio.' };
  }
  if (trimmed.length < 5) {
    return { isValid: false, error: 'El cargo debe tener al menos 5 caracteres.' };
  }
  if (!CARGO_REGEX.test(trimmed)) {
    return { isValid: false, error: 'El cargo contiene caracteres no permitidos.' };
  }
  return { isValid: true };
}

export function validateCelular(val: string): ValidationResult {
  const trimmed = val.trim();
  if (!trimmed) {
    return { isValid: false, error: 'El celular es obligatorio.' };
  }
  if (!/^\d+$/.test(trimmed)) {
    return { isValid: false, error: 'El número de celular debe contener únicamente números.' };
  }
  if (trimmed.length !== 10) {
    return { isValid: false, error: 'El celular debe tener exactamente 10 dígitos.' };
  }
  return { isValid: true };
}

export function validateCedula(val: string): ValidationResult {
  const trimmed = val.trim();
  if (!trimmed) {
    return { isValid: false, error: 'La cédula es obligatoria.' };
  }
  if (!/^\d+$/.test(trimmed)) {
    return { isValid: false, error: 'La cédula debe contener únicamente números.' };
  }
  if (trimmed.length < 8 || trimmed.length > 11) {
    return { isValid: false, error: 'La cédula debe contener entre 8 y 11 dígitos.' };
  }
  return { isValid: true };
}

export function validateCiudad(val: string): ValidationResult {
  const trimmed = val.trim();
  if (!trimmed) {
    return { isValid: false, error: 'La ciudad es obligatoria.' };
  }
  if (trimmed.length < 3) {
    return { isValid: false, error: 'La ciudad debe tener al menos 3 caracteres.' };
  }
  if (!CIUDAD_REGEX.test(trimmed)) {
    return { isValid: false, error: 'La ciudad debe contener únicamente letras, espacios, punto o guion.' };
  }
  return { isValid: true };
}

export function validateCorporateEmail(val: string): ValidationResult {
  const trimmed = val.trim().toLowerCase();
  if (!trimmed) {
    return { isValid: false, error: 'El correo electrónico es obligatorio.' };
  }
  if (!CORPORATE_EMAIL_REGEX.test(trimmed)) {
    return {
      isValid: false,
      error: 'Solo se permiten correos corporativos (@iaclatam.com o @iac.com.co).'
    };
  }
  return { isValid: true };
}

export function validatePassword(val: string): ValidationResult {
  if (!val || val.length < 8) {
    return { isValid: false, error: 'La contraseña debe tener al menos 8 caracteres.' };
  }
  return { isValid: true };
}

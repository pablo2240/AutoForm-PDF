import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateName,
  validateCargo,
  validateCelular,
  validateCedula,
  validateCiudad,
  validateCorporateEmail,
  validatePassword
} from '../src/utils/registrationValidation.ts';

test('validateName accepts valid names and rejects invalid names', () => {
  assert.strictEqual(validateName('Kelly').isValid, true);
  assert.strictEqual(validateName('Juan Carlos').isValid, true);
  assert.strictEqual(validateName('María José').isValid, true);

  // Rejects less than 4 chars
  assert.strictEqual(validateName('Ana').isValid, false);
  assert.strictEqual(validateName('  Lu  ').isValid, false);

  // Rejects digits and symbols
  assert.strictEqual(validateName('Kelly123').isValid, false);
  assert.strictEqual(validateName('Carlos@').isValid, false);
});

test('validateCargo accepts valid cargo and rejects invalid', () => {
  assert.strictEqual(validateCargo('Asesor Comercial').isValid, true);
  assert.strictEqual(validateCargo('Líder').isValid, true);
  assert.strictEqual(validateCargo('Líder de Ventas 1').isValid, true);

  // Rejects less than 5 chars
  assert.strictEqual(validateCargo('Jefe').isValid, false);
  assert.strictEqual(validateCargo('Adm').isValid, false);
});

test('validateCelular accepts exactly 10 digits and rejects others', () => {
  assert.strictEqual(validateCelular('3014750760').isValid, true);
  assert.strictEqual(validateCelular('3201234567').isValid, true);

  // Rejects less than 10 or more than 10
  assert.strictEqual(validateCelular('301475076').isValid, false);
  assert.strictEqual(validateCelular('30147507601').isValid, false);

  // Rejects non-digits
  assert.strictEqual(validateCelular('301-475076').isValid, false);
  assert.strictEqual(validateCelular('301475076a').isValid, false);
});

test('validateCedula accepts between 8 and 11 digits', () => {
  assert.strictEqual(validateCedula('12345678').isValid, true);
  assert.strictEqual(validateCedula('1017123456').isValid, true);
  assert.strictEqual(validateCedula('12345678901').isValid, true);

  // Rejects less than 8 or more than 11
  assert.strictEqual(validateCedula('1234567').isValid, false);
  assert.strictEqual(validateCedula('123456789012').isValid, false);

  // Rejects non-digits
  assert.strictEqual(validateCedula('10171234A').isValid, false);
});

test('validateCiudad accepts valid city names and rejects invalid', () => {
  assert.strictEqual(validateCiudad('Bogotá').isValid, true);
  assert.strictEqual(validateCiudad('Medellín').isValid, true);
  assert.strictEqual(validateCiudad('Cali').isValid, true);
  assert.strictEqual(validateCiudad('San Juan de Pasto').isValid, true);
  assert.strictEqual(validateCiudad('Bogotá D.C.').isValid, true);

  // Rejects less than 3 chars
  assert.strictEqual(validateCiudad('Bo').isValid, false);

  // Rejects numbers and special symbols
  assert.strictEqual(validateCiudad('Medellin1').isValid, false);
  assert.strictEqual(validateCiudad('Cali#').isValid, false);
});

test('validateCorporateEmail accepts @iaclatam.com and @iac.com.co and rejects other domains', () => {
  assert.strictEqual(validateCorporateEmail('kelly.delgado@iaclatam.com').isValid, true);
  assert.strictEqual(validateCorporateEmail('JUAN.PEREZ@IAC.COM.CO').isValid, true);
  assert.strictEqual(validateCorporateEmail('asesor@iaclatam.com').isValid, true);

  // Rejects public/other domains
  assert.strictEqual(validateCorporateEmail('asesor@gmail.com').isValid, false);
  assert.strictEqual(validateCorporateEmail('asesor@hotmail.com').isValid, false);
  assert.strictEqual(validateCorporateEmail('asesor@iac.com').isValid, false);
  assert.strictEqual(validateCorporateEmail('not-an-email').isValid, false);
});

test('validatePassword accepts at least 8 characters', () => {
  assert.strictEqual(validatePassword('12345678').isValid, true);
  assert.strictEqual(validatePassword('SecurePassword2026').isValid, true);

  // Rejects less than 8 chars
  assert.strictEqual(validatePassword('1234567').isValid, false);
  assert.strictEqual(validatePassword('short').isValid, false);
  assert.strictEqual(validatePassword('').isValid, false);
});

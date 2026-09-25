import React, { useState } from 'react';
import logoIac from '../../assets/logo_iac.png';
import {
  Lock,
  Mail,
  Building,
  KeyRound,
  AlertCircle,
  Eye,
  EyeOff,
  UserCheck,
  UserPlus,
  CheckCircle2,
  ArrowLeft,
  User,
  Briefcase,
  Phone,
  CreditCard,
  MapPin
} from 'lucide-react';
import { adminLogin, registerCommercial, checkEmailAvailability } from '../../api';
import { supabase } from '../../supabaseClient';
import type { AdminSessionUser } from '../../types';
import {
  validateName,
  validateCargo,
  validateCelular,
  validateCedula,
  validateCiudad,
  validateCorporateEmail,
  validatePassword
} from '../../utils/registrationValidation';
import './AuthPortal.css';

interface AuthPortalProps {
  onAuthenticated: (user: AdminSessionUser) => void;
}

export const AuthPortal: React.FC<AuthPortalProps> = ({ onAuthenticated }) => {
  const [view, setView] = useState<'login' | 'register' | 'recovery'>('login');
  
  // Login State
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Registration State
  const [regNombre, setRegNombre] = useState('');
  const [regApellido, setRegApellido] = useState('');
  const [regCedula, setRegCedula] = useState('');
  const [regCelular, setRegCelular] = useState('');
  const [regCiudad, setRegCiudad] = useState('');
  const [regCargo, setRegCargo] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);

  // Password Recovery State
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [isSendingRecovery, setIsSendingRecovery] = useState(false);
  const [recoverySuccess, setRecoverySuccess] = useState<string | null>(null);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);

    const emailTrim = loginEmail.trim();
    if (!emailTrim || !loginPassword) {
      setLoginError('Por favor ingresa tu correo corporativo y contraseña.');
      return;
    }

    try {
      setIsLoggingIn(true);
      const res = await adminLogin(emailTrim, loginPassword);
      onAuthenticated(res);
    } catch (err: any) {
      setLoginError(err.message || 'Credenciales incorrectas o usuario inactivo.');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleEmailBlur = async () => {
    const vEmail = validateCorporateEmail(regEmail);
    if (!vEmail.isValid) {
      setEmailAvailable(null);
      return;
    }
    try {
      setEmailChecking(true);
      const res = await checkEmailAvailability(regEmail.trim().toLowerCase());
      setEmailAvailable(res.available);
      if (!res.available) {
        setRegError(`El correo ${regEmail.trim().toLowerCase()} ya se encuentra registrado.`);
      } else {
        if (regError?.includes('ya se encuentra registrado')) {
          setRegError(null);
        }
      }
    } catch {
      setEmailAvailable(null);
    } finally {
      setEmailChecking(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);

    // Client-side validations
    const vNombre = validateName(regNombre, 'El nombre');
    if (!vNombre.isValid) { setRegError(vNombre.error!); return; }

    const vApellido = validateName(regApellido, 'El apellido');
    if (!vApellido.isValid) { setRegError(vApellido.error!); return; }

    const vCedula = validateCedula(regCedula);
    if (!vCedula.isValid) { setRegError(vCedula.error!); return; }

    const vCelular = validateCelular(regCelular);
    if (!vCelular.isValid) { setRegError(vCelular.error!); return; }

    const vCiudad = validateCiudad(regCiudad);
    if (!vCiudad.isValid) { setRegError(vCiudad.error!); return; }

    const vCargo = validateCargo(regCargo);
    if (!vCargo.isValid) { setRegError(vCargo.error!); return; }

    const vEmail = validateCorporateEmail(regEmail);
    if (!vEmail.isValid) { setRegError(vEmail.error!); return; }

    const vPass = validatePassword(regPassword);
    if (!vPass.isValid) { setRegError(vPass.error!); return; }

    try {
      setIsRegistering(true);
      const res = await registerCommercial({
        nombre: regNombre.trim(),
        apellido: regApellido.trim(),
        documento_identidad: regCedula.trim(),
        celular: regCelular.trim(),
        ciudad: regCiudad.trim(),
        cargo: regCargo.trim(),
        email: regEmail.trim().toLowerCase(),
        password: regPassword.trim(),
        tipo_documento: 'CC'
      });
      // Direct session issuance - enters workspace immediately
      onAuthenticated(res);
    } catch (err: any) {
      setRegError(err.message || 'Error al completar el registro.');
    } finally {
      setIsRegistering(false);
    }
  };

  const handleRecoverySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRecoveryError(null);
    setRecoverySuccess(null);

    const emailClean = recoveryEmail.trim().toLowerCase();
    if (!emailClean || !emailClean.includes('@')) {
      setRecoveryError('Por favor ingresa un correo corporativo válido.');
      return;
    }

    const domainMatch = /^[^@\s]+@(iaclatam\.com|iac\.com\.co)$/i.test(emailClean);
    if (!domainMatch) {
      setRecoveryError('El correo debe pertenecer a un dominio corporativo autorizado (@iaclatam.com o @iac.com.co).');
      return;
    }

    try {
      setIsSendingRecovery(true);
      const siteOrigin = window.location.origin;
      await supabase.auth.resetPasswordForEmail(emailClean, {
        redirectTo: `${siteOrigin}/auth/reset-password`
      });
      setRecoverySuccess(
        'Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso.'
      );
    } catch {
      setRecoverySuccess(
        'Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso.'
      );
    } finally {
      setIsSendingRecovery(false);
    }
  };

  return (
    <div className="auth-portal-page">
      <div className={`auth-portal-layout ${view === 'register' ? 'layout-register-expanded' : ''}`}>
        {/* ========================================================= */}
        {/* LEFT COLUMN: Industrial Technical Engine Showcase        */}
        {/* ========================================================= */}
        <aside className="auth-showcase-column">
          <div className="showcase-brand-header">
            <div className="showcase-logo-badge">
              <img src={logoIac} alt="IAC Latam" className="showcase-iac-logo" />
            </div>
            <div>
              <h1 className="showcase-app-name">AutoForm PDF</h1>
              <p className="showcase-company-tag">Ingeniería Asistida Por Computador S.A.S</p>
            </div>
          </div>

          <div className="showcase-hero-content">
            <div className="showcase-status-badge">
              <Building size={13} />
              <span>Plataforma Corporativa de Llenado Automatizado</span>
            </div>

            <h2 className="showcase-headline">
              Diligenciamiento Inteligente de Formularios para Operaciones Comerciales
            </h2>

            <p className="showcase-lead">
              Motor de correspondencia semántica y superposición visual de alta precisión para vinculación de clientes, proveedores y contrapartes.
            </p>

            <div className="showcase-metric-cards">
              <div className="metric-card">
                <span className="metric-val">+22</span>
                <span className="metric-lbl">Reglas Semánticas</span>
              </div>
              <div className="metric-card">
                <span className="metric-val">100%</span>
                <span className="metric-lbl">Cumplimiento Legal</span>
              </div>
              <div className="metric-card">
                <span className="metric-val">0</span>
                <span className="metric-lbl">Pérdida de Calidad</span>
              </div>
            </div>

            <div className="sample-profile-chip">
              <div className="sample-chip-header">
                <span className="chip-indicator" />
                <span className="chip-title">Entorno Autoritativo Activo</span>
              </div>
              <div className="sample-chip-body">
                <div className="sample-field-row">
                  <span className="sample-field-label">Razón Social</span>
                  <span className="sample-field-val">Ingeniería Asistida Por Computador S.A.S</span>
                </div>
                <div className="sample-field-row">
                  <span className="sample-field-label">NIT</span>
                  <span className="sample-field-val">811.004.721-2</span>
                </div>
                <div className="sample-field-row">
                  <span className="sample-field-label">Representante Legal</span>
                  <span className="sample-field-val">Guillermo Humberto Cañón Sarria</span>
                </div>
                <div className="sample-field-row">
                  <span className="sample-field-label">Cédula de Contacto</span>
                  <span className="sample-field-val masked">CC ••••••••</span>
                </div>
              </div>
            </div>
          </div>

          <footer className="showcase-footer">
            <span>© 2026 IAC Latam · Seguridad y Precisión Documental</span>
          </footer>
        </aside>

        {/* ========================================================= */}
        {/* RIGHT COLUMN: Authentication Console                     */}
        {/* ========================================================= */}
        <main className="auth-form-column">
          <div className={`auth-form-card ${view === 'register' ? 'card-register-expanded' : ''}`}>

            {/* View Switching Navigation (Login / Register Tabs) */}
            {view !== 'recovery' && (
              <div className="auth-tabs-nav">
                <button
                  type="button"
                  className={`auth-tab-btn ${view === 'login' ? 'active' : ''}`}
                  onClick={() => {
                    setView('login');
                    setLoginError(null);
                  }}
                >
                  <UserCheck size={16} />
                  <span>Iniciar Sesión</span>
                </button>
                <button
                  type="button"
                  className={`auth-tab-btn ${view === 'register' ? 'active' : ''}`}
                  onClick={() => {
                    setView('register');
                    setRegError(null);
                  }}
                >
                  <UserPlus size={16} />
                  <span>Crear Cuenta</span>
                </button>
              </div>
            )}

            {/* =================================================== */}
            {/* VIEW: LOGIN                                         */}
            {/* =================================================== */}
            {view === 'login' && (
              <div className="auth-view-container view-fade-in" key="view-login">
                <div className="auth-view-header">
                  <div className="auth-view-header-badge">
                    <KeyRound size={13} />
                    <span>Portal Corporativo</span>
                  </div>
                  <h3>Acceso de Responsables</h3>
                  <p>Ingresa con tu correo corporativo y contraseña para acceder al espacio de trabajo.</p>
                </div>

                {loginError && (
                  <div className="auth-alert alert-error" role="alert">
                    <AlertCircle size={16} />
                    <span>{loginError}</span>
                  </div>
                )}

                <form onSubmit={handleLoginSubmit} className="auth-form">
                  <div className="auth-field">
                    <label htmlFor="loginEmail">Correo Corporativo</label>
                    <div className="auth-input-wrapper">
                      <Mail size={17} className="auth-input-icon" />
                      <input
                        id="loginEmail"
                        type="email"
                        required
                        autoComplete="email"
                        placeholder="ejemplo@iaclatam.com"
                        value={loginEmail}
                        onChange={(e) => setLoginEmail(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="auth-field">
                    <div className="field-label-row">
                      <label htmlFor="loginPassword">Contraseña</label>
                      <button
                        type="button"
                        className="auth-link-button text-xs"
                        onClick={() => {
                          setRecoveryEmail(loginEmail);
                          setRecoverySuccess(null);
                          setRecoveryError(null);
                          setView('recovery');
                        }}
                      >
                        ¿Olvidaste tu contraseña?
                      </button>
                    </div>
                    <div className="auth-input-wrapper">
                      <Lock size={17} className="auth-input-icon" />
                      <input
                        id="loginPassword"
                        type={showLoginPassword ? 'text' : 'password'}
                        required
                        autoComplete="current-password"
                        placeholder="••••••••"
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn-toggle-eye"
                        onClick={() => setShowLoginPassword(!showLoginPassword)}
                        title={showLoginPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                      >
                        {showLoginPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-auth-primary"
                    disabled={isLoggingIn}
                  >
                    {isLoggingIn ? (
                      <>
                        <span className="auth-spinner" />
                        <span>Verificando credenciales...</span>
                      </>
                    ) : (
                      <>
                        <UserCheck size={18} />
                        <span>Ingresar al Espacio de Trabajo</span>
                      </>
                    )}
                  </button>
                </form>

                <div className="auth-card-footer">
                  <p>
                    ¿Eres nuevo asesor comercial?{' '}
                    <button
                      type="button"
                      className="auth-link-button"
                      onClick={() => {
                        setView('register');
                        setRegError(null);
                      }}
                    >
                      Regístrate aquí
                    </button>
                  </p>
                </div>
              </div>
            )}

            {/* =================================================== */}
            {/* VIEW: REGISTER                                      */}
            {/* =================================================== */}
            {view === 'register' && (
              <div className="auth-view-container view-fade-in" key="view-register">
                <div className="auth-view-header">
                  <div className="auth-view-header-badge">
                    <UserPlus size={13} />
                    <span>Registro Comercial</span>
                  </div>
                  <h3>Nueva Cuenta de Asesor</h3>
                  <p>Completa tus datos corporativos para habilitar tu cuenta comercial de forma inmediata.</p>
                </div>

                {regError && (
                  <div className="auth-alert alert-error" role="alert">
                    <AlertCircle size={16} />
                    <span>{regError}</span>
                  </div>
                )}

                <form onSubmit={handleRegisterSubmit} className="auth-form reg-grid-form">
                  <div className="form-row-2col">
                    <div className="auth-field">
                      <label htmlFor="regNombre">Nombres *</label>
                      <div className="auth-input-wrapper">
                        <User size={17} className="auth-input-icon" />
                        <input
                          id="regNombre"
                          type="text"
                          required
                          placeholder="Mínimo 4 letras"
                          value={regNombre}
                          onChange={(e) => setRegNombre(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="auth-field">
                      <label htmlFor="regApellido">Apellidos *</label>
                      <div className="auth-input-wrapper">
                        <User size={17} className="auth-input-icon" />
                        <input
                          id="regApellido"
                          type="text"
                          required
                          placeholder="Mínimo 4 letras"
                          value={regApellido}
                          onChange={(e) => setRegApellido(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="form-row-2col">
                    <div className="auth-field">
                      <label htmlFor="regCedula">Cédula de Ciudadanía *</label>
                      <div className="auth-input-wrapper">
                        <CreditCard size={17} className="auth-input-icon" />
                        <input
                          id="regCedula"
                          type="text"
                          required
                          maxLength={11}
                          placeholder="8 a 11 dígitos"
                          value={regCedula}
                          onChange={(e) => setRegCedula(e.target.value.replace(/\D/g, ''))}
                        />
                      </div>
                    </div>

                    <div className="auth-field">
                      <label htmlFor="regCelular">Celular de Contacto *</label>
                      <div className="auth-input-wrapper">
                        <Phone size={17} className="auth-input-icon" />
                        <input
                          id="regCelular"
                          type="tel"
                          required
                          maxLength={10}
                          placeholder="10 dígitos (3XXXXXXXXX)"
                          value={regCelular}
                          onChange={(e) => setRegCelular(e.target.value.replace(/\D/g, ''))}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="form-row-2col">
                    <div className="auth-field">
                      <label htmlFor="regCiudad">Ciudad *</label>
                      <div className="auth-input-wrapper">
                        <MapPin size={17} className="auth-input-icon" />
                        <input
                          id="regCiudad"
                          type="text"
                          required
                          placeholder="Ej. Bogotá, Medellín"
                          value={regCiudad}
                          onChange={(e) => setRegCiudad(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="auth-field">
                      <label htmlFor="regCargo">Cargo Corporativo *</label>
                      <div className="auth-input-wrapper">
                        <Briefcase size={17} className="auth-input-icon" />
                        <input
                          id="regCargo"
                          type="text"
                          required
                          placeholder="Ej. Asesor Comercial"
                          value={regCargo}
                          onChange={(e) => setRegCargo(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="auth-field">
                    <div className="field-label-row">
                      <label htmlFor="regEmail">Correo Corporativo (@iaclatam.com o @iac.com.co) *</label>
                      {emailChecking && <span className="text-xs text-muted">Comprobando disponibilidad...</span>}
                      {emailAvailable === true && <span className="text-xs text-success font-medium">✓ Disponible</span>}
                      {emailAvailable === false && <span className="text-xs text-danger font-medium">✗ No disponible</span>}
                    </div>
                    <div className="auth-input-wrapper">
                      <Mail size={17} className="auth-input-icon" />
                      <input
                        id="regEmail"
                        type="email"
                        required
                        autoComplete="email"
                        placeholder="tu.nombre@iaclatam.com"
                        value={regEmail}
                        onChange={(e) => {
                          setRegEmail(e.target.value);
                          setEmailAvailable(null);
                        }}
                        onBlur={handleEmailBlur}
                      />
                    </div>
                  </div>

                  <div className="auth-field">
                    <label htmlFor="regPassword">Contraseña de Acceso *</label>
                    <div className="auth-input-wrapper">
                      <Lock size={17} className="auth-input-icon" />
                      <input
                        id="regPassword"
                        type={showRegPassword ? 'text' : 'password'}
                        required
                        autoComplete="new-password"
                        placeholder="Mínimo 12 caracteres"
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn-toggle-eye"
                        onClick={() => setShowRegPassword(!showRegPassword)}
                        title={showRegPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                      >
                        {showRegPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-auth-primary"
                    disabled={isRegistering}
                  >
                    {isRegistering ? (
                      <>
                        <span className="auth-spinner" />
                        <span>Registrando y habilitando acceso...</span>
                      </>
                    ) : (
                      <>
                        <UserPlus size={18} />
                        <span>Crear Cuenta y Acceder</span>
                      </>
                    )}
                  </button>
                </form>

                <div className="auth-card-footer">
                  <p>
                    ¿Ya tienes una cuenta comercial?{' '}
                    <button
                      type="button"
                      className="auth-link-button"
                      onClick={() => {
                        setView('login');
                        setLoginError(null);
                      }}
                    >
                      Inicia sesión aquí
                    </button>
                  </p>
                </div>
              </div>
            )}

            {/* =================================================== */}
            {/* VIEW: PASSWORD RECOVERY                             */}
            {/* =================================================== */}
            {view === 'recovery' && (
              <div className="auth-view-container view-fade-in" key="view-recovery">
                <button
                  type="button"
                  className="auth-back-link"
                  onClick={() => {
                    setView('login');
                    setRecoveryError(null);
                    setRecoverySuccess(null);
                  }}
                >
                  <ArrowLeft size={15} />
                  <span>Volver a Iniciar Sesión</span>
                </button>

                <div className="auth-view-header">
                  <div className="auth-view-header-badge badge-amber">
                    <KeyRound size={13} />
                    <span>Recuperación de Contraseña</span>
                  </div>
                  <h3>Restablecer Contraseña</h3>
                  <p>
                    Ingresa tu correo corporativo (@iaclatam.com o @iac.com.co). Te enviaremos un enlace seguro para crear o actualizar tu contraseña de acceso.
                  </p>
                </div>

                {recoverySuccess && (
                  <div className="auth-alert alert-success" role="alert">
                    <CheckCircle2 size={16} />
                    <span>{recoverySuccess}</span>
                  </div>
                )}

                {recoveryError && (
                  <div className="auth-alert alert-error" role="alert">
                    <AlertCircle size={16} />
                    <span>{recoveryError}</span>
                  </div>
                )}

                <form onSubmit={handleRecoverySubmit} className="auth-form">
                  <div className="auth-field">
                    <label htmlFor="recoveryEmail">Correo Corporativo</label>
                    <div className="auth-input-wrapper">
                      <Mail size={17} className="auth-input-icon" />
                      <input
                        id="recoveryEmail"
                        type="email"
                        required
                        autoComplete="email"
                        placeholder="nombre.apellido@iaclatam.com"
                        value={recoveryEmail}
                        onChange={(e) => setRecoveryEmail(e.target.value)}
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-auth-primary"
                    disabled={isSendingRecovery}
                  >
                    {isSendingRecovery ? (
                      <>
                        <span className="auth-spinner" />
                        <span>Enviando enlace seguro...</span>
                      </>
                    ) : (
                      <>
                        <Mail size={18} />
                        <span>Enviar Enlace de Recuperación</span>
                      </>
                    )}
                  </button>
                </form>

                <div className="auth-card-footer">
                  <p>
                    ¿Recordaste tu contraseña?{' '}
                    <button
                      type="button"
                      className="auth-link-button"
                      onClick={() => {
                        setView('login');
                        setRecoveryError(null);
                        setRecoverySuccess(null);
                      }}
                    >
                      Inicia sesión aquí
                    </button>
                  </p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

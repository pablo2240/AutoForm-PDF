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
  FileText, 
  ShieldAlert,
  CheckCircle2,
  ArrowLeft
} from 'lucide-react';
import { adminLogin } from '../../api';
import { supabase } from '../../supabaseClient';
import type { AdminSessionUser } from '../../types';
import './AuthPortal.css';

interface AuthPortalProps {
  onAuthenticated: (user: AdminSessionUser) => void;
}

export const AuthPortal: React.FC<AuthPortalProps> = ({ onAuthenticated }) => {
  const [view, setView] = useState<'login' | 'recovery'>('login');
  
  // Login State
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

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

  const handleRecoverySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRecoveryError(null);
    setRecoverySuccess(null);

    const emailClean = recoveryEmail.trim().toLowerCase();
    if (!emailClean || !emailClean.includes('@')) {
      setRecoveryError('Por favor ingresa un correo corporativo válido.');
      return;
    }

    // Validación estricta de dominios corporativos autorizados
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
      // Respuesta genérica para evitar enumeración de usuarios
      setRecoverySuccess(
        'Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso.'
      );
    } catch {
      // Mantener respuesta genérica consistente
      setRecoverySuccess(
        'Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso.'
      );
    } finally {
      setIsSendingRecovery(false);
    }
  };

  return (
    <div className="auth-portal-page">
      <div className="auth-portal-layout">
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
              <span>Plataforma Oficial de Diligenciamiento</span>
            </div>

            <h2 className="showcase-headline">
              Diligenciamiento de formularios con aislamiento consciente de contacto.
            </h2>
            <p className="showcase-subtext">
              Herramienta diseñada para el equipo comercial de IAC. Rellena formularios de clientes 
              y licitaciones con precisión milimétrica, protegiendo los datos estatutarios del Representante Legal.
            </p>

            {/* Document Diligence Artifact Preview */}
            <div className="showcase-sample-card">
              <div className="sample-card-header">
                <FileText size={15} className="sample-doc-icon" />
                <span className="sample-card-title">Mapeo Inteligente de Formulario</span>
                <span className="sample-card-tag">AcroForm + Visual</span>
              </div>
              <div className="sample-card-body">
                <div className="sample-field-row">
                  <span className="sample-field-label">Representante Legal (Estatutario)</span>
                  <span className="sample-field-val statutory">Guillermo Humberto Cañón Sarria</span>
                </div>
                <div className="sample-field-row">
                  <span className="sample-field-label">Persona de Contacto Comercial</span>
                  <span className="sample-field-val dynamic">
                    Responsable Asignado Dinámicamente
                  </span>
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
          <div className="auth-form-card">
            {view === 'login' ? (
              <div className="auth-view-container view-fade-in" key="view-login">
                <div className="auth-view-header">
                  <div className="auth-view-header-badge">
                    <KeyRound size={13} />
                    <span>Portal Corporativo</span>
                  </div>
                  <h3>Acceso de Responsables</h3>
                  <p>Ingresa con tu correo corporativo y contraseña para acceder al espacio de trabajo y plantillas.</p>
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

                {/* Corporate Account Policy Notice */}
                <div className="auth-corporate-policy-banner">
                  <div className="policy-banner-icon">
                    <ShieldAlert size={18} />
                  </div>
                  <div className="policy-banner-text">
                    <strong>Acceso Administrado Corporativamente</strong>
                    <p>
                      Las cuentas de acceso son creadas y autorizadas exclusivamente por el administrador corporativo.
                      Si requieres acceso o activación de cuenta, contacta al área administrativa de IAC Latam.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              /* =================================================== */
              /* VIEW: PASSWORD RECOVERY                             */
              /* =================================================== */
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

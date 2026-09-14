import React, { useState } from 'react';
import logoIac from '../../assets/logo_iac.png';
import { 
  Lock, 
  Mail, 
  User, 
  Phone, 
  Briefcase, 
  ShieldCheck, 
  Database, 
  FileText, 
  CheckCircle2, 
  AlertCircle,
  Eye,
  EyeOff,
  UserCheck,
  Building,
  Info,
  KeyRound
} from 'lucide-react';
import { adminLogin, registerCommercial } from '../../api';
import type { AdminSessionUser, CommercialRegisterPayload } from '../../types';
import './AuthPortal.css';

interface AuthPortalProps {
  onAuthenticated: (user: AdminSessionUser) => void;
}

export const AuthPortal: React.FC<AuthPortalProps> = ({ onAuthenticated }) => {
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  
  // Login State
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Register State
  const [regNombre, setRegNombre] = useState('');
  const [regApellido, setRegApellido] = useState('');
  const [regCargo, setRegCargo] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regCelular, setRegCelular] = useState('');
  const [regTipoDoc, setRegTipoDoc] = useState('CC');
  const [regDocumento, setRegDocumento] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [showRegConfirmPassword, setShowRegConfirmPassword] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);

  // Password strength calculation
  const getPasswordStrength = (pass: string) => {
    if (!pass) return { score: 0, label: '', color: '' };
    if (pass.length < 6) return { score: 1, label: 'Muy corta (mínimo 6)', color: '#ef4444' };
    
    let score = 1;
    if (pass.length >= 8) score++;
    if (/[0-9]/.test(pass) && /[a-zA-Z]/.test(pass)) score++;
    if (/[^A-Za-z0-9]/.test(pass)) score++;

    if (score <= 2) return { score: 2, label: 'Aceptable', color: '#f59e0b' };
    return { score: 3, label: 'Segura', color: '#10b981' };
  };

  const passwordStrength = getPasswordStrength(regPassword);

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

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);

    if (!regNombre.trim() || !regApellido.trim()) {
      setRegError('Nombres y apellidos son campos obligatorios.');
      return;
    }
    if (!regEmail.trim() || !regEmail.includes('@')) {
      setRegError('Ingresa un correo electrónico corporativo válido.');
      return;
    }
    if (regPassword.length < 6) {
      setRegError('La contraseña debe tener al menos 6 caracteres.');
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setRegError('Las contraseñas no coinciden. Por favor verifícalas.');
      return;
    }

    const payload: CommercialRegisterPayload = {
      profile_name: `${regNombre.trim()} ${regApellido.trim()}`,
      nombre: regNombre.trim(),
      apellido: regApellido.trim(),
      cargo: regCargo.trim() || 'Asesor Comercial',
      email: regEmail.trim().toLowerCase(),
      celular: regCelular.trim(),
      tipo_documento: regTipoDoc,
      documento_identidad: regDocumento.trim() || undefined,
      password: regPassword,
    };

    try {
      setIsRegistering(true);
      const res = await registerCommercial(payload);
      onAuthenticated(res);
    } catch (err: any) {
      setRegError(err.message || 'Error al registrar el perfil comercial.');
    } finally {
      setIsRegistering(false);
    }
  };

  return (
    <div className="auth-portal-page">
      <div className={`auth-portal-layout ${activeTab === 'register' ? 'layout-register-expanded' : ''}`}>
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
                    {activeTab === 'register' && regNombre 
                      ? `${regNombre} ${regApellido || ''}`.trim()
                      : 'Responsable Asignado Dinámicamente'}
                  </span>
                </div>
                <div className="sample-field-row">
                  <span className="sample-field-label">Cédula de Contacto (Habeas Data)</span>
                  <span className="sample-field-val masked">CC •••••••• (Cifrada)</span>
                </div>
              </div>
            </div>

            {/* Architectural Trust Badges */}
            <div className="showcase-pillars">
              <div className="pillar-item">
                <ShieldCheck size={16} className="pillar-icon text-emerald" />
                <div>
                  <strong>Ley 1581 (Habeas Data)</strong>
                  <span>Documentos de identidad enmascarados y de uso exclusivo en casillas de contacto.</span>
                </div>
              </div>
              <div className="pillar-item">
                <Database size={16} className="pillar-icon text-amber" />
                <div>
                  <strong>Persistencia en PostgreSQL Neon</strong>
                  <span>Tus perfiles y mapeos no se pierden en reinicios de servidor.</span>
                </div>
              </div>
            </div>
          </div>

          <footer className="showcase-footer">
            <span>© 2026 IAC Latam · Seguridad y Precisión Documental</span>
          </footer>
        </aside>

        {/* ========================================================= */}
        {/* RIGHT COLUMN: Authentication & Registration Console       */}
        {/* ========================================================= */}
        <main className={`auth-form-column ${activeTab === 'register' ? 'column-register-expanded' : ''}`}>
          <div className={`auth-form-card ${activeTab === 'register' ? 'card-register-expanded' : ''}`}>
            
            {/* Animated Tab Switcher with Sliding Pill Indicator */}
            <div className="auth-tab-switcher" role="tablist" aria-label="Opciones de autenticación">
              <div 
                className={`auth-tab-slider ${activeTab === 'register' ? 'slide-to-register' : 'slide-to-login'}`}
                aria-hidden="true"
              />
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'login'}
                className={`tab-btn ${activeTab === 'login' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('login');
                  setLoginError(null);
                }}
              >
                <UserCheck size={15} className="tab-icon" />
                <span>Iniciar Sesión</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'register'}
                className={`tab-btn ${activeTab === 'register' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('register');
                  setRegError(null);
                }}
              >
                <Briefcase size={15} className="tab-icon" />
                <span>Registrarme como Comercial</span>
              </button>
            </div>

            {/* =================================================== */}
            {/* VIEW 1: LOGIN                                       */}
            {/* =================================================== */}
            {activeTab === 'login' ? (
              <div className="auth-view-container view-fade-in" key="view-login">
                <div className="auth-view-header">
                  <div className="auth-view-header-badge">
                    <KeyRound size={13} />
                    <span>Portal de Acceso</span>
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
                    <label htmlFor="loginPassword">Contraseña</label>
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
                    ¿Eres nuevo en el equipo comercial?{' '}
                    <button
                      type="button"
                      className="auth-link-button"
                      onClick={() => {
                        setActiveTab('register');
                        setRegError(null);
                      }}
                    >
                      Crea tu perfil individual aquí
                    </button>
                  </p>
                </div>
              </div>
            ) : (
              /* =================================================== */
              /* VIEW 2: REGISTER (AMPLIADO Y ESTRUCTURADO)           */
              /* =================================================== */
              <div className="auth-view-container view-fade-in" key="view-register">
                <div className="auth-view-header">
                  <div className="auth-view-header-badge badge-amber">
                    <UserCheck size={13} />
                    <span>Nuevo Asesor Comercial</span>
                  </div>
                  <h3>Registro de Responsable Comercial</h3>
                  <p>
                    Configura tu perfil individual. Tus datos se utilizarán para diligenciar de manera 
                    automática las casillas de contacto en los formularios de tus clientes.
                  </p>
                </div>

                {regError && (
                  <div className="auth-alert alert-error" role="alert">
                    <AlertCircle size={16} />
                    <span>{regError}</span>
                  </div>
                )}

                <form onSubmit={handleRegisterSubmit} className="auth-form auth-form-expanded">
                  
                  {/* SECCIÓN 1: DATOS PERSONALES Y CONTACTO */}
                  <div className="form-section-block">
                    <div className="form-section-legend">
                      <User size={14} className="legend-icon text-amber" />
                      <span>1. Datos del Asesor y Contacto</span>
                    </div>

                    <div className="form-grid-2">
                      <div className="auth-field">
                        <label htmlFor="regNombre">Nombres *</label>
                        <div className="auth-input-wrapper">
                          <User size={16} className="auth-input-icon" />
                          <input
                            id="regNombre"
                            type="text"
                            required
                            placeholder="ej. Kelly Yohana"
                            value={regNombre}
                            onChange={(e) => setRegNombre(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="auth-field">
                        <label htmlFor="regApellido">Apellidos *</label>
                        <div className="auth-input-wrapper">
                          <input
                            id="regApellido"
                            type="text"
                            required
                            placeholder="ej. Delgado Macea"
                            value={regApellido}
                            onChange={(e) => setRegApellido(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="form-grid-2">
                      <div className="auth-field">
                        <label htmlFor="regCargo">Cargo en la Empresa</label>
                        <div className="auth-input-wrapper">
                          <Briefcase size={16} className="auth-input-icon" />
                          <input
                            id="regCargo"
                            type="text"
                            placeholder="ej. Asesor Comercial"
                            value={regCargo}
                            onChange={(e) => setRegCargo(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="auth-field">
                        <label htmlFor="regCelular">Celular / Teléfono</label>
                        <div className="auth-input-wrapper">
                          <Phone size={16} className="auth-input-icon" />
                          <input
                            id="regCelular"
                            type="tel"
                            placeholder="ej. 301 475 0760"
                            value={regCelular}
                            onChange={(e) => setRegCelular(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="auth-field">
                      <label htmlFor="regEmail">Correo Electrónico Corporativo *</label>
                      <div className="auth-input-wrapper">
                        <Mail size={16} className="auth-input-icon" />
                        <input
                          id="regEmail"
                          type="email"
                          required
                          autoComplete="email"
                          placeholder="nombre.apellido@iaclatam.com"
                          value={regEmail}
                          onChange={(e) => setRegEmail(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  {/* SECCIÓN 2: DILIGENCIAMIENTO OFICIAL & HABEAS DATA */}
                  <div className="form-section-block">
                    <div className="form-section-legend">
                      <ShieldCheck size={14} className="legend-icon text-emerald" />
                      <span>2. Diligenciamiento Oficial de Formularios</span>
                    </div>

                    <div className="form-grid-doc">
                      <div className="auth-field doc-type-select">
                        <label htmlFor="regTipoDoc">Tipo</label>
                        <select
                          id="regTipoDoc"
                          value={regTipoDoc}
                          onChange={(e) => setRegTipoDoc(e.target.value)}
                        >
                          <option value="CC">CC</option>
                          <option value="CE">CE</option>
                          <option value="PA">PA</option>
                          <option value="NIT">NIT</option>
                        </select>
                      </div>

                      <div className="auth-field">
                        <label htmlFor="regDocumento">
                          <span>Número de Documento (Cédula)</span>
                          <span className="doc-privacy-tag">Habeas Data</span>
                        </label>
                        <div className="auth-input-wrapper">
                          <input
                            id="regDocumento"
                            type="text"
                            placeholder="ej. 1020304050"
                            value={regDocumento}
                            onChange={(e) => setRegDocumento(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="habeas-data-card">
                      <Info size={14} className="habeas-icon" />
                      <p>
                        Tu documento se resguarda bajo la <strong>Ley 1581 de 2012</strong>. Se utilizará 
                        exclusivamente cuando un formulario de licitación exija la cédula de la persona de contacto.
                      </p>
                    </div>
                  </div>

                  {/* SECCIÓN 3: SEGURIDAD DE LA CUENTA */}
                  <div className="form-section-block">
                    <div className="form-section-legend">
                      <Lock size={14} className="legend-icon text-amber" />
                      <span>3. Credenciales de Seguridad</span>
                    </div>

                    <div className="form-grid-2">
                      <div className="auth-field">
                        <label htmlFor="regPassword">Contraseña de Acceso *</label>
                        <div className="auth-input-wrapper">
                          <Lock size={16} className="auth-input-icon" />
                          <input
                            id="regPassword"
                            type={showRegPassword ? 'text' : 'password'}
                            required
                            autoComplete="new-password"
                            placeholder="Mínimo 6 caracteres"
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

                        {/* Indicador de Fortaleza */}
                        {regPassword && (
                          <div className="password-meter-wrap">
                            <div className="password-meter-bars">
                              <span className={`meter-bar ${passwordStrength.score >= 1 ? 'active' : ''}`} style={{ backgroundColor: passwordStrength.score >= 1 ? passwordStrength.color : undefined }} />
                              <span className={`meter-bar ${passwordStrength.score >= 2 ? 'active' : ''}`} style={{ backgroundColor: passwordStrength.score >= 2 ? passwordStrength.color : undefined }} />
                              <span className={`meter-bar ${passwordStrength.score >= 3 ? 'active' : ''}`} style={{ backgroundColor: passwordStrength.score >= 3 ? passwordStrength.color : undefined }} />
                            </div>
                            <span className="meter-label" style={{ color: passwordStrength.color }}>
                              {passwordStrength.label}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="auth-field">
                        <label htmlFor="regConfirmPassword">Confirmar Contraseña *</label>
                        <div className="auth-input-wrapper">
                          <Lock size={16} className="auth-input-icon" />
                          <input
                            id="regConfirmPassword"
                            type={showRegConfirmPassword ? 'text' : 'password'}
                            required
                            autoComplete="new-password"
                            placeholder="Repite tu contraseña"
                            value={regConfirmPassword}
                            onChange={(e) => setRegConfirmPassword(e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn-toggle-eye"
                            onClick={() => setShowRegConfirmPassword(!showRegConfirmPassword)}
                            title={showRegConfirmPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                          >
                            {showRegConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                          </button>
                        </div>
                        {regConfirmPassword && regPassword !== regConfirmPassword && (
                          <span className="field-hint-error">Las contraseñas no coinciden</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-auth-primary btn-auth-submit-large"
                    disabled={isRegistering}
                  >
                    {isRegistering ? (
                      <>
                        <span className="auth-spinner" />
                        <span>Creando perfil comercial en base de datos...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 size={18} />
                        <span>Crear Perfil y Comenzar a Diligenciar</span>
                      </>
                    )}
                  </button>
                </form>

                <div className="auth-card-footer">
                  <p>
                    ¿Ya tienes una cuenta registrada en el sistema?{' '}
                    <button
                      type="button"
                      className="auth-link-button"
                      onClick={() => {
                        setActiveTab('login');
                        setLoginError(null);
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

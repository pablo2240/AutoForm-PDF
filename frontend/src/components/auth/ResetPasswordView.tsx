import React, { useState } from 'react';
import { Lock, Eye, EyeOff, CheckCircle2, AlertCircle, ArrowLeft, KeyRound } from 'lucide-react';
import { supabase } from '../../supabaseClient';
import logoIac from '../../assets/logo_iac.png';
import './AuthPortal.css';

interface ResetPasswordViewProps {
  onComplete: () => void;
  onCancel?: () => void;
}

export const ResetPasswordView: React.FC<ResetPasswordViewProps> = ({ onComplete, onCancel }) => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Live criteria validation
  const hasMinLength = password.length >= 8;
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasNumberOrSpecial = /[0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password);
  const passwordsMatch = password.length > 0 && confirmPassword.length > 0 && password === confirmPassword;
  const isFormValid = hasMinLength && hasUpper && hasLower && hasNumberOrSpecial && passwordsMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!hasMinLength) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (!hasUpper || !hasLower) {
      setError('La contraseña debe contener al menos una letra mayúscula y una minúscula.');
      return;
    }
    if (!hasNumberOrSpecial) {
      setError('La contraseña debe contener al menos un número o símbolo.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Las contraseñas ingresadas no coinciden.');
      return;
    }

    try {
      setIsLoading(true);
      const { error: updateError } = await supabase.auth.updateUser({
        password: password
      });

      if (updateError) {
        throw updateError;
      }

      // Clean tokens from browser address bar immediately without reload
      if (typeof window !== 'undefined' && window.history && window.history.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      setSuccess('Tu contraseña corporativa ha sido actualizada exitosamente.');
      setTimeout(() => {
        onComplete();
      }, 1800);
    } catch (err: any) {
      setError(err.message || 'Error al actualizar la contraseña. El enlace puede haber expirado.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-portal-page">
      <div className="auth-portal-layout layout-single-card">
        <main className="auth-form-column" style={{ padding: '36px 32px', maxHeight: 'none' }}>
          <div className="auth-form-card" style={{ maxWidth: '100%' }}>

            <div className="auth-view-header text-center">
              <div className="reset-brand-badge">
                <img src={logoIac} alt="IAC Latam" className="reset-brand-logo" />
                <span className="reset-brand-title">AutoForm PDF</span>
              </div>
              <div className="auth-view-header-badge badge-amber">
                <KeyRound size={13} />
                <span>Seguridad Corporativa</span>
              </div>
              <h3>Establecer Nueva Contraseña</h3>
              <p>Crea tu nueva contraseña para acceder a la plataforma comercial.</p>
            </div>

            {error && (
              <div className="auth-alert alert-error" role="alert">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="auth-alert alert-success" role="alert">
                <CheckCircle2 size={16} />
                <span>{success}</span>
              </div>
            )}

            {!success && (
              <form onSubmit={handleSubmit} className="auth-form">
                <div className="auth-field">
                  <label htmlFor="resetPassword">Nueva Contraseña</label>
                  <div className="auth-input-wrapper">
                    <Lock size={17} className="auth-input-icon" />
                    <input
                      id="resetPassword"
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="new-password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (error) setError(null);
                      }}
                    />
                    <button
                      type="button"
                      className="btn-toggle-eye"
                      onClick={() => setShowPassword(!showPassword)}
                      title={showPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className="auth-field">
                  <label htmlFor="resetConfirmPassword">Confirmar Contraseña</label>
                  <div className="auth-input-wrapper">
                    <Lock size={17} className="auth-input-icon" />
                    <input
                      id="resetConfirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      required
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (error) setError(null);
                      }}
                    />
                    <button
                      type="button"
                      className="btn-toggle-eye"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      title={showConfirmPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                    >
                      {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Interactive Dynamic Checklist */}
                <div className="password-requirements-card">
                  <span className="req-title">Requisitos de seguridad:</span>
                  <div className="req-grid">
                    <div className={`req-item ${hasMinLength ? 'met' : ''}`}>
                      <CheckCircle2 size={13} className="req-icon" />
                      <span>Mínimo 8 caracteres</span>
                    </div>
                    <div className={`req-item ${hasUpper && hasLower ? 'met' : ''}`}>
                      <CheckCircle2 size={13} className="req-icon" />
                      <span>Mayúscula y minúscula</span>
                    </div>
                    <div className={`req-item ${hasNumberOrSpecial ? 'met' : ''}`}>
                      <CheckCircle2 size={13} className="req-icon" />
                      <span>Número o símbolo</span>
                    </div>
                    <div className={`req-item ${passwordsMatch ? 'met' : ''}`}>
                      <CheckCircle2 size={13} className="req-icon" />
                      <span>Contraseñas coinciden</span>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-auth-primary"
                  disabled={isLoading || !isFormValid}
                >
                  {isLoading ? (
                    <>
                      <span className="auth-spinner" />
                      <span>Actualizando credenciales...</span>
                    </>
                  ) : (
                    <>
                      <KeyRound size={17} />
                      <span>Actualizar Contraseña y Acceder</span>
                    </>
                  )}
                </button>

                {onCancel && (
                  <div className="reset-back-wrapper">
                    <button
                      type="button"
                      className="auth-back-link"
                      onClick={onCancel}
                    >
                      <ArrowLeft size={15} />
                      <span>Volver al Inicio de Sesión</span>
                    </button>
                  </div>
                )}
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

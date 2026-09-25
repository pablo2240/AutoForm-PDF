import React, { useState } from 'react';
import { Lock, Eye, EyeOff, CheckCircle, AlertTriangle, ArrowLeft } from 'lucide-react';
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

  const validatePassword = (pass: string): string | null => {
    if (pass.length < 8) {
      return 'La contraseña debe tener al menos 8 caracteres.';
    }
    if (!/[A-Z]/.test(pass)) {
      return 'La contraseña debe contener al menos una letra mayúscula.';
    }
    if (!/[a-z]/.test(pass)) {
      return 'La contraseña debe contener al menos una letra minúscula.';
    }
    if (!/[0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pass)) {
      return 'La contraseña debe contener al menos un número o carácter especial.';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const validationError = validatePassword(password);
    if (validationError) {
      setError(validationError);
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

      setSuccess('Tu contraseña ha sido actualizada exitosamente.');
      setTimeout(() => {
        onComplete();
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Error al actualizar la contraseña. El enlace puede haber expirado.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-portal-page">
      <div className="auth-portal-layout" style={{ maxWidth: 500, margin: '0 auto' }}>
        <main className="auth-form-column" style={{ width: '100%' }}>
          <div className="auth-form-card">
            <div className="auth-form-header">
              <div className="auth-card-brand">
                <img src={logoIac} alt="IAC Logo" className="auth-brand-logo-img" />
                <span className="auth-brand-name">AutoForm PDF</span>
              </div>
              <h2 className="auth-form-title">Establecer Nueva Contraseña</h2>
              <p className="auth-form-subtitle">
                Ingresa y confirma tu nueva contraseña corporativa para acceder a la plataforma.
              </p>
            </div>

            {error && (
              <div className="auth-alert error" role="alert">
                <AlertTriangle size={15} className="alert-icon" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="auth-alert success" role="alert">
                <CheckCircle size={15} className="alert-icon" />
                <span>{success}</span>
              </div>
            )}

            {!success && (
              <form onSubmit={handleSubmit} className="auth-form-body">
                <div className="auth-field-group">
                  <label className="auth-field-label">Nueva Contraseña</label>
                  <div className="auth-input-wrapper">
                    <Lock size={15} className="field-icon" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="auth-text-input"
                      placeholder="Mínimo 8 caracteres"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="field-toggle-btn"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="auth-field-group">
                  <label className="auth-field-label">Confirmar Contraseña</label>
                  <div className="auth-input-wrapper">
                    <Lock size={15} className="field-icon" />
                    <input
                      type={showConfirmPassword ? 'text' : 'password'}
                      className="auth-text-input"
                      placeholder="Repite tu contraseña"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="field-toggle-btn"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    >
                      {showConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="password-hints" style={{ fontSize: '0.8rem', color: '#64748b', margin: '8px 0 16px' }}>
                  <p>La contraseña debe contener:</p>
                  <ul style={{ paddingLeft: '1.2rem', margin: '4px 0' }}>
                    <li>Mínimo 8 caracteres</li>
                    <li>Al menos una letra mayúscula y una minúscula</li>
                    <li>Al menos un número o símbolo</li>
                  </ul>
                </div>

                <button
                  type="submit"
                  className="auth-submit-btn primary"
                  disabled={isLoading}
                >
                  {isLoading ? 'Actualizando contraseña...' : 'Actualizar Contraseña'}
                </button>

                {onCancel && (
                  <button
                    type="button"
                    className="auth-link-button center"
                    onClick={onCancel}
                    style={{ marginTop: 12 }}
                  >
                    <ArrowLeft size={14} /> Volver al Inicio de Sesión
                  </button>
                )}
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

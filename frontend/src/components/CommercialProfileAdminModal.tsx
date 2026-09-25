import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldCheck, 
  Lock, 
  Mail, 
  Phone, 
  Eye, 
  EyeOff, 
  Check, 
  Edit2, 
  UserX, 
  UserCheck, 
  Trash2,
  LogOut,
  AlertCircle
} from 'lucide-react';
import { 
  adminLogin, 
  adminCheck, 
  adminLogout, 
  fetchAdminCommercialProfiles, 
  createCommercialProfile, 
  updateCommercialProfile, 
  deleteCommercialProfile 
} from '../api';
import type { CommercialProfileAdmin, AdminSessionUser } from '../types';

interface CommercialProfileAdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfilesUpdated: () => void;
}

const EMPTY_FORM = {
  profile_name: '',
  nombre: '',
  apellido: '',
  cargo: '',
  email: '',
  celular: '',
  tipo_documento: 'CC',
  documento_identidad: '',
  role: 'commercial',
  password: '',
  is_active: true,
};

export const CommercialProfileAdminModal: React.FC<CommercialProfileAdminModalProps> = ({
  isOpen,
  onClose,
  onProfilesUpdated,
}) => {
  // Auth state
  const [sessionUser, setSessionUser] = useState<AdminSessionUser>({ authenticated: false });
  const [checkingAuth, setCheckingAuth] = useState<boolean>(true);
  const [loginEmail, setLoginEmail] = useState<string>('');
  const [loginPassword, setLoginPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  // Data state
  const [profiles, setProfiles] = useState<CommercialProfileAdmin[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState<boolean>(false);
  const [revealedDocs, setRevealedDocs] = useState<Record<string, boolean>>({});

  // Form state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // Check auth on modal open
  useEffect(() => {
    if (isOpen) {
      checkCurrentSession();
    }
  }, [isOpen]);

  const checkCurrentSession = async () => {
    setCheckingAuth(true);
    setLoginError(null);
    try {
      const user = await adminCheck();
      setSessionUser(user);
      if (user.authenticated) {
        await loadProfiles();
      }
    } catch {
      setSessionUser({ authenticated: false });
    } finally {
      setCheckingAuth(false);
    }
  };

  const loadProfiles = async () => {
    setLoadingProfiles(true);
    try {
      const list = await fetchAdminCommercialProfiles();
      setProfiles(list);
    } catch (err: any) {
      console.error('Error fetching admin profiles', err);
    } finally {
      setLoadingProfiles(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      const res = await adminLogin(loginEmail, loginPassword);
      setSessionUser({
        authenticated: true,
        email: loginEmail,
        role: res.role,
        profile_name: res.profile_name,
      });
      setLoginPassword('');
      await loadProfiles();
    } catch (err: any) {
      setLoginError(err.message || 'Credenciales inválidas');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    try {
      await adminLogout();
    } catch (err) {
      console.error(err);
    }
    setSessionUser({ authenticated: false });
    setProfiles([]);
    setEditingId(null);
    setFormData(EMPTY_FORM);
  };

  const toggleRevealDoc = (profileId: string) => {
    setRevealedDocs((prev) => ({
      ...prev,
      [profileId]: !prev[profileId],
    }));
  };

  const handleStartEdit = (p: CommercialProfileAdmin) => {
    setEditingId(p.id);
    setFormError(null);
    setFormData({
      profile_name: p.profile_name,
      nombre: p.nombre,
      apellido: p.apellido,
      cargo: p.cargo || '',
      email: p.email || '',
      celular: p.celular || '',
      tipo_documento: p.tipo_documento || 'CC',
      documento_identidad: p.documento_identidad || '',
      role: p.role || 'commercial',
      password: '',
      is_active: p.is_active,
    });
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setFormError(null);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formData.profile_name.trim() || !formData.nombre.trim() || !formData.apellido.trim() || !formData.email.trim()) {
      setFormError('Por favor completa los campos obligatorios (Nombre perfil, Nombres, Apellidos, Email).');
      return;
    }

    try {
      setIsSaving(true);
      const payload: any = {
        profile_name: formData.profile_name.trim(),
        nombre: formData.nombre.trim(),
        apellido: formData.apellido.trim(),
        cargo: formData.cargo.trim(),
        email: formData.email.trim().toLowerCase(),
        celular: formData.celular.trim(),
        tipo_documento: formData.tipo_documento.trim() || 'CC',
        documento_identidad: formData.documento_identidad.trim(),
        role: formData.role,
        is_active: formData.is_active,
      };

      if (formData.password.trim()) {
        payload.password = formData.password.trim();
      }

      if (editingId) {
        await updateCommercialProfile(editingId, payload);
      } else {
        await createCommercialProfile(payload);
      }

      handleCancelEdit();
      await loadProfiles();
      onProfilesUpdated();
    } catch (err: any) {
      setFormError(err.message || 'Error al guardar el perfil comercial');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleActive = async (p: CommercialProfileAdmin) => {
    try {
      await updateCommercialProfile(p.id, { is_active: !p.is_active });
      await loadProfiles();
      onProfilesUpdated();
    } catch (err: any) {
      alert(`Error al cambiar estado: ${err.message}`);
    }
  };

  const handleDeleteProfile = async (p: CommercialProfileAdmin) => {
    if (!window.confirm(`¿Estás seguro de eliminar el perfil comercial "${p.profile_name}"?`)) {
      return;
    }
    try {
      await deleteCommercialProfile(p.id);
      await loadProfiles();
      onProfilesUpdated();
    } catch (err: any) {
      alert(`Error al eliminar perfil: ${err.message}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog admin-profile-modal-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <ShieldCheck size={20} className="icon-shield-admin" />
            <div>
              <h3>Gestión de Responsables Comerciales</h3>
            </div>
          </div>
          <button className="btn-close" onClick={onClose} title="Cerrar modal">
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body admin-modal-body">
          {checkingAuth ? (
            <div className="admin-loading-state">
              <div className="spinner" />
              <p>Verificando credenciales de acceso...</p>
            </div>
          ) : !sessionUser.authenticated ? (
            /* ========================================== */
            /* LOGIN SCREEN                               */
            /* ========================================== */
            <div className="admin-login-card">
              <div className="login-header">
                <div className="login-icon-circle">
                  <Lock size={26} />
                </div>
                <h4>Acceso Administrativo Seguro</h4>
                <p>
                  Para acceder a la administración de responsables comerciales, inicia sesión con tu cuenta de administrador.
                </p>
              </div>
          ) : sessionUser.role !== 'admin' ? (
            <div className="admin-login-card">
              <div className="login-header">
                <div className="login-icon-circle" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
                  <AlertCircle size={26} />
                </div>
                <h4>Acceso Restringido</h4>
                <p>
                  Tu cuenta ({sessionUser.email}) no tiene permisos de Administrador.
                  Solo los administradores pueden gestionar los responsables comerciales.
                </p>
              </div>
            </div>

              {loginError && (
                <div className="alert-message alert-danger">
                  <AlertCircle size={16} />
                  <span>{loginError}</span>
                </div>
              )}

              <form onSubmit={handleLogin} className="admin-login-form">
                <div className="form-group">
                  <label htmlFor="adminEmail">Correo Corporativo</label>
                  <div className="input-with-icon">
                    <Mail size={16} />
                    <input
                      id="adminEmail"
                      type="email"
                      required
                      placeholder="ejemplo@iaclatam.com"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="adminPassword">Contraseña</label>
                  <div className="input-with-icon">
                    <Lock size={16} />
                    <input
                      id="adminPassword"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                    />
                  </div>
                </div>

                <button 
                  type="submit" 
                  className="btn btn-primary btn-login-submit"
                  disabled={isLoggingIn}
                >
                  {isLoggingIn ? 'Autenticando...' : 'Iniciar Sesión'}
                </button>
              </form>

              <div className="login-help-text">
                <span>🔐 Cuentas autorizadas: Guillermo Cañón (Admin) & Kelly Delgado (Comercial)</span>
              </div>
            </div>
          ) : (
            /* ========================================== */
            /* ADMIN DASHBOARD: LIST + FORM               */
            /* ========================================== */
            <div className="admin-dashboard-container">
              {/* User Session Bar */}
              <div className="admin-session-bar">
                <div className="session-user-info">
                  <span className="session-pill">Sesión Activa</span>
                  <strong>{sessionUser.profile_name || sessionUser.email}</strong>
                  <span className={`role-badge role-${sessionUser.role}`}>
                    {sessionUser.role === 'admin' ? '👑 Administrador' : '💼 Comercial'}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm btn-logout"
                  onClick={handleLogout}
                  title="Cerrar sesión administrativa"
                >
                  <LogOut size={14} />
                  <span>Salir</span>
                </button>
              </div>

              <div className="admin-grid-layout">
                {/* Left Side: Commercial Profiles Table */}
                <div className="admin-profiles-column">
                  <div className="column-header">
                    <h4>Responsables Registrados ({profiles.length})</h4>
                    <span className="column-sub">Visibles en el selector del formulario</span>
                  </div>

                  {loadingProfiles ? (
                    <div className="admin-loading-state">
                      <div className="spinner" />
                    </div>
                  ) : profiles.length === 0 ? (
                    <div className="empty-profiles-state">
                      <p>No hay responsables registrados.</p>
                    </div>
                  ) : (
                    <div className="profiles-table-container">
                      <table className="admin-profiles-table">
                        <thead>
                          <tr>
                            <th>Nombre y Cargo</th>
                            <th>Contacto</th>
                            <th>Documento de Identidad</th>
                            <th>Estado</th>
                            <th>Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profiles.map((p) => {
                            const isRevealed = !!revealedDocs[p.id];
                            const isCurrentlyEditing = editingId === p.id;
                            return (
                              <tr key={p.id} className={`${!p.is_active ? 'row-inactive' : ''} ${isCurrentlyEditing ? 'row-editing' : ''}`}>
                                <td>
                                  <div className="profile-name-cell">
                                    <strong>{p.profile_name}</strong>
                                    <span className="profile-subname">{p.nombre} {p.apellido}</span>
                                    <span className="profile-cargo-badge">{p.cargo || 'Comercial'}</span>
                                  </div>
                                </td>
                                <td>
                                  <div className="profile-contact-cell">
                                    <span><Mail size={12} /> {p.email}</span>
                                    {p.celular && <span><Phone size={12} /> {p.celular}</span>}
                                  </div>
                                </td>
                                <td>
                                  <div className="profile-doc-cell">
                                    <span className="doc-type-pill">{p.tipo_documento || 'CC'}</span>
                                    <span className="doc-value">
                                      {isRevealed 
                                        ? (p.documento_identidad || 'Sin registrar')
                                        : (p.documento_identidad ? '••••••••' : '—')}
                                    </span>
                                    {p.documento_identidad && (
                                      <button
                                        type="button"
                                        className="btn-doc-toggle"
                                        onClick={() => toggleRevealDoc(p.id)}
                                        title={isRevealed ? "Ocultar documento" : "Ver documento de identidad"}
                                      >
                                        {isRevealed ? <EyeOff size={13} /> : <Eye size={13} />}
                                      </button>
                                    )}
                                  </div>
                                </td>
                                <td>
                                  <span className={`status-pill ${p.is_active ? 'status-active' : 'status-inactive'}`}>
                                    {p.is_active ? 'Activo' : 'Inactivo'}
                                  </span>
                                </td>
                                <td>
                                  <div className="action-buttons-cell">
                                    <button
                                      type="button"
                                      className="btn-action-icon"
                                      onClick={() => handleStartEdit(p)}
                                      title="Editar datos de este responsable"
                                    >
                                      <Edit2 size={14} />
                                    </button>
                                    <button
                                      type="button"
                                      className={`btn-action-icon ${p.is_active ? 'btn-deactivate' : 'btn-activate'}`}
                                      onClick={() => handleToggleActive(p)}
                                      title={p.is_active ? "Desactivar perfil" : "Activar perfil"}
                                    >
                                      {p.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                                    </button>
                                    <button
                                      type="button"
                                      className="btn-action-icon btn-deactivate"
                                      onClick={() => handleDeleteProfile(p)}
                                      title="Eliminar perfil comercial"
                                    >
                                      <Trash2 size={14} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Right Side: Create / Edit Form */}
                <div className="admin-form-column">
                  <div className="column-header">
                    <h4>{editingId ? 'Editar Responsable' : 'Nuevo Responsable'}</h4>
                    {editingId && (
                      <button
                        type="button"
                        className="btn btn-sm btn-secondary"
                        onClick={handleCancelEdit}
                      >
                        Cancelar
                      </button>
                    )}
                  </div>

                  {formError && (
                    <div className="alert-message alert-danger">
                      <AlertCircle size={15} />
                      <span>{formError}</span>
                    </div>
                  )}

                  <form onSubmit={handleSaveProfile} className="profile-edit-form">
                    <div className="form-row">
                      <div className="form-group flex-1">
                        <label>Nombre en Selector *</label>
                        <input
                          type="text"
                          required
                          placeholder="ej. Kelly Delgado"
                          value={formData.profile_name}
                          onChange={(e) => setFormData({ ...formData, profile_name: e.target.value })}
                        />
                      </div>
                      <div className="form-group flex-1">
                        <label>Cargo / Rol en Formulario</label>
                        <input
                          type="text"
                          placeholder="ej. Asesor Comercial"
                          value={formData.cargo}
                          onChange={(e) => setFormData({ ...formData, cargo: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-row">
                      <div className="form-group flex-1">
                        <label>Nombres *</label>
                        <input
                          type="text"
                          required
                          placeholder="ej. Kelly Johana"
                          value={formData.nombre}
                          onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                        />
                      </div>
                      <div className="form-group flex-1">
                        <label>Apellidos *</label>
                        <input
                          type="text"
                          required
                          placeholder="ej. Delgado"
                          value={formData.apellido}
                          onChange={(e) => setFormData({ ...formData, apellido: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-row">
                      <div className="form-group flex-1">
                        <label>Correo Electrónico *</label>
                        <input
                          type="email"
                          required
                          placeholder="ejemplo@iaclatam.com"
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        />
                      </div>
                      <div className="form-group flex-1">
                        <label>Teléfono / Celular</label>
                        <input
                          type="tel"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={15}
                          placeholder="ej. 3100000000"
                          value={formData.celular}
                          onChange={(e) => setFormData({ ...formData, celular: e.target.value.replace(/\D/g, '') })}
                        />
                      </div>
                    </div>

                    <div className="form-row">
                      <div className="form-group" style={{ maxWidth: '100px' }}>
                        <label>Tipo Doc</label>
                        <select
                          value={formData.tipo_documento}
                          onChange={(e) => setFormData({ ...formData, tipo_documento: e.target.value })}
                        >
                          <option value="CC">CC</option>
                          <option value="CE">CE</option>
                          <option value="PA">PA</option>
                        </select>
                      </div>
                      <div className="form-group flex-1">
                        <label>Número de Documento (Cédula)</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={15}
                          placeholder="Cédula para casillas de contacto"
                          value={formData.documento_identidad}
                          onChange={(e) => setFormData({ ...formData, documento_identidad: e.target.value.replace(/\D/g, '') })}
                        />
                      </div>
                    </div>

                    <div className="form-row">
                      <div className="form-group flex-1">
                        <label>Rol de Acceso</label>
                        <select
                          value={formData.role}
                          onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        >
                          <option value="commercial">Comercial</option>
                          <option value="admin">Administrador</option>
                        </select>
                      </div>
                      <div className="form-group flex-1">
                        <label>Contraseña {editingId ? '(opcional para cambiar)' : '(opcional)'}</label>
                        <input
                          type="password"
                          placeholder="Clave de acceso"
                          value={formData.password}
                          onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-group-checkbox">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={formData.is_active}
                          onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                        />
                        <span>Perfil Activo (visible en la lista desplegable de formularios)</span>
                      </label>
                    </div>

                    <div className="form-actions-right">
                      <button
                        type="submit"
                        className="btn btn-primary btn-save-profile"
                        disabled={isSaving}
                      >
                        {isSaving ? 'Guardando...' : (
                          <>
                            <Check size={16} />
                            <span>{editingId ? 'Actualizar Perfil' : 'Crear Perfil'}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

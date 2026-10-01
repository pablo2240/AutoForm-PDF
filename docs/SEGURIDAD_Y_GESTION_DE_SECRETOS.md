# DocumentForge — Seguridad, Confidencialidad y Gestión de Secretos

Este documento define la política canónica de seguridad, gobierno de credenciales, inventario de variables de entorno y protocolos de administración segura para la plataforma **DocumentForge**.

---

## 1. Principios Rectores de Seguridad

1. **Defensa en Profundidad y Confidencialidad Jurídica**: Todo dato gestionado por DocumentForge está sujeto al secreto profesional y normativas de protección de datos personales. Ninguna comodidad operativa justifica relajar controles de acceso o cifrado.
2. **Arquitectura Zero Trust y Mínimo Privilegio**: Ningún servicio, usuario o proceso cuenta con privilegios implícitos. Cada acceso entre microservicios (C#, Go, Python, Frontend) debe estar autenticado, autorizado y auditado.
3. **Cero Retención y No Entrenamiento por Modelos de IA**:
   * Queda terminantemente prohibido utilizar documentos de clientes, metadatos contractuales, expedientes judiciales o consultas en lenguaje natural para entrenar, reentrenar o ajustar (*fine-tune*) modelos de IA.
   * Los servicios de inferencia LLM deben contratarse bajo acuerdos empresariales con política explícita de **Cero Retención de Datos** (*Zero Data Retention* / No-Human Review).

---

## 2. Reglas Infranqueables de Credenciales (Tolerancia Cero)

> [!CAUTION]
> **POLÍTICA INMUTABLE DE PROTECCIÓN DE SECRETOS**
> * **PROHIBICIÓN ABSOLUTA DE COMMITS DE SECRETOS**: Jamás debe subirse al control de versiones (Git), ramas de prueba, Pull Requests ni issues ningún tipo de credencial real: contraseñas de base de datos, API keys de Azure OpenAI, secretos de cliente de Microsoft Entra, llaves de firma JWT ni tokens personales de acceso.
> * **NO INCLUSIÓN DE CORREOS PERSONALES**: Las cuentas administrativas deben pertenecer exclusivamente a dominios corporativos autorizados (`@empresa.com`). Queda prohibido registrar o documentar correos personales (`@gmail.com`, `@hotmail.com`, etc.).
> * **NO TEXTO PLANO EN COMUNICACIONES**: Está prohibido compartir credenciales o tokens por herramientas de mensajería instantánea (Slack, Teams, WhatsApp), correos electrónicos no cifrados o tickets de soporte técnico.
> * **NO VOLCADO EN LOGS NI TELEMETRÍA**: Los filtros de sanitización deben impedir que variables de entorno o valores de encabezados `Authorization` aparezcan en la consola de depuración o sistemas de observabilidad.

---

## 3. Gestor de Secretos Aprobado y Aprovisionamiento Seguro

### 3.1. Almacén Centralizado de Secretos
Todas las credenciales productivas deben residir exclusivamente en el gestor de secretos corporativo aprobado:
* **Entornos de Nube (Producción / Staging)**: **Azure Key Vault** o **AWS Secrets Manager** con cifrado en reposo mediante HSM (Hardware Security Module) y control de acceso RBAC granular.
* **Inyección en Tiempo de Ejecución (Runtime)**:
  * Los contenedores o servicios App Service consumen los secretos en memoria mediante referencias directas a Key Vault (`@Microsoft.KeyVault(...)`) o agentes de secretos autorizados por Managed Identity.
  * Los secretos nunca se graban en imágenes de Docker ni en discos de servidores.
* **Entorno de Desarrollo Local**:
  * Empleo de archivos `.env` locales excluidos estrictamente de Git mediante `.gitignore`.
  * Los desarrolladores utilizan credenciales de pruebas aisladas con permisos restringidos; nunca credenciales con acceso a datos de clientes.

### 3.2. Procedimientos de Administración de Credenciales

#### A. Procedimiento para Solicitar Nuevos Accesos Administrativos
1. **Justificación y Mínimo Privilegio**: El solicitante debe presentar una solicitud formal indicando el rol requerido (`admin`, `auditor`, `devops`), el proyecto específico y la ventana de tiempo de acceso requerida.
2. **Aprobación de Seguridad**: Toda solicitud administrativa requiere la aprobación explícita del Administrador de Seguridad (SecOps / CISO).
3. **Aprovisionamiento sin Exposición de Contraseña**:
   * El usuario se registra en la plataforma mediante el flujo de invitación segura.
   * El sistema genera un enlace criptográfico temporal con vigencia de 15 minutos enviado directamente al correo corporativo del nuevo administrador.
   * El administrador define su contraseña con doble factor de autenticación (MFA) obligatorio. Ningún operador humano conoce ni almacena dicha contraseña.

#### B. Procedimiento de Rotación Programada y de Emergencia
* **Rotación Periódica**:
  * Secretos de API de Azure OpenAI y Microsoft Graph: cada **180 días**.
  * Cadenas de conexión a base de datos y llaves de cifrado de tokens: cada **90 días**.
* **Técnica de Rotación sin Interrupción (Dual-Secret / Overlapping)**:
  1. En Microsoft Entra ID o Azure OpenAI, se crea una llave secundaria (`Key 2`).
  2. Se actualiza el secreto en el Key Vault.
  3. Se reinician los workers de procesamiento para tomar la nueva llave.
  4. Una vez verificada la continuidad del servicio, se elimina la llave anterior (`Key 1`).
* **Rotación de Emergencia (Sospecha de Compromiso)**:
  1. Revocación instantánea de la llave afectada en el portal de nube.
  2. Emisión forzada de nueva credencial y actualización atómica en Key Vault.
  3. Desconexión inmediata de todas las sesiones de usuario activas.
  4. Ejecución del Checklist de Respuesta ante Incidentes.

#### C. Procedimiento de Revocación Inmediata de Accesos
* En caso de desvinculación de un colaborador o baja de un rol administrativo:
  1. Desactivación inmediata de la cuenta en Microsoft Entra ID / Proveedor de Identidad corporativo.
  2. Invalidación de tokens de refresco (*refresh tokens*) activos.
  3. En la base de datos de DocumentForge, conmutación del estado del perfil: `is_active = false`.
  4. Revisión del registro de auditoría de los últimos 30 días para descartar exportaciones no autorizadas.

#### D. Procedimiento Seguro de Recuperación de Accesos
* Si un administrador olvida su contraseña o extravía su dispositivo MFA:
  1. Se ejecuta el flujo de autoservicio de recuperación mediante correo corporativo.
  2. El enlace de un solo uso requiere validación de identidad y verificación de canal secundario.
  3. Si la cuenta está bloqueada por intentos fallidos, el desbloqueo solo puede ser autorizado por un segundo administrador con rol Super-Admin, registrando el ticket correspondiente en el log de auditoría.

---

## 4. Inventario Canónico de Variables de Entorno

A continuación se detalla la totalidad de variables requeridas por DocumentForge en sus distintos componentes.

> [!IMPORTANT]
> **REGLA DE DOCUMENTACIÓN SEGURA:**
> Esta tabla **NO** contiene valores reales, cadenas de conexión productivas ni contraseñas. Sirve exclusivamente como inventario técnico y guía de aprovisionamiento para DevOps y administradores de sistemas.

| Variable de Entorno | Propósito Técnico | Componente Consumidor | Responsable | Dónde se Configura |
|---|---|---|---|---|
| `ENVIRONMENT` | Define el entorno de ejecución (`production`, `staging`, `development`). | Backend / Frontend | DevOps | App Service / Variable de Sistema |
| `PORT` | Puerto de escucha para el servidor HTTP FastAPI (por defecto `8000`). | Backend Python | DevOps | Configuración de Runtime / Contenedor |
| `ALLOWED_ORIGINS` | Lista separada por comas de orígenes permitidos por CORS (FQDN HTTPS). | Backend FastAPI | SecOps / DevOps | Key Vault / App Configuration |
| `AZURE_OPENAI_ENDPOINT` | URL del recurso de Azure OpenAI para el despliegue del modelo LLM. | Backend Python | Administrador Nube | Azure Key Vault / App Settings |
| `AZURE_OPENAI_API_KEY` | Clave criptográfica para autenticación contra Azure OpenAI Service. | Backend Python | SecOps | Azure Key Vault (Managed Secret) |
| `AZURE_OPENAI_DEPLOYMENT_NAME`| Nombre del modelo desplegado (ej. `gpt-4.1-mini`). | Backend Python | Administrador IA | App Service Environment Variables |
| `AZURE_OPENAI_API_VERSION` | Versión de API de Azure OpenAI (ej. `2024-12-01-preview`). | Backend Python | Administrador IA | App Service Environment Variables |
| `MICROSOFT_TENANT_ID` | Identificador del directorio tenant de Microsoft Entra del cliente. | Conector C# | Admin M365 | Key Vault / Configuración Conector |
| `MICROSOFT_CLIENT_ID` | ID de la aplicación registrada en Microsoft Entra ID. | Conector C# | Admin M365 | Key Vault / Configuración Conector |
| `MICROSOFT_CLIENT_SECRET` | Secreto OAuth de la aplicación de Microsoft Entra para daemon sync. | Conector C# | SecOps | Azure Key Vault (Managed Secret) |
| `DATABASE_URL` | Cadena de conexión cifrada (PostgreSQL con flag `sslmode=require`). | Backend Python / Go | DBA / SecOps | Azure Key Vault (Connection String) |
| `SUPABASE_URL` | URL de la instancia de base de datos y autenticación de Supabase. | Backend / Frontend | DevOps | Key Vault / Vite Build Settings |
| `SUPABASE_ANON_KEY` | Llave pública anónima de Supabase para operaciones del frontend. | Frontend React | DevOps | Vite Environment (`VITE_SUPABASE_ANON_KEY`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Llave de administración con bypass de RLS para tareas de mantenimiento. | Backend Python (Admin) | SecOps | Azure Key Vault (Acceso Crítico) |
| `JWT_SECRET_KEY` | Semilla criptográfica (mínimo 256 bits) para firma de tokens de sesión. | Backend FastAPI | SecOps | Azure Key Vault (Managed Secret) |
| `STORAGE_BUCKET_NAME` | Nombre del contenedor de objetos donde reposan los PDFs originales. | Backend / Conectores | DevOps | App Service Environment Variables |
| `STORAGE_ACCESS_KEY` | Llave de acceso al almacenamiento de objetos (si no usa Managed Identity).| Backend Python | SecOps | Azure Key Vault (Managed Secret) |
| `VITE_API_URL` | URL pública HTTPS del backend FastAPI para consumo de la UI React. | Frontend UI | DevOps | Configuración de Build de Vite |

---

## 5. Cifrado y Políticas de Protección de Datos

### 5.1. Cifrado en Reposo y en Tránsito
* **En Tránsito**:
  * Obligatoriedad de **TLS 1.3** (mínimo TLS 1.2) en todas las comunicaciones externas e inter-servicios.
  * Deshabilitación explícita de suites criptográficas obsoletas (RC4, 3DES, CBC).
  * Redirección forzada de HTTP a HTTPS mediante encabezados `Strict-Transport-Security` (HSTS).
* **En Reposo**:
  * Bases de datos relacionales y vectoriales cifradas mediante **AES-256** administrado por infraestructura.
  * Almacenamiento de documentos con cifrado del lado del servidor (SSE-KMS o SSE-S3 con claves administradas por el cliente - CMK opcional).

### 5.2. Sanitización y Prevención de Fugas de Información
* **Políticas en Pruebas Automatizadas**:
  * Las suites de prueba (`pytest`, `npm test`) deben utilizar datos simulados (*mock data* o fixtures) sintéticos.
  * Está estrictamente prohibido utilizar copias de expedientes jurídicos reales de clientes como archivos de prueba en repositorios o pipelines de CI/CD.
* **Sanitización de Salidas de Error**:
  * Los mensajes de error devueltos por la API ante excepciones no controladas deben retornar códigos de error opacos y Correlation IDs sin exponer trazas de pila (*stacktraces*), rutas internas de carpetas ni detalles de consultas SQL.

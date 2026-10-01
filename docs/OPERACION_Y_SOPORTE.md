# DocumentForge — Guía de Operación, Mantenimiento y Soporte

Este documento establece las directrices operativas, procedimientos de mantenimiento preventivo y correctivo, y protocolos de soporte técnico para la plataforma **DocumentForge**. Está dirigido a ingenieros de operaciones, confiabilidad de sitio (SRE), administradores de sistemas y equipos de soporte técnico L1/L2/L3.

---

## 1. Descripción General de DocumentForge y Arquitectura del Sistema

### 1.1. Propósito y Misión de la Plataforma
**DocumentForge** es una plataforma corporativa segura de búsqueda documental, extracción semántica y recuperación aumentada con IA (RAG), diseñada para estudios jurídicos, departamentos de compliance y sectores con alta exigencia documental y estricto secreto profesional.

* **Ingestión multicanal controlada**: Conexión a repositorios de SharePoint Online, OneDrive for Business y Google Drive con sincronización incremental.
* **Procesamiento y enriquecimiento**: Aplicación de reconocimiento óptico de caracteres (OCR) multilingüe, extracción de entidades jurídicas/financieras y cálculo de embeddings vectoriales.
* **Recuperación con citas directas verificables**: Respuestas formuladas exclusivamente con base en evidencia documental verificable, indicando documento origen, página exacta y fragmento textual.
* **Límites éticos y legales irrenunciables**:
  * La plataforma **nunca** emite asesoría jurídica vinculante ni conclusiones no respaldadas.
  * Prohibición absoluta de alucinación o inferencia inductiva sin evidencia textual directa en el corpus.

### 1.2. Arquitectura de Servicios y Flujo de Datos
La solución opera bajo una arquitectura desacoplada de alto rendimiento y bajo acoplamiento:

```
[Fuentes Externas] (SharePoint / OneDrive / Google Drive)
        │
        ▼ (Sincronización incremental / Delta tokens)
[Conectores de Ingestión - C# .NET Core]
        │
        ▼ (Tareas y eventos encolados con Idempotencia)
[Orquestador y Colas de Tareas - Go]
        │
        ▼ (Extracción, OCR, Embeddings y RAG)
[Motor de Visión y Procesamiento de IA - Python 3.10+] ───► [Azure OpenAI (GPT-4.1-mini)]
        │                                                     (Zero-Data Retention)
        ├─────────────────────────────┬─────────────────────────────┐
        ▼                             ▼                             ▼
[Almacenamiento Seguro WORM]  [PostgreSQL + pgvector]      [Base de Datos Relacional]
(Documentos Originales)       (Embeddings & Índices Híbridos) (Metadatos, Casos, RBAC)
        │
        ▼ (Consultas filtradas por Caso/Organización/Rol)
[Buscador y Visor Side-by-Side - TypeScript / React 19]
```

* **Conectores de Ingesta (C# / .NET Core)**: Conexión con Microsoft Graph API y Google Workspace API; procesamiento de eventos webhook y control de tokens de sincronización incremental (*delta tokens*).
* **Orquestador y Colas de Despacho (Go)**: Despacho de tareas con garantía de idempotencia, control de concurrencia y tolerancia a fallos.
* **Motor Documental y Pipeline de IA (Python 3.10+ / FastAPI)**: Extracción con PyMuPDF, filtrado de imágenes con OpenCV/Tesseract, generación de embeddings y búsqueda híbrida (léxica BM25 + vectorial densa) con reranking.
* **Consola de Usuario y Búsqueda (TypeScript / React 19 + Vite)**: Búsqueda facetada (caso, cliente, tipo documental, jurisdicción, fecha), visor side-by-side de citas y gestión de roles.
* **Almacenamiento de Originales**: Almacenamiento seguro de objetos con versionado inmutable (WORM), utilizado en modo de solo lectura para auditoría y visualización de citas.

---

## 2. Tecnologías Implementadas, Dependencias y Verificación

### 2.1. Stack Tecnológico y Dependencias Principales

| Capa | Lenguaje / Framework | Dependencias Clave | Propósito Operativo |
|---|---|---|---|
| **Pipeline IA & Backend** | Python 3.10+ / FastAPI | `PyMuPDF (>=1.23)`, `OpenCV-headless`, `pydantic (>=2.10)`, `openai (>=1.40)`, `SQLAlchemy`, `supabase-py` | OCR, extracción de metadatos, embeddings, endpoints de consulta y autollenado. |
| **Frontend & UI** | React 19 / TypeScript 6 / Vite | `lucide-react`, `@supabase/supabase-js`, `oxlint` | Interfaz de búsqueda, visor de citas side-by-side y panel de administración. |
| **Persistencia & Vectorial** | PostgreSQL (Supabase / Neon) | Extensión `pgvector`, esquema relacional con RBAC | Almacenamiento de perfiles, permisos, trazabilidad y búsqueda semántica híbrida. |
| **Motor LLM Corporativo** | Azure OpenAI Service | Despliegue dedicado `gpt-4.1-mini` (API Version `2024-12-01-preview`) | Generación fundamentada de respuestas con citas y correspondencia determinística. |

### 2.2. Procedimiento de Ejecución de Pruebas y Validaciones

Antes de autorizar cualquier pase a producción o mantenimiento, deben ejecutarse las suites de validación automatizadas en el entorno local o de integración continua:

#### Validación del Backend (Python)
```powershell
# Ejecución de la suite completa de pruebas unitarias y de integración
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Validación específica de endurecimiento de autenticación y sesiones
.\.venv\Scripts\python.exe tests/test_auth_hardening.py

# Validación de consistencia de endpoints y contratos de API
.\.venv\Scripts\python.exe tests/test_backend_api.py

# Validación de reglas de validación y extracción documental
.\.venv\Scripts\python.exe tests/test_filling_validator.py
```

#### Validación del Frontend (TypeScript & React)
```powershell
cd frontend

# Pruebas automatizadas de lógica y contratos
npm test

# Verificación de tipado estricto
npx tsc -b

# Linter de código estático (Oxlint)
npm run lint

# Verificación de compilación limpia de producción
npm run build
```

#### Verificación de Integridad de Código
```powershell
# Verificar que no existan espacios en blanco corruptos ni conflictos de merge
git diff --check

# Verificar estado del árbol de trabajo
git status --short
```

---

## 3. Guía de Mantenimiento Preventivo y Operativo

### 3.1. Monitoreo y Telemetría del Servicio
La supervisión de DocumentForge debe centrarse en la estabilidad de los pipelines de procesamiento y la salud de las integraciones:

1. **Endpoint de Salud (Healthcheck)**:
   * URL: `GET /api/health`
   * Código esperado: `200 OK`
   * Frecuencia de sondeo recomendada: cada 30 segundos mediante agente de monitoreo externo.
   * Valida conectividad hacia la base de datos, servicio de almacenamiento de objetos y disponibilidad de endpoints de IA.
2. **Métricas Clave de Rendimiento (KPIs)**:
   * **Latencia de OCR**: Tiempo medio de rasterizado y extracción de texto por página (umbral de alerta: > 2.5 segundos/página).
   * **Latencia de Búsqueda RAG**: Tiempo total entre consulta del usuario y entrega de respuesta con citas (umbral de alerta: > 4.0 segundos).
   * **Tasa de Errores HTTP 5xx**: Debe mantenerse por debajo del 0.05% de las transacciones totales.
   * **Consumo de Memoria en Workers de Visión**: Monitoreo estricto de PyMuPDF y OpenCV para detectar fugas de memoria (*memory leaks*) en documentos de más de 300 páginas.

### 3.2. Política de Logs: Qué está Permitido y Qué está Prohibido

> [!CAUTION]
> **ADVERTENCIA CRÍTICA DE CONFIDENCIALIDAD Y SECRETO PROFESIONAL**
> Los documentos de clientes, textos extraídos, fragmentos contractuales, datos de identificación personal (PII) y respuestas de IA **JAMÁS** deben registrarse en archivos de log, herramientas de observabilidad ni consolas de depuración.

| Categoría | Estado | Ejemplos de Datos |
|---|---|---|
| **Contenido Documental** | 🚫 **ESTRICTAMENTE PROHIBIDO** | Texto de contratos, cláusulas arbitrales, montos, nombres de clientes, anexos legales, respuestas del LLM, fragmentos de OCR. |
| **Credenciales y Secretos** | 🚫 **ESTRICTAMENTE PROHIBIDO** | API keys, contraseñas, bearer tokens, refresh tokens, cadenas de conexión, secretos de cliente OAuth. |
| **Identificadores Personales** | 🚫 **ESTRICTAMENTE PROHIBIDO** | Cédulas, números de pasaporte, direcciones de domicilio, teléfonos privados de directores. |
| **Metadatos Técnicos** | ✅ **PERMITIDO** | Correlation ID (UUIDv4), Timestamp ISO 8601 en UTC, Código de estado HTTP, Duración en ms, ID de Caso (numérico/hash), Tipo de evento (`DOC_INGESTED`, `QUERY_EXECUTED`), Número de páginas procesadas. |

### 3.3. Política de Respaldos (Backups)
* **Base de Datos Relacional y Metadatos (PostgreSQL)**:
  * Respaldos automáticos continuos (*Point-in-Time Recovery* - PITR) con retención de 7 días.
  * Exportación diaria cifrada (`pg_dump`) almacenada en un bucket secundario geodistribuido con bloqueo de eliminación.
* **Índices Vectoriales**:
  * Reconstruibles determinísticamente desde los fragmentos almacenados.
  * Snapshot semanal del espacio de embeddings para recuperación acelerada en caso de desastre.
* **Documentos Originales**:
  * Almacenamiento en repositorio de objetos con versionado activo y política WORM (*Write Once, Read Many*) para garantizar inalterabilidad legal.

### 3.4. Manejo de Errores e Idempotencia
* **Idempotencia en Ingestión**: Cada archivo procesado genera un hash SHA-256 de su contenido binario. Si un evento de ingestión se reintenta, el sistema detecta el hash existente y evita duplicar registros o incurrir en costos redundantes de OCR.
* **Reintentos con Backoff Exponencial**:
  * Fallos transitorios de red o rate-limits de IA (HTTP 429) implementan reintentos automáticos con cálculo de retroceso exponencial (`2^n + jitter`) hasta un máximo de 5 intentos.
* **Cola de Mensajes Muertos (Dead-Letter Queue - DLQ)**:
  * Documentos corruptos, con contraseñas de apertura no soportadas o con fallos de OCR persistentes se aíslan en la cola DLQ para análisis manual por L3, sin detener la sincronización del resto de archivos.

---

## 4. Guía de Soporte Técnico y Diagnóstico

### 4.1. Matriz de Resolución de Problemas Frecuentes

#### Caso 1: Error 429 "Too Many Requests" en Procesamiento con IA
* **Síntoma**: Fallo intermitente al indexar lotes grandes de documentos o al autollenar campos con IA.
* **Causa**: Superación del límite de tokens por minuto (TPM) o peticiones por minuto (RPM) en el recurso de Azure OpenAI.
* **Solución**:
  1. Verificar el consumo en Azure Portal > Azure OpenAI > Metrics.
  2. Confirmar que el worker esté respetando el encabezado `Retry-After`.
  3. Si la carga es legítima y sostenida, tramitar el escalado de TPM en el despliegue de Azure OpenAI.

#### Caso 2: Documento Escaneado no Produce Resultados de Búsqueda
* **Síntoma**: Un archivo PDF está visible en el expediente, pero sus cláusulas no aparecen en las búsquedas ni respuestas.
* **Causa**: Documento escaneado como imagen de baja resolución (< 150 DPI), rotado 90°/180°, o con contraste insuficiente para OCR.
* **Solución**:
  1. Revisar los logs técnicos para verificar si el archivo generó una alerta de "Low OCR Confidence".
  2. Comprobar si el documento está en la cola DLQ.
  3. Solicitar al usuario una copia digital nativa o un escaneo a 300 DPI en escala de grises.

#### Caso 3: Error de Autenticación / Sesión Expirada en Portal
* **Síntoma**: El usuario recibe "Credenciales incorrectas o usuario inactivo" o desconexiones recurrentes.
* **Causa**: Token de sesión revocado por inactividad, clock skew entre el servidor y el cliente, o perfil desactivado por el administrador.
* **Solución**:
  1. Verificar en la base de datos que el campo `is_active` del perfil esté en `true`.
  2. Confirmar sincronización NTP del servidor.
  3. Solicitar al usuario que borre caché de sesión y vuelva a ingresar mediante el flujo seguro.

### 4.2. Protocolo de Recopilación de Información para Soporte (L1 / L2)
Cuando un usuario reporte una incidencia, el equipo de soporte debe recopilar **únicamente**:
* **Correlation ID / Request ID** del error (proporcionado en el modal de alerta o consola de usuario).
* **Fecha y hora exacta** del evento (especificando zona horaria).
* **ID del Caso o Expediente** (código alfanumérico interno, sin nombres de personas ni detalles del litigio).
* **Acción realizada**: ingestión, búsqueda, visor de citas o autollenado.
* **Mensaje de error técnico exacto** retornado por la interfaz.

> [!WARNING]
> **REGLA DE ORO PARA EL EQUIPO DE SOPORTE:**
> Está estrictamente prohibido solicitar al cliente copias de contratos por correo, fotos de pantallas que contengan fragmentos jurídicos, o credenciales de acceso. Toda depuración debe realizarse mediante identificadores opacos y trazas técnicas.

### 4.3. Niveles de Severidad y Matriz de Escalamiento

| Severidad | Definición | Tiempo de Respuesta (SLA) | Escalamiento |
|---|---|---|---|
| **P1 - Crítico** | Plataforma completamente inaccesible; falla total de autenticación; sospecha de vulnerabilidad de seguridad o fuga de datos. | < 15 minutos | Notificación inmediata a SRE Lead, SecOps y Gerencia Técnica. |
| **P2 - Alto** | Falla en conectores de Microsoft Graph (bloqueo total de ingestión); imposibilidad de consultar citas en expedientes activos. | < 1 hora | Escalamiento a Ingeniero Backend L3 y Administrador de Nube. |
| **P3 - Medio** | Degradación de rendimiento en OCR; lentitud en respuestas RAG; error en un documento aislado enviado a DLQ. | < 4 horas | Asignación a equipo de soporte L2 y desarrollo. |
| **P4 - Bajo** | Dudas operativas de usuarios; sugerencias de interfaz; ajustes cosméticos. | < 24 horas | Atendido por Mesa de Ayuda L1. |

---

## 5. Checklists de Operación

### 5.1. Checklist de Pre-Producción (Go-Live Readiness)
Antes de habilitar el servicio para un nuevo cliente u organización, verificar punto por punto:
- [ ] **Aislamiento Multi-Tenant**: Confirmar que los filtros por `organization_id` y `case_id` estén activos en todas las consultas a nivel de base de datos y vector store.
- [ ] **Validación de Pruebas**: Todas las pruebas unitarias y de integración de backend y frontend pasan al 100% (`pytest` y `npm test`).
- [ ] **Gestión de Secretos**: No existen variables `.env` commiteadas ni credenciales en código duro; todas las variables requeridas están inyectadas desde el gestor de secretos seguro.
- [ ] **Configuración de Azure OpenAI**: Despliegue activo con política de *Zero Data Retention* (no almacenamiento de prompts por parte del proveedor).
- [ ] **Integración Microsoft Entra**: Aplicación registrada con permisos mínimos `Sites.Selected`, consentida por el administrador del tenant del cliente.
- [ ] **Salud de Endpoints**: Endpoint `/api/health` retorna HTTP 200 OK y latencias dentro de norma.
- [ ] **Sanitización de Logs**: Se ha inspeccionado el flujo de logging para garantizar que ninguna petición imprima PII, texto de documentos ni tokens.

### 5.2. Checklist de Respuesta ante Incidentes de Seguridad
En caso de detectar anomalías, accesos no autorizados o fallos de seguridad:
- [ ] **Paso 1: Contención Inmediata**: Revocar tokens de sesión activos de las cuentas involucradas y deshabilitar temporalmente la sincronización del conector afectado.
- [ ] **Paso 2: Rotación de Secretos**: Si se sospecha compromiso de credenciales de servicio (ej. Client Secret de Azure AD o API Key de Azure OpenAI), ejecutar el procedimiento de rotación de emergencia en el gestor de secretos.
- [ ] **Paso 3: Aislamiento Forense**: Exportar logs del sistema (metadatos técnicos y trazas de acceso) a un bucket de retención forense inmutable.
- [ ] **Paso 4: Auditoría de Acceso a Documentos**: Consultar la tabla de auditoría para determinar qué documentos o casos fueron consultados por el usuario o token comprometido.
- [ ] **Paso 5: Notificación y Resolución**: Informar al Oficial de Privacidad y emitir informe post-mortem con causa raíz y medidas correctivas.

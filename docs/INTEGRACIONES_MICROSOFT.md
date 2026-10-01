# DocumentForge — Guía de Integración con el Ecosistema Microsoft

Este documento describe la arquitectura, mecanismos de autenticación, modelo de permisos de mínimo privilegio, sincronización incremental y gestión de ciclo de vida de tokens para la integración de **DocumentForge** con **SharePoint Online**, **OneDrive for Business** y **Microsoft Graph API**.

---

## 1. Alcance y Arquitectura de la Integración

### 1.1. Propósito de la Conectividad
DocumentForge permite a estudios jurídicos y departamentos corporativos centralizar la ingesta, búsqueda e indexación semántica de su acervo documental almacenado en la nube de Microsoft 365, garantizando:
* Conservación estricta de la estructura de carpetas, metadatos de expediente y fechas de vigencia.
* Detección automática y procesamiento desatendido de adiciones, modificaciones y bajas de documentos (contratos, anexos, poderes y fallos).
* Uso **exclusivo de APIs oficiales de Microsoft** (Microsoft Graph API v1.0), sin emplear librerías no soportadas, scraping ni accesos no autorizados.

### 1.2. Componentes de la Integración
* **Conector de Ingesta (C# / .NET Core)**: Servicio especializado que interactúa con Microsoft Graph SDK / REST API v1.0, gestiona la suscripción a eventos de cambio y ejecuta la descarga en memoria.
* **Controlador de Sincronización Incremental**: Administra los cursores de cambio (*delta tokens*), garantizando que solo los archivos nuevos o modificados sean procesados.
* **Almacenamiento Temporal Seguro en Memoria**: Procesamiento de flujos de bytes (*streams*) en memoria volátil cifrada sin persistencia no autorizada en disco rígido.

---

## 2. Autenticación y Registro en Microsoft Entra ID (Azure AD)

### 2.1. Registro de la Aplicación en Entra ID
Para habilitar la conectividad, el administrador del tenant del cliente debe registrar la aplicación en el portal de Microsoft Entra:
* **Tipo de Cuenta Soportada**: Cuentas en este directorio organizativo únicamente (Single Tenant) o Multi-tenant según el acuerdo de servicio.
* **Identificadores Clave (Generados por Entra ID)**:
  * `Application (client) ID`: Identificador único de la aplicación.
  * `Directory (tenant) ID`: Identificador único del tenant de Microsoft 365 del cliente.
  * `Client Secret` o `Client Certificate`: Secreto criptográfico o certificado X.509 para autenticación desatendida.

### 2.2. Flujos OAuth 2.0 Soportados

#### A. Flujo de Credenciales de Cliente (Client Credentials Grant - Daemon / Background Sync)
Utilizado por el worker desatendido en C# para la sincronización periódica e indexación masiva:
* **Endpoint de Token**: `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
* **Parámetros de la solicitud**:
  * `grant_type`: `client_credentials`
  * `client_id`: ID de la aplicación.
  * `client_secret`: Secreto almacenado exclusivamente en el gestor de secretos (Key Vault).
  * `scope`: `https://graph.microsoft.com/.default`

#### B. Flujo de Código de Autorización con PKCE (Authorization Code Flow)
Utilizado cuando un abogado o administrador vincula una biblioteca personal de OneDrive o un sitio específico de SharePoint mediante consentimiento interactivo:
* **Endpoint de Autorización**: `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize`
* **Parámetros**:
  * `response_type`: `code`
  * `code_challenge_method`: `S256`
  * `scope`: `Files.Read offline_access User.Read`

---

## 3. Modelo de Permisos de Mínimo Privilegio (Least Privilege)

Para mitigar riesgos de seguridad y cumplir con normativas de protección de datos, DocumentForge rechaza el uso de permisos omnipotentes (`Sites.FullControl.All` o `Files.ReadWrite.All`). Se implementa la siguiente política estricta:

### 3.1. Permisos de Aplicación (Background Worker)

| Permiso de API | Tipo | Justificación Operativa | Impacto de Seguridad |
|---|---|---|---|
| `Sites.Selected` | Application | **Mejor práctica de seguridad recomendada por Microsoft**. La aplicación solo puede acceder a los sitios de SharePoint que el administrador le haya asignado explícitamente mediante una llamada previa con rol de lectura. | **Aislamiento total**: la aplicación queda ciega ante cualquier otro sitio del tenant. |
| `Files.Read.All` | Application | Requerido únicamente cuando el cliente no utiliza `Sites.Selected` y requiere indexar múltiples bibliotecas documentales a nivel de tenant. Debe contar con Consentimiento Administrativo (*Admin Consent*). | Acceso de solo lectura a archivos de la organización. |

#### Configuración de `Sites.Selected` (Procedimiento de Aislamiento)
Una vez otorgado `Sites.Selected`, el administrador de Microsoft 365 del cliente otorga permisos exclusivos al sitio del estudio jurídico mediante Graph API:
```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
Content-Type: application/json

{
  "roles": ["read"],
  "grantedToIdentities": [{
    "application": {
      "id": "{client-id-de-documentforge}",
      "displayName": "DocumentForge Connector"
    }
  }]
}
```

### 3.2. Permisos Delegados (Flujo Interactivo)

| Permiso de API | Tipo | Justificación Operativa |
|---|---|---|
| `Files.Read` | Delegated | Permite leer archivos a los que el usuario autenticado ya tiene acceso legítimo. |
| `offline_access` | Delegated | Permite obtener un *refresh token* para renovar el acceso sin interrumpir al usuario. |
| `User.Read` | Delegated | Lectura del perfil básico (nombre corporativo y correo) para trazabilidad. |

---

## 4. Sincronización Incremental con Delta Query

### 4.1. Funcionamiento de Microsoft Graph Delta
En lugar de escanear recursivamente miles de archivos en cada ejecución, DocumentForge utiliza la API oficial de **Delta Query**:
* **URL Inicial**: `https://graph.microsoft.com/v1.0/sites/{site-id}/drive/root/delta`
* **Proceso de Paginación**:
  1. La API devuelve páginas con metadatos de documentos y una propiedad `@odata.nextLink` si hay más páginas en el lote actual.
  2. Al llegar al final del conjunto de cambios, la API entrega una propiedad `@odata.deltaLink` que contiene el *delta token* codificado.
  3. DocumentForge almacena de forma persistente este `@odata.deltaLink` en su base de datos relacional asociado al expediente.
  4. En la siguiente ejecución, el conector consulta directamente ese `@odata.deltaLink`, obteniendo **únicamente** los archivos creados, editados o eliminados desde la última sincronización.

### 4.2. Detección de Cambios e Idempotencia
Cada documento recibido en el payload de cambio contiene:
* `id`: Identificador único inmutable del item en SharePoint/OneDrive.
* `eTag` / `cTag`: Identificadores de versión del contenido y metadatos.
* `file`: Propiedad que contiene el hash criptográfico oficial calculado por Microsoft 365 (`hashes.quickXorHash` o `hashes.sha256Hash`).
* `deleted`: Indicador si el archivo fue removido en la fuente de origen.

**Garantía de Idempotencia**:
* Si el `eTag` coincide con el registro previo en DocumentForge, el archivo se omite de inmediato, evitando costos computacionales de descarga, OCR y cálculo de embeddings.
* Si el item presenta la marca `deleted`, DocumentForge marca el documento como inactivo en el índice de búsqueda y archiva sus embeddings correspondientes.

### 4.3. Suscripciones Webhook (Notificaciones en Tiempo Real)
Para evitar sondeos continuos por polling, el conector registra suscripciones de notificación en Graph API:
* **Endpoint de Registro**: `POST https://graph.microsoft.com/v1.0/subscriptions`
* **Recurso**: `sites/{site-id}/drive/root`
* **Tipo de Cambio**: `updated`
* **Validación de Token**: El webhook de DocumentForge valida el `validationToken` de Microsoft antes de aceptar la suscripción.
* **Tiempo de Vida de Suscripción**: Máximo 4230 minutos (~3 días) para recursos de Drive. El orquestador ejecuta una tarea cron diaria para renovar las suscripciones activas.

---

## 5. Ciclo de Vida y Renovación de Tokens

### 5.1. Duración y Estrategia de Renovación
* **Access Tokens (JWT)**: Emitidos por Microsoft Entra ID con un tiempo de vida estándar de 60 a 90 minutos.
* **Renovación Proactiva**:
  * El conector evalúa la marca temporal de expiración (`exp`) en cada petición.
  * Si faltan menos de **5 minutos** para el vencimiento del token, se ejecuta una solicitud de renovación asíncrona antes de enviar la siguiente llamada a Graph API.
* **Manejo de Refresh Tokens**:
  * Almacenados de forma cifrada en la base de datos mediante clave de envoltura (Envelope Encryption).
  * Si un refresh token es revocado (ej. por cambio de contraseña corporativa del usuario delegado), el sistema notifica al administrador para re-autenticación limpia.

---

## 6. Matriz de Errores Frecuentes y Diagnóstico

### 6.1. Código HTTP 401 Unauthorized (`InvalidAuthenticationToken` / `TokenExpired`)
* **Diagnóstico**: El token de acceso ha expirado, el secreto del cliente ha caducado en Entra ID, o existe un desfase horario severo (*clock skew* > 5 minutos) en el servidor.
* **Procedimiento**:
  1. Verificar fecha de vigencia del *Client Secret* en el portal de Entra ID.
  2. Comprobar la sincronización del servicio NTP en el servidor de DocumentForge.
  3. Forzar purga de la caché de tokens en memoria para obligar a una nueva emisión mediante Client Credentials.

### 6.2. Código HTTP 403 Forbidden (`AccessDenied`)
* **Diagnóstico**: La aplicación no cuenta con Consentimiento Administrativo concedido, o el sitio de SharePoint solicitado no ha sido asignado al permiso `Sites.Selected`.
* **Procedimiento**:
  1. Revisar en Entra ID > Enterprise Applications > Permissions que el estado indique "Granted for [Organización]".
  2. Ejecutar consulta de diagnóstico de permisos sobre el sitio específico de SharePoint para verificar la presencia del Application ID de DocumentForge con rol `read`.

### 6.3. Código HTTP 429 Too Many Requests (`Throttling`)
* **Diagnóstico**: Microsoft Graph ha limitado la tasa de peticiones concurrentes para proteger la infraestructura del tenant.
* **Procedimiento**:
  1. Inspeccionar el encabezado de respuesta HTTP `Retry-After` (especifica los segundos exactos de espera requeridos).
  2. El conector pausa automáticamente el hilo de sincronización durante el intervalo estipulado.
  3. Aplicar un factor de *jitter* aleatorio (+100 a 500 ms) para evitar reintentos sincronizados en ráfaga.

### 6.4. Código HTTP 410 Gone (`ResyncRequired`)
* **Diagnóstico**: El `deltaToken` almacenado ha caducado (su validez máxima es de 3 meses de inactividad) o se produjo un cambio estructural masivo en la biblioteca que invalidó el cursor incremental.
* **Procedimiento**:
  1. El sistema descarta el `deltaLink` obsoleto.
  2. Se inicia una **resincronización completa controlada** (*full sweep*).
  3. Los hashes de los archivos ya indexados previenen re-procesar documentos sin cambios.

---

## 7. Advertencias de Privacidad y Manejo de Archivos

> [!CAUTION]
> **POLÍTICA INFRANQUEABLE DE AISLAMIENTO Y LIMPIEZA DE DATOS**
> 1. **Cero almacenamiento en disco temporal no cifrado**: Las descargas desde Microsoft Graph deben procesarse en flujos de memoria (`MemoryStream` / buffers en RAM) o en volúmenes efímeros cifrados con eliminación atómica inmediata al finalizar el OCR.
> 2. **Prohibición de Logs de Contenido**: Ningún nombre de archivo de cliente, contenido contractual, cláusula ni fragmento de texto puede registrarse en los logs de los conectores de Microsoft. Los logs solo deben registrar: `TenantID`, `SiteID`, `ItemCount`, `BytesReceived`, `DurationMs` y `CorrelationID`.
> 3. **No Retención por Microsoft de Respuestas**: Las peticiones enviadas a Graph API son operaciones puras de lectura hacia el tenant del propio cliente. No se transmite información hacia terceros ni hacia servicios no aprobados.

# 📄 AutoForm PDF (SmartFormAI)

**AutoForm PDF** es una solución web integral y modular diseñada para automatizar el llenado de formularios PDF planos (no interactivos) mediante un editor visual intuitivo (**WYSIWYG**), herramientas de formato tipográfico, estampado de firmas/imágenes y un gestor de datos basado en el patrón de **Revelación Progresiva (Progressive Disclosure)**.

---

## ✨ Características Principales

### 1. 🎨 Editor Visual (*Draw-to-Map*)
* **Mapeo con el Ratón:** Selecciona cualquier variable y dibuja recuadros directamente sobre las celdas del documento.
* **Arrastrar y Mover con Clic Derecho:** Reubica y ajusta la posición de cualquier recuadro arrastrándolo con el clic derecho.
* **Barra de Formato Tipográfico:**
  * **Fuentes Populares:** *Arial*, *Calibri*, *Helvetica*, *Times New Roman*.
  * **Tamaño:** Selector con valores en puntos (`pt`) y botones de incremento/decremento (`+` / `-`).
  * **Negrilla:** Interruptor para aplicar texto en negrita.
  * **Color:** Paleta de colores preestablecidos (*Negro*, *Azul Oscuro*, *Azul Rey*, *Rojo*, *Verde*) y selector de color hexadecimal libre.
  * **Edición Directa de Texto:** Modifica el texto en vivo de cualquier recuadro seleccionado.
  * **Estampado de Firmas / Imágenes:** Sube cualquier firma, sello o logotipo en formato PNG/JPG y estampa su marco proporcional en el PDF.

### 2. 🗂️ Gestor de Datos con Revelación Progresiva (2 Columnas)
* **Columna Izquierda (Panel de Entrada):**
  * **Dato Empresa:** Clasificación en 4 categorías (`🪪 ID`, `📍 Contacto`, `🏦 Banco`, `❓ Otros`) con sugerencias automáticas.
  * **Perfil Empleador:** Ficha estructurada (Nombre, Apellido, Correo/Gmail, Celular) y campos personalizados ilimitados (clave/valor).
* **Columna Derecha (Visualizador en Acordeón):**
  * **Acordeón Empresa:** Pestañas internas para visualizar y gestionar cada categoría.
  * **Acordeones de Perfiles:** Generación dinámica debajo del bloque de empresa con vista colapsable individual.

### 3. ⚙️ Motor de Estampado de Alta Fidelidad
* Renderizado de páginas PDF a imágenes de alta definición vía **PyMuPDF**.
* Detección y emparejamiento automático de la fuente predominante del documento original.
* Auto-ajuste de tamaño de texto para evitar desbordamiento de celdas.

---

## 🏛️ Estructura del Proyecto

```text
smartformai/
├── backend/
│   ├── data/                 # Almacenamiento local de perfiles y mapeos JSON
│   ├── pdf_filling_agent/    # Motor de visión y procesamiento PDF (PyMuPDF + OpenCV)
│   │   ├── cv_detector.py
│   │   └── visual_processor.py
│   └── main.py               # Servidor API FastAPI
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── data-manager/ # Interfaz modular de revelación progresiva
│   │   │   │   ├── DataEntryPanel.tsx
│   │   │   │   ├── DataAccordionViewer.tsx
│   │   │   │   └── DataManagerModal.tsx
│   │   │   ├── Navbar.tsx
│   │   │   ├── Toolbar.tsx   # Barra de fuentes, colores, tamaños y firmas
│   │   │   ├── Sidebar.tsx   # Listado de variables mapeables
│   │   │   ├── PDFCanvas.tsx # Visor interactivo Draw-to-Map
│   │   │   └── ResultModal.tsx
│   │   ├── types.ts          # Modelos de datos TypeScript
│   │   ├── api.ts            # Cliente HTTP
│   │   └── App.tsx
│   └── package.json
├── input/                    # Plantillas PDF disponibles para mapear
├── output/                   # Formularios PDF generados
├── tests/                    # Pruebas de integración automatizadas
├── run_demo.bat              # Script de inicio rápido (1 clic) para Windows
├── run_demo.ps1              # Script de inicio rápido para PowerShell
├── pyproject.toml            # Dependencias del Backend
└── README.md
```

---

## 🚀 Inicio Rápido

### Opción 1: Ejecución con 1 Clic (Recomendado)
Haz doble clic sobre el archivo:
```bash
run_demo.bat
```
*(O ejecuta `.\run_demo.ps1` en PowerShell).*

Abre tu navegador en: **`http://localhost:5173`**

---

### Opción 2: Ejecución Manual

#### 1. Backend (FastAPI)
```powershell
# En la raíz del proyecto
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend (React + Vite)
```powershell
cd frontend
npm install
npm run dev
```

---

## 🧪 Pruebas Automatizadas

Para validar que todos los endpoints y el motor de estampado funcionan correctamente:

```powershell
.\.venv\Scripts\python.exe tests/test_backend_api.py
```

---

## 📄 Licencia

Distribuido bajo la Licencia MIT.

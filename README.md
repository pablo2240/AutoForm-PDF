<div align="center">

# 🤖 AutoForm PDF — SmartFormAI

**Llenado inteligente de formularios PDF con IA · Editor Visual WYSIWYG · API FastAPI**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vite.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-GPT--4.1--mini-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/products/ai-services/openai-service)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📌 ¿Qué es?

**AutoForm PDF** es una solución web full-stack para automatizar el llenado de formularios PDF. Combina un **editor visual interactivo** (draw-to-map), un **gestor de datos empresariales** con revelación progresiva y un **agente de IA** (Azure OpenAI GPT-4.1-mini) que identifica inteligentemente qué campos llenar, con qué datos y qué secciones ignorar.

---

## ✨ Características

### 🤖 Autollenado con IA
- Agente CEO con perfil completo de la empresa y representante legal
- Mapeo determinístico de +22 reglas antes de consultar al LLM
- Exclusión automática de secciones: **PEP**, **Solo para Clientes**, **Uso exclusivo de la entidad**, **Extranjeros**
- Prevención de desplazamiento de valores (Nacionalidad ≠ Teléfono)
- Soporte para formularios AcroForm (interactivos) y PDFs planos

### 🎨 Editor Visual WYSIWYG
- **Draw-to-Map:** dibuja recuadros sobre celdas del PDF con el ratón
- **Arrastrar con clic derecho** para reubicar elementos
- **Barra de formato:** fuentes (Arial, Calibri, Helvetica, Times), tamaño `pt`, negrilla, color libre
- **Estampado de firmas/imágenes:** sube PNG/JPG y posiciona en el documento

### 🗂️ Gestor de Datos Empresariales
- Panel de entrada clasificado en `🪪 ID`, `📍 Contacto`, `🏦 Banco`, `❓ Otros`
- Perfil del representante legal con campos personalizados
- Acordeón de visualización con revelación progresiva (2 columnas)

### ⚙️ Motor de Estampado
- Renderizado de alta definición vía **PyMuPDF**
- Detección de fuente predominante del documento original
- Auto-ajuste de tamaño para evitar desbordamiento de celdas

---

## 🏗️ Arquitectura

```
smartformai/
├── 🐍 backend/
│   ├── data/                       # Perfiles y mapeos JSON
│   ├── pdf_filling_agent/
│   │   ├── agent.py                # Motor IA: determinístico + LLM Azure OpenAI
│   │   ├── field_dictionary.py     # Sinónimos de campos + reglas de exclusión
│   │   ├── knowledge_base.py       # Contexto CEO / perfil empresa
│   │   ├── visual_processor.py     # Overlay de texto en PDF plano
│   │   └── pdf_processor.py        # AcroForm writer (PyMuPDF)
│   └── main.py                     # API FastAPI (endpoints REST)
│
├── ⚛️ frontend/
│   └── src/
│       ├── components/
│       │   ├── data-manager/       # Panel revelación progresiva
│       │   ├── PDFCanvas.tsx       # Visor draw-to-map interactivo
│       │   ├── Toolbar.tsx         # Barra de formato tipográfico
│       │   ├── Sidebar.tsx         # Variables mapeables
│       │   └── ResultModal.tsx     # Modal de descarga
│       ├── api.ts                  # Cliente HTTP
│       └── App.tsx
│
├── 📁 input/                       # Plantillas PDF de entrada
├── 📁 output/                      # Formularios PDF generados
├── 🧪 tests/                       # Pruebas de integración
├── ▶️ run_demo.ps1                  # Inicio rápido PowerShell
├── ▶️ run_demo.bat                  # Inicio rápido Windows (1 clic)
└── pyproject.toml
```

---

## 🚀 Inicio Rápido (Local)

### ▶️ Opción 1 — 1 Clic (Windows)

```
run_demo.bat
```
*O en PowerShell:*
```powershell
.\run_demo.ps1
```

Abre: **`http://localhost:5173`**

---

### 🔧 Opción 2 — Manual

**Backend (FastAPI)**
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (React + Vite)**
```powershell
cd frontend
npm install
npm run dev
```

---

### 🔑 Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/
AZURE_OPENAI_API_KEY=tu_clave_aqui
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

---

## ☁️ Despliegue en Render

> **No se necesita Docker.** Render soporta Python y Static Sites de forma nativa.

### 1️⃣ Backend — Web Service

| Campo | Valor |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |

Agrega las 4 variables de entorno de Azure OpenAI en el panel de Render.

### 2️⃣ Frontend — Static Site

| Campo | Valor |
|---|---|
| Root Directory | `frontend` |
| Build Command | `npm install && npm run build` |
| Publish Directory | `dist` |

---

## 🧪 Pruebas

```powershell
.\.venv\Scripts\python.exe tests/test_backend_api.py
```

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| 🧠 IA | Azure OpenAI GPT-4.1-mini |
| 🐍 Backend | FastAPI + Uvicorn + PyMuPDF |
| ⚛️ Frontend | React 19 + TypeScript + Vite |
| 📄 PDF Engine | PyMuPDF (fitz) + OpenCV |
| 🎨 UI Icons | Lucide React |

---

## 📄 Licencia

Distribuido bajo la [Licencia MIT](LICENSE).

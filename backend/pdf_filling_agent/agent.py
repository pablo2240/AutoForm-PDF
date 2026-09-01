"""
AI Agent for PDF filling using OpenRouter API.
Supports:
- Interactive AcroForm PDFs (widgets)
- Flat/non-interactive PDFs with text layer (visual overlay via text blocks)
- Scanned/image PDFs (vision mode via multimodal LLM)
- Static form maps for deterministic filling of known company forms
"""

import os
import json
import re
import base64
import unicodedata
import fitz
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from pydantic import BaseModel, Field

PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(PROJECT_ROOT_DIR, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=True)

from .knowledge_base import KnowledgeBase
from .pdf_processor import PDFProcessor
from .visual_processor import VisualPDFProcessor, VisualPlacement, PageImage
from .field_dictionary import FIELD_SYNONYMS, IGNORE_RULES, get_dictionary_context


class FieldMapping(BaseModel):
    """Model for field mapping decisions."""
    pdf_field_name: str = Field(description="The actual PDF field name")
    user_value: str = Field(description="The value to assign to this field")
    confidence: float = Field(default=1.0, description="Confidence score 0.0-1.0")
    reasoning: str = Field(default="", description="Why this field should get this value")


class VisualPlacementsResult(BaseModel):
    """Model for structured visual placement generation."""
    placements: List[VisualPlacement] = Field(default_factory=list)
    explanation: Optional[str] = Field(default="")


class StaticFormField(BaseModel):
    """Model for a field in a static form map."""
    id: str
    label: str
    page: int
    rect: List[float]
    type: str  # text, number, date, checkbox, radio
    maps_to: Optional[str] = None
    format: Optional[str] = None
    options: Optional[List[str]] = None
    value_when_true: Optional[str] = None
    default: Optional[bool] = None


class StaticFormMap(BaseModel):
    """Model for a static form map."""
    form_name: str
    pdf_name: str
    aliases: List[str] = Field(default_factory=list)
    pages: int
    description: Optional[str] = ""
    fields: List[StaticFormField] = Field(default_factory=list)


class PDFAgent:
    """AI agent that generates and executes PDF filling for multiple form types."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None,
                 knowledge_base: Optional[KnowledgeBase] = None,
                 company_profile_path: Optional[str] = None,
                 forms_dir: Optional[str] = None):
        
        # Always reload environment from .env with explicit path
        if os.path.exists(ENV_PATH):
            load_dotenv(dotenv_path=ENV_PATH, override=True)

        # Determine provider: Azure OpenAI, OpenAI Standard, or OpenRouter
        azure_key = (
            api_key if (api_key and os.getenv("LLM_PROVIDER") == "azure")
            else os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        )
        azure_endpoint = (
            base_url if (base_url and "azure" in (base_url or "").lower())
            else os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT") or os.getenv("AZURE_OPENAI_BASE_URL") or os.getenv("AZURE_BASE_URL")
        )
        azure_deployment = (
            model or 
            os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or 
            os.getenv("AZURE_OPENAI_DEPLOYMENT") or 
            os.getenv("AZURE_OPENAI_MODEL") or 
            os.getenv("AZURE_MODEL") or 
            "gpt-4.1-mini"
        )
        azure_api_version = (
            os.getenv("AZURE_OPENAI_API_VERSION") or 
            os.getenv("AZURE_API_VERSION") or 
            "2024-12-01-preview"
        )

        is_azure = bool(
            azure_key or 
            os.getenv("LLM_PROVIDER") == "azure" or 
            (azure_endpoint and not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"))
        )

        if is_azure and (azure_key or azure_endpoint):
            self.provider = "azure"
            self.api_key = azure_key or api_key
            self.azure_endpoint = (azure_endpoint or "").strip()
            self.api_version = azure_api_version
            self.model = azure_deployment

            if not self.api_key:
                raise ValueError("Azure OpenAI API key not found. Please set AZURE_OPENAI_API_KEY in your .env file.")
            if not self.azure_endpoint:
                raise ValueError(
                    "Azure OpenAI Endpoint no configurado. Por favor agrega AZURE_OPENAI_ENDPOINT en tu archivo .env "
                    "(Ejemplo: AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/)"
                )

            self.client = AzureOpenAI(
                azure_endpoint=self.azure_endpoint,
                api_key=self.api_key,
                api_version=self.api_version
            )
            print(f"[INFO] Initialized Azure OpenAI Client (Endpoint: {self.azure_endpoint}, Deployment: {self.model}, API Version: {self.api_version})")

        elif os.getenv("OPENAI_API_KEY"):
            self.provider = "openai"
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            print(f"[INFO] Initialized Standard OpenAI Client (Model: {self.model})")

        elif os.getenv("OPENROUTER_API_KEY") or api_key:
            self.provider = "openrouter"
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-5.6-luna")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            print(f"[INFO] Initialized OpenRouter Client (Model: {self.model})")

        else:
            raise ValueError(
                "No LLM API keys found. Please configure AZURE_OPENAI_API_KEY & AZURE_OPENAI_ENDPOINT, "
                "or OPENAI_API_KEY, or OPENROUTER_API_KEY in your environment or .env file."
            )

        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.pdf_processor = PDFProcessor()
        self.visual_processor = VisualPDFProcessor()

        # Load company profile
        self.company_profile = self._load_company_profile(company_profile_path)

        # Load static form maps
        self.forms_dir = forms_dir or os.path.join(os.path.dirname(__file__), "..", "forms")
        self.form_maps: Dict[str, StaticFormMap] = {}
        self._load_form_maps()

    def _load_company_profile(self, profile_path: Optional[str]) -> Dict[str, Any]:
        """Load company profile from JSON file."""
        if profile_path is None:
            # Default paths
            base_dir = os.path.dirname(os.path.dirname(__file__))
            profile_path = os.path.join(base_dir, "data", "company_data.json")
            if not os.path.exists(profile_path):
                profile_path = os.path.join(base_dir, "company_profile.json")

        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8-sig') as f:
                profile = json.load(f)
            company_name = profile.get('razon_social') or profile.get('company_name', 'Unknown')
            print(f"[INFO] Loaded company profile: {company_name}")
            return profile
        else:
            print(f"[WARN] Company profile not found at {profile_path}")
            return {}

    def _call_llm(self, messages: List[Dict[str, Any]], token_limit: int = 2000) -> str:
        """Call LLM with auto-compatibility for both max_completion_tokens (GPT-5.x/o-series) and max_tokens."""
        # 1. Try max_completion_tokens (standard for GPT-5.6 / modern OpenAI models)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=token_limit
            )
            return response.choices[0].message.content.strip()
        except Exception as e1:
            err_msg = str(e1)
            # If model does not support max_completion_tokens, fallback to max_tokens + temperature
            if "max_completion_tokens" in err_msg or "unsupported_parameter" in err_msg.lower():
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=token_limit,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()
            raise e1

    def _load_form_maps(self):
        """Load all static form maps from the forms directory."""
        if not os.path.exists(self.forms_dir):
            print(f"[INFO] Forms directory not found: {self.forms_dir}")
            return

        for filename in os.listdir(self.forms_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.forms_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    form_map = StaticFormMap(**data)
                    # Index by pdf_name (without extension) and form_name
                    key = form_map.pdf_name.replace('.pdf', '').lower().replace(' ', '_')
                    self.form_maps[key] = form_map
                    print(f"[INFO] Loaded form map: {form_map.form_name} (key: {key})")
                except Exception as e:
                    print(f"[WARN] Failed to load form map {filename}: {e}")

    def _find_form_map(self, pdf_path: str) -> Optional[StaticFormMap]:
        """Find a matching static form map for the given PDF."""
        pdf_name = os.path.basename(pdf_path).replace('.pdf', '').lower().replace(' ', '_')
        # Try exact match first
        if pdf_name in self.form_maps:
            return self.form_maps[pdf_name]
        # Try partial match on keys
        for key, form_map in self.form_maps.items():
            if key in pdf_name or pdf_name in key:
                return form_map
        # Try matching against aliases
        for form_map in self.form_maps.values():
            for alias in form_map.aliases:
                alias_norm = alias.lower().replace(' ', '_')
                if alias_norm in pdf_name or pdf_name in alias_norm:
                    return form_map
            # Also match by form_name keywords
            form_keywords = form_map.form_name.lower().replace(' ', '_').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            if any(kw in pdf_name for kw in form_keywords.split('_') if len(kw) > 3):
                return form_map
        return None

    def _resolve_value(self, maps_to: Optional[str], profile: Dict[str, Any]) -> Optional[str]:
        """Resolve a value from the company profile using dot notation path."""
        if not maps_to or not profile:
            return None

        # Special cases
        if maps_to == "current_date":
            return datetime.now().strftime("%d/%m/%Y")
        if maps_to == "current_date_ddmmyyyy":
            return datetime.now().strftime("%d/%m/%Y")
        if maps_to == "current_date_mmddyyyy":
            return datetime.now().strftime("%m/%d/%Y")

        # Navigate nested dict with dot notation
        keys = maps_to.split('.')
        value = profile
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        if value is None:
            return None

        # Format based on type
        if isinstance(value, bool):
            return "X" if value else ""
        if isinstance(value, (int, float)):
            # Format numbers with thousand separators for Colombian format
            return f"{value:,}".replace(",", ".")
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)

        return str(value)

    def _get_raw_profile_value(self, maps_to: str, profile: Dict[str, Any]) -> Any:
        """Get raw value from profile without formatting (for checkbox boolean logic)."""
        if not maps_to or not profile:
            return None
        keys = maps_to.split('.')
        value = profile
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def _fill_with_static_map(self, pdf_path: str, form_map: StaticFormMap, user_instructions: str) -> str:
        """Fill PDF using a static form map (deterministic coordinates)."""
        print(f"[INFO] Using static form map: {form_map.form_name}")

        # Build field values from company profile + user instructions
        field_values: Dict[str, Any] = {}

        # First, extract any explicit values from user instructions
        explicit_values = self._parse_explicit_values(user_instructions)

        for field in form_map.fields:
            value = None

            # 1. Check explicit user instruction
            if field.id in explicit_values:
                value = explicit_values[field.id]
            # 2. Check if maps_to company profile
            elif field.maps_to:
                value = self._resolve_value(field.maps_to, self.company_profile)
            # 3. Check checkbox defaults
            elif field.type == "checkbox" and field.default is not None:
                value = field.value_when_true if field.default else ""

            # Store the raw value (could be bool, str, int, etc.)
            if value is not None and value != "":
                field_values[field.id] = value
                print(f"  [MAP] {field.id} ({field.label}) = {value}")

        if not field_values:
            print("[WARN] No field values resolved from static map")
            return self._fill_visual(pdf_path, user_instructions)

        # Convert to VisualPlacement objects
        placements = []
        for field in form_map.fields:
            if field.id in field_values:
                val = field_values[field.id]
                if field.type == "checkbox":
                    # Determine if checkbox should be checked
                    checked = False
                    
                    # Special handling: if field maps_to a boolean in profile, 
                    # check SI/YES when true, NO when false
                    raw_bool = None
                    if field.maps_to:
                        raw_bool = self._get_raw_profile_value(field.maps_to, self.company_profile)
                    
                    if isinstance(raw_bool, bool):
                        # Boolean profile field: check based on value_when_true
                        if raw_bool and field.value_when_true and field.value_when_true.upper() in ["SI", "YES", "X", "TRUE"]:
                            checked = True
                        elif not raw_bool and field.value_when_true and field.value_when_true.upper() in ["NO", "FALSE"]:
                            checked = True
                    elif field.value_when_true is not None:
                        # Compare resolved value with expected value
                        checked = str(val).strip().upper() == field.value_when_true.strip().upper()
                    elif isinstance(val, bool):
                        checked = val
                    elif isinstance(val, str):
                        checked = val.upper() in ["X", "SI", "TRUE", "YES", "1"]
                    
                    if checked:
                        placements.append(VisualPlacement(
                            page=field.page,
                            rect=field.rect,
                            text="X",
                            font_size=10,
                            align=1,
                            field_description=field.label
                        ))
                else:
                    placements.append(VisualPlacement(
                        page=field.page,
                        rect=field.rect,
                        text=str(val),
                        font_size=8.5,
                        align=0,
                        field_description=field.label
                    ))

        print(f"[INFO] Applying {len(placements)} placements from static map")
        return self.visual_processor.apply_visual_placements(pdf_path, placements)

    def _parse_explicit_values(self, instructions: str) -> Dict[str, str]:
        """Parse explicit field=value pairs from user instructions."""
        values = {}
        # Pattern: "field_id: value" or "field_id = value"
        patterns = [
            r'(\w+)\s*[:=]\s*([^\n,]+)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, instructions):
                key = match.group(1).strip().lower()
                val = match.group(2).strip()
                values[key] = val
        return values

    def fill_pdf(self,
                 pdf_path: str,
                 user_instructions: str,
                 output_dir: Optional[str] = None,
                 mode: str = "auto") -> str:
        """
        Fill a PDF based on user instructions with hybrid mode support.

        Args:
            pdf_path: Path to the input PDF file
            user_instructions: Natural language instructions for filling the PDF
            output_dir: Output directory (optional)
            mode: 'auto', 'widget', 'visual', 'vision', 'static'
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if output_dir:
            self.pdf_processor.output_dir = output_dir
            self.visual_processor.output_dir = output_dir

        # Check for static form map first (highest priority for known forms)
        form_map = self._find_form_map(pdf_path)
        if form_map and mode in ["auto", "static"]:
            print(f"[INFO] Static form map found. Using deterministic filling.")
            return self._fill_with_static_map(pdf_path, form_map, user_instructions)

        # Inspect PDF widgets
        fields = self.pdf_processor.get_pdf_fields(pdf_path)
        has_widgets = len(fields) > 0

        if mode == "widget" or (mode == "auto" and has_widgets):
            print(f"[INFO] Interactive form detected ({len(fields)} fields). Using AcroForm mode.")
            return self._fill_acroform(pdf_path, fields, user_instructions)

        # For flat PDFs, check if pages have text layer
        layouts = self.visual_processor.extract_page_layouts(pdf_path)
        pages_with_text = sum(1 for l in layouts if l["blocks"])
        total_pages = len(layouts)

        if mode == "vision" or (mode == "auto" and pages_with_text == 0):
            print(f"[INFO] Scanned/image PDF detected (no text layer). Using Vision mode.")
            return self._fill_vision(pdf_path, user_instructions)
        else:
            print(f"[INFO] Flat PDF with text layer ({pages_with_text}/{total_pages} pages). Using Visual Overlay mode.")
            return self._fill_visual(pdf_path, user_instructions)

    def _extract_rich_acro_widgets(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract all widgets with their precise visual labels from the PDF pages."""
        rich_widgets = []
        for pno in range(len(doc)):
            page = doc[pno]
            widgets = list(page.widgets())
            if not widgets:
                continue
            words = page.get_text("words")
            blocks = page.get_text("blocks")
            
            for w in widgets:
                wr = w.rect
                attr_label = getattr(w, 'field_label', '') or ''
                
                # Words immediately above the widget strictly overlapping its column width
                above_words = [nw[4] for nw in sorted([wd for wd in words if 0 <= wr.y0 - wd[3] < 14 and (wd[2] >= wr.x0 - 4 and wd[0] <= wr.x1 + 4)], key=lambda x: (x[1], x[0]))]
                # Words to the left on the same horizontal baseline band
                left_words = [nw[4] for nw in sorted([wd for wd in words if abs(wd[1] - wr.y0) < 10 and wd[2] <= wr.x0 + 2 and (wr.x0 - wd[2]) < 130], key=lambda x: (x[1], x[0]))]
                
                left_str = " ".join(left_words)
                above_str = " ".join(above_words)
                
                # Closest section header
                section_header = ""
                for b in blocks:
                    if b[4].strip() and b[3] <= wr.y0 and (wr.y0 - b[3]) < 70:
                        section_header = b[4].strip().replace("\n", " ")
                
                label = attr_label or left_str or above_str or w.field_name
                rich_widgets.append({
                    "widget": w,
                    "field_name": w.field_name,
                    "field_type": w.field_type_string,
                    "rect": wr,
                    "attr_label": attr_label,
                    "left_text": left_str,
                    "above_text": above_str,
                    "label": label,
                    "section": section_header,
                    "page": pno
                })
        return rich_widgets

    def _normalize_label(self, text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
        return re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower().strip()

    def _deterministic_acroform_match(self, rich_widgets: List[Dict[str, Any]]) -> Dict[str, str]:
        """Deterministic mapping based on company profile and synonyms dictionary."""
        profile = self.company_profile
        if not profile:
            return {}

        nit_val = str(profile.get("nit", "")).strip()
        nit_base = nit_val[:-1] if len(nit_val) == 10 and nit_val.isdigit() else nit_val
        nit_dv = nit_val[-1] if len(nit_val) == 10 and nit_val.isdigit() else "2"
        
        rep_full = str(profile.get("representante_legal", "Guillermo Humberto Cañón Sarria")).strip()
        rep_nombre = str(profile.get("representante_nombre", "Guillermo Humberto")).strip()
        rep_apellido = str(profile.get("representante_apellido", "Cañón Sarria")).strip()
        rep_apellidos_split = rep_apellido.split()
        primer_apellido = rep_apellidos_split[0] if len(rep_apellidos_split) > 0 else rep_apellido
        segundo_apellido = rep_apellidos_split[1] if len(rep_apellidos_split) > 1 else ""

        mappings = {}
        assigned_categories = set()
        
        for item in rich_widgets:
            fn = item["field_name"]
            ftype = item["field_type"]
            pno = item["page"]

            # 1. SKIP RadioButtons / CheckBoxes in deterministic text matching
            if ftype in ["RadioButton", "CheckBox", "Button"]:
                continue

            # 2. SKIP secondary table rows (Row index >= 1) - ONLY fill Row 1 [0]
            row_match = re.search(r'(?:Fila|Row|Item|Tabla\d*)\[(\d+)\]', fn, re.IGNORECASE)
            if row_match and int(row_match.group(1)) > 0:
                continue

            full_context = f"{item['attr_label']} {item['left_text']} {item['above_text']} {item['section']} {fn}".strip()
            norm = self._normalize_label(full_context)
            norm_left = self._normalize_label(item["left_text"])
            norm_above = self._normalize_label(item["above_text"])
            
            # Exclusion rules: ignore foreign, counterparty, internal use, sucursal, PEP, or 'OTRA' / 'OTRO'
            if any(ign in norm for ign in ["extranjero", "foreign", "uso exclusivo", "espacio reservado", "aprobacion interna", "sucursal", "nacimiento", "pep", "politicamente expuesta", "expuesta politicamente", "persona expuesta"]):
                continue
            if re.search(r'\b(otra|otro|otras|otros)\b', norm) and not any(k in norm for k in ["razon social", "representante legal"]):
                continue

            val_to_set = None
            
            # 1. Razón Social (Assigned once to primary company name field)
            if any(k in norm_left or k in norm_above for k in ["razon social", "nombre empresa", "nombre o razon social", "denominacion social"]):
                if "representante" not in norm and "intermediario" not in norm and "p_razon_social" not in assigned_categories:
                    val_to_set = profile.get("razon_social")
                    assigned_categories.add("p_razon_social")
            
            # 2. DV
            elif re.search(r'\b(dv|digito verificacion|digito de verificacion)\b', norm_left) or re.search(r'\b(dv|digito verificacion|digito de verificacion)\b', norm_above):
                val_to_set = nit_dv
            
            # 3. NIT / RUT
            elif (re.search(r'\b(nit|rut|identificacion tributaria)\b', norm_left) or re.search(r'\b(nit|rut|identificacion tributaria)\b', norm_above)) and "dv" not in norm_left and "dv" not in norm_above:
                if "tipo" not in norm and "p_nit" not in assigned_categories:
                    val_to_set = nit_base or nit_val
                    assigned_categories.add("p_nit")
                elif ftype == "ComboBox":
                    val_to_set = "NIT"
            
            # 4. Apellidos y Nombres / Nombres y Apellidos en una sola casilla
            elif any(k in norm_left or k in norm_above for k in ["apellidos y nombres", "nombres y apellidos", "nombre y apellidos", "apellidos y nombre"]):
                val_to_set = rep_full

            # 5. Primer Apellido (Representante Legal)
            elif "primer apellido" in norm_left or "primer apellido" in norm_above:
                val_to_set = primer_apellido
                
            # 6. Segundo Apellido (Representante Legal)
            elif "segundo apellido" in norm_left or "segundo apellido" in norm_above:
                val_to_set = segundo_apellido
                
            # 7. Nombres (Representante Legal)
            elif "nombres" in norm_left or "nombres" in norm_above:
                val_to_set = rep_nombre
                
            # 8. Representante Legal Full Name
            elif "representante legal" in norm and ("nombre" in norm or "apellidos" in norm or "representante" in norm) and "p_rep_full" not in assigned_categories:
                val_to_set = rep_full
                assigned_categories.add("p_rep_full")
            
            # 9. Cédula / Número ID
            elif (re.search(r'\b(numero id|nro id|no id|num id|numero de id|cedula|numero de documento|no documento)\b', norm_left) or re.search(r'\b(numero id|nro id|num id|numero de id|cedula)\b', norm_above)) and "tipo" not in norm_left and "tipo" not in norm_above:
                val_to_set = profile.get("numero_cedula")

            # 10. Document Type
            elif re.search(r'\b(tipo de documento|tipo doc|tipo id)\b', norm_left) or re.search(r'\b(tipo de documento|tipo doc|tipo id)\b', norm_above):
                if "empresa" in norm or "juridica" in norm:
                    val_to_set = "NIT"
                else:
                    val_to_set = profile.get("tipo_documento", "C.C.")
            
            # 11. Lugar Expedición ('de' / 'De' tras cédula / expedida en)
            elif (
                re.search(r'\b(lugar de expedicion|lugar expedicion|expedida en|ciudad de expedicion)\b', norm_left) or 
                re.search(r'\b(lugar de expedicion|lugar expedicion)\b', norm_above) or
                norm_left in ["de", "de:", "de :"] or norm_above in ["de", "de:", "de :"] or
                norm_left.endswith(" de") or norm_above.endswith(" de")
            ):
                val_to_set = profile.get("lugar_expedicion_rep", "Envigado")
            
            # 12. Nacionalidad (Hace referencia al país: Colombiana)
            elif re.search(r'\b(nacionalidad|nacionalidad 1|nacionalidad 2|pais de origen)\b', norm_left) or re.search(r'\b(nacionalidad|nacionalidad 1|nacionalidad 2|pais de origen)\b', norm_above):
                val_to_set = profile.get("nacionalidad", "Colombiana")

            # 13. Contacto Principal / Persona de Contacto
            elif "contacto" in norm:
                if any(k in norm for k in ["nombre", "persona de contacto", "contacto principal"]):
                    val_to_set = profile.get("contacto_principal_nombre", rep_full)
                elif "cargo" in norm:
                    val_to_set = profile.get("contacto_cargo", "Representante Legal")
                elif any(k in norm for k in ["celular", "movil"]):
                    val_to_set = profile.get("celular_rep", "3104120217")
                elif any(k in norm for k in ["telefono", "tel"]):
                    val_to_set = profile.get("telefono", "2656868")
                elif any(k in norm for k in ["correo", "email", "e mail"]):
                    val_to_set = profile.get("correo_rep", "guillermo.canon@iaclatam.com")

            # 14. Dirección Domicilio Principal
            elif (re.search(r'\b(direccion|domicilio|oficina principal direccion|direccion domicilio)\b', norm_left) or re.search(r'\b(direccion|domicilio)\b', norm_above)) and "p_dir" not in assigned_categories:
                val_to_set = profile.get("direccion_principal")
                assigned_categories.add("p_dir")
            
            # 15. Ciudad
            elif (re.search(r'\b(ciudad|municipio)\b', norm_left) or re.search(r'\b(ciudad|municipio)\b', norm_above)) and "sucursal" not in norm and "expedicion" not in norm and "nacimiento" not in norm and "p_ciudad" not in assigned_categories:
                val_to_set = profile.get("ciudad", "Medellin")
                assigned_categories.add("p_ciudad")
            
            # 16. Departamento
            elif (re.search(r'\b(departamento|dpto)\b', norm_left) or re.search(r'\b(departamento|dpto)\b', norm_above)) and "p_dpto" not in assigned_categories:
                val_to_set = profile.get("departamento", "Antioquia")
                assigned_categories.add("p_dpto")
            
            # 17. País
            elif (re.search(r'\b(pais|pais de domicilio)\b', norm_left) or re.search(r'\b(pais)\b', norm_above)) and "p_pais" not in assigned_categories:
                val_to_set = profile.get("pais", "Colombia")
                assigned_categories.add("p_pais")
            
            # 18. Teléfono / Celular
            elif (re.search(r'\b(telefono celular|celular)\b', norm_left) or re.search(r'\b(telefono celular|celular)\b', norm_above)) and "p_cel" not in assigned_categories:
                val_to_set = profile.get("celular_rep", profile.get("telefono"))
                assigned_categories.add("p_cel")
            elif (re.search(r'\b(telefono|telefono fijo|tel)\b', norm_left) or re.search(r'\b(telefono|tel)\b', norm_above)) and "p_tel" not in assigned_categories:
                val_to_set = profile.get("telefono")
                assigned_categories.add("p_tel")
            
            # 19. Email / Correo
            elif (re.search(r'\b(correo|e mail|email|correo electronico)\b', norm_left) or re.search(r'\b(correo|e mail|email)\b', norm_above)) and "p_email" not in assigned_categories:
                val_to_set = profile.get("correo_rep")
                assigned_categories.add("p_email")
            
            # 20. Web
            elif re.search(r'\b(pagina web|sitio web|web)\b', norm_left) or re.search(r'\b(pagina web|sitio web|web)\b', norm_above):
                val_to_set = profile.get("pagina_web")
            
            # 21. Banco / Cuenta
            elif re.search(r'\b(banco|entidad bancaria|entidad financiera)\b', norm_left) or re.search(r'\b(banco|entidad bancaria)\b', norm_above):
                val_to_set = profile.get("entidad_bancaria")
            elif (re.search(r'\b(numero de cuenta|no cuenta|cuenta no)\b', norm_left) or re.search(r'\b(numero de cuenta|no cuenta)\b', norm_above)) and "tipo" not in norm:
                val_to_set = profile.get("numero_cuenta")
            elif re.search(r'\b(tipo de cuenta|tipo cuenta)\b', norm_left) or re.search(r'\b(tipo de cuenta|tipo cuenta)\b', norm_above):
                val_to_set = profile.get("tipo_cuenta")
            
            # 22. Tipo de empresa
            elif re.search(r'\b(tipo de empresa)\b', norm_left) or re.search(r'\b(tipo de empresa)\b', norm_above):
                val_to_set = "PRIVADA"

            if val_to_set:
                mappings[fn] = str(val_to_set)

        return mappings

    def _fill_acroform(self, pdf_path: str, fields: Dict[str, str], user_instructions: str) -> str:
        """Fill an interactive PDF form with AcroForm widgets using rich label extraction + LLM + dictionary hybrid."""
        doc = fitz.open(pdf_path)
        rich_widgets = self._extract_rich_acro_widgets(doc)
        
        # 1. Deterministic high-confidence matches from dictionary
        deterministic_matches = self._deterministic_acroform_match(rich_widgets)
        print(f"[INFO] Deterministic AcroForm matches found: {len(deterministic_matches)}")

        # 2. LLM enriched page-by-page mapping
        llm_matches: Dict[str, str] = {}
        
        # Group rich widgets by page
        pages_dict: Dict[int, List[Dict[str, Any]]] = {}
        for rw in rich_widgets:
            pages_dict.setdefault(rw["page"], []).append(rw)

        system_instructions = self.knowledge_base.get_system_instructions()
        chunk_size = 35

        for pno, p_widgets in pages_dict.items():
            for i in range(0, len(p_widgets), chunk_size):
                chunk = p_widgets[i:i + chunk_size]
                fields_text = "\n".join([f"- ID: {f['field_name']} | Label: '{f['label']}' | Type: {f['field_type']}" for f in chunk])
                
                prompt = f"""
Given the following interactive PDF form fields on Page {pno + 1}:
{fields_text}

Company Profile Data:
{json.dumps(self.company_profile, ensure_ascii=False, indent=2)}

User Instructions:
{user_instructions}

Assign the appropriate company profile values to matching fields.
CRITICAL RULES:
1. ONLY map fields that correspond to the company ({self.company_profile.get('razon_social', 'la empresa')}) or its main legal representative ({self.company_profile.get('representante_legal', 'el representante legal')}).
2. PERSONAS EXPUESTAS POLÍTICAMENTE (PEP): Ignora y NO respondas ni marques casillas en secciones como '6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)', 'PEP', 'PEPs' o preguntas sobre PEP; déjalas totalmente vacías.
3. APELLIDOS Y NOMBRES COMPLETOS: Cuando un campo pida 'Apellidos y Nombres' o 'Nombres y Apellidos' en una sola casilla o renglón, escribe el nombre completo: '{self.company_profile.get('representante_legal', 'Guillermo Humberto Cañón Sarria')}'.
4. NÚMERO ID Y LUGAR DE EXPEDICIÓN ('DE'): Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID', 'CÉDULA', llénalo con '{self.company_profile.get('numero_cedula', '98555384')}'. Si inmediatamente después hay una casilla que dice 'de' o 'De' (ej. No. ID: _____ de _____), pon el lugar de expedición: '{self.company_profile.get('lugar_expedicion_rep', 'Envigado')}'.
5. NACIONALIDAD: Cuando un campo pida 'Nacionalidad', hace referencia al país y debe escribirse '{self.company_profile.get('nacionalidad', 'Colombiana')}'.
6. CONTACTO PRINCIPAL: Cuando una sección solicite datos de 'Contacto Principal' o 'Persona de Contacto', llena los campos con los datos del contacto/representante (Nombre: {self.company_profile.get('representante_legal')}, Teléfono/Celular: {self.company_profile.get('celular_rep')}, Correo: {self.company_profile.get('correo_rep')}, Cargo: Representante Legal).
7. TABLAS CON MÚLTIPLES FILAS (SOLO PRIMERA FILA): En tablas o subformularios repetitivos (ej. Fila1[0], Fila1[1], Fila1[2] o Subform[29], Subform[30], Subform[31]), llena ÚNICAMENTE la primera fila (índice 0 / Fila 1). NUNCA repitas los datos en las filas 2, 3, 4 ni siguientes.
8. NO DUPLICACIÓN: No coloques el mismo dato repetido en campos contiguos con finalidades distintas (ej. Sucursal no es Ciudad; Segundo Apellido no es Nombres).
9. DO NOT fill sections for Foreigners ('Extranjeros'), Counterparties, or Internal entity use ('Uso exclusivo de la entidad').
10. OTRA / OTRO: If a field or label mentions 'OTRA', 'OTRO', 'OTRAS', or 'OTROS', DO NOT put data (leave it completely empty).
11. OPCIONES MÚLTIPLES: If a field or group represents multiple choice options ('opciones múltiples') or generic option lists, IGNORE and write nothing.
12. For CheckBoxes, use '1', 'Yes', or 'X' when True, or 'Off' when False.
13. Return ONLY a valid JSON object mapping exact field IDs to string values.
"""
                try:
                    raw_text = self._call_llm([
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": prompt}
                    ], token_limit=2000)
                    
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        for k, v in parsed.items():
                            if v is not None and str(v).strip():
                                llm_matches[k] = str(v)
                except Exception as ex:
                    print(f"[WARN] AcroForm LLM chunk error on page {pno}: {ex}")

        # Filter out secondary table rows from LLM matches to strictly avoid repetition
        filtered_llm = {}
        for k, v in llm_matches.items():
            row_match = re.search(r'(?:Fila|Row|Item|Tabla\d*)\[(\d+)\]', k, re.IGNORECASE)
            if row_match and int(row_match.group(1)) > 0:
                continue
            filtered_llm[k] = v

        # Combine matches: LLM adds complementary context, deterministic matches take authoritative baseline
        final_field_values = {**filtered_llm, **deterministic_matches}
        print(f"[INFO] Total AcroForm field values mapped: {len(final_field_values)}")
        print(f"[INFO] Mapped field values: {final_field_values}")

        doc.close()
        return self.pdf_processor.fill_pdf(pdf_path, final_field_values)

    def _fill_visual(self, pdf_path: str, user_instructions: str) -> str:
        """Fill a flat PDF by extracting layout and asking LLM to position text/marks page by page."""
        layouts = self.visual_processor.extract_page_layouts(pdf_path)
        all_placements: List[VisualPlacement] = []

        # System instructions already contain the full synonyms dictionary and exclusion rules via KnowledgeBase
        system_instructions = self.knowledge_base.get_system_instructions()

        # Build context with company profile
        profile_context = ""
        if self.company_profile:
            profile_context = f"\n\nCOMPANY PROFILE (use these values when instructions reference 'datos de la empresa'):\n"
            profile_context += json.dumps(self.company_profile, ensure_ascii=False, indent=2)

        # Extract keywords from user instructions to identify relevant pages
        keywords = [w.lower() for w in re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}', user_instructions)]

        for page_layout in layouts:
            page_no = page_layout["page"]
            w, h = page_layout["width"], page_layout["height"]

            page_text = " ".join([b['text'].lower() for b in page_layout["blocks"]])
            is_relevant = any(k in page_text for k in keywords) or page_no == 0

            if not is_relevant:
                print(f"[INFO] Skipping page {page_no} (no matching fields in instructions).")
                continue

            print(f"[INFO] Analyzing page {page_no} for visual field placements...")

            blocks_text = []
            for b in page_layout["blocks"]:
                txt = b['text'].replace('\n', ' ')
                if len(txt) > 60:
                    txt = txt[:60] + "..."
                bbox_str = f"[{b['bbox'][0]}, {b['bbox'][1]}, {b['bbox'][2]}, {b['bbox'][3]}]"
                blocks_text.append(f"  BBOX {bbox_str}: {txt}")

            layout_summary = f"PAGE {page_no} (Dimensions: {w} x {h}):\n" + "\n".join(blocks_text)

            prompt = f"""
Visual layout for PAGE {page_no} [x0, y0, x1, y1]:
{layout_summary}

User Instructions for filling the form:
{user_instructions}
{profile_context}

Analyze each field label on this page using the synonyms dictionary from your system instructions.
Strictly follow exclusion rules:
1. PERSONAS EXPUESTAS POLÍTICAMENTE (PEP): Ignora y NO respondas ni marques casillas en secciones como '6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)', 'PEP', 'PEPs' o preguntas sobre PEP; déjalas totalmente vacías.
2. APELLIDOS Y NOMBRES COMPLETOS: Cuando un campo pida 'Apellidos y Nombres' o 'Nombres y Apellidos' en una sola casilla o renglón, escribe el nombre completo: '{self.company_profile.get('representante_legal', 'Guillermo Humberto Cañón Sarria')}'.
3. NÚMERO ID Y LUGAR DE EXPEDICIÓN ('DE'): Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID', 'CÉDULA', llénalo con '{self.company_profile.get('numero_cedula', '98555384')}'. Si inmediatamente después hay una casilla que dice 'de' o 'De' (ej. No. ID: _____ de _____), pon el lugar de expedición: '{self.company_profile.get('lugar_expedicion_rep', 'Envigado')}'.
4. NACIONALIDAD: Cuando un campo pida 'Nacionalidad', hace referencia al país y debe escribirse '{self.company_profile.get('nacionalidad', 'Colombiana')}'.
5. CONTACTO PRINCIPAL: Cuando una sección solicite datos de 'Contacto Principal' o 'Persona de Contacto', llena los campos con los datos del contacto/representante (Nombre: {self.company_profile.get('representante_legal')}, Teléfono/Celular: {self.company_profile.get('celular_rep')}, Correo: {self.company_profile.get('correo_rep')}, Cargo: Representante Legal).
6. TABLAS CON MÚLTIPLES FILAS (SOLO PRIMERA FILA): En tablas o bloques con varias filas repetidas (ej. socios, accionistas, referencias, junta directiva), llena ÚNICAMENTE la primera fila (Fila 1). NUNCA repitas los datos en las filas 2, 3, 4 ni siguientes.
7. NO DUPLICACIÓN: No repitas el mismo dato en casillas o etiquetas contiguas de la misma página.
8. DO NOT fill sections for foreigners, counterparty, or exclusive use of the entity.
9. OTRA / OTRO: If a field or label mentions 'OTRA', 'OTRO', 'OTRAS', or 'OTROS', DO NOT put data (leave it completely empty).
10. OPCIONES MÚLTIPLES: If a field or group represents multiple choice options ('opciones múltiples') or generic option lists, IGNORE and write nothing.
For each field to fill on PAGE {page_no}, provide:
- "page": {page_no}
- "rect": [x0, y0, x1, y1] bounding box where text should fit
- "text": the text string to insert (or "X" for checkboxes)
- "font_size": 8.5
- "align": 0 (left) or 1 (center)

Return ONLY a valid JSON object with key "placements". If nothing needs to be filled, return {{"placements": []}}.
Example:
{{
  "placements": [
    {{
      "page": {page_no},
      "rect": [125.0, 195.0, 480.0, 209.4],
      "text": "Empresa Ejemplo S.A.S",
      "font_size": 8.5,
      "align": 0
    }}
  ]
}}
"""
            raw_text = None
            for token_limit in [4000, 2500]:
                try:
                    raw_text = self._call_llm([
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": prompt}
                    ], token_limit=token_limit)
                    break
                except Exception as err:
                    if "402" in str(err) and token_limit > 2500:
                        print(f"[WARN] Credit constraint on {self.model}, retrying with fewer tokens...")
                        continue
                    else:
                        print(f"[WARN] Error analyzing page {page_no} with {self.model}: {err}")
                        break

            if raw_text:
                data = self._safe_parse_json(raw_text)
                placements_data = data.get("placements", []) if isinstance(data, dict) else []
                for p in placements_data:
                    if isinstance(p, dict):
                        text_val = p.get("text") or p.get("value") or ""
                        rect_val = p.get("rect") or p.get("bbox") or p.get("rect_px")
                        if text_val and rect_val and isinstance(rect_val, list) and len(rect_val) == 4:
                            all_placements.append(VisualPlacement(
                                page=page_no,
                                rect=[float(c) for c in rect_val],
                                text=str(text_val),
                                font_size=float(p.get("font_size", 8.5)),
                                align=p.get("align", 0),
                                field_description=p.get("field_description") or p.get("label") or p.get("field", "")
                            ))

        print(f"[INFO] Total generated {len(all_placements)} visual placements across {len(layouts)} pages.")
        for p in all_placements:
            print(f"  - Page {p.page}: '{p.text}' at rect {p.rect}")

        return self.visual_processor.apply_visual_placements(pdf_path, all_placements)

    def _fill_vision(self, pdf_path: str, user_instructions: str, dpi: int = 150) -> str:
        """Fill a scanned/image PDF by rendering pages and using multimodal LLM."""
        print(f"[INFO] Vision mode: rendering pages at {dpi} DPI and analyzing with multimodal model")

        all_placements: List[VisualPlacement] = []

        system_instructions = self.knowledge_base.get_system_instructions()

        # Build company profile context
        profile_context = ""
        if self.company_profile:
            profile_context = f"\n\nCOMPANY PROFILE (use these values for 'datos de la empresa'):\n"
            profile_context += json.dumps(self.company_profile, ensure_ascii=False, indent=2)

        # Render all pages to images
        page_images = self.visual_processor.render_all_pages(pdf_path, dpi=dpi)

        for page_image in page_images:
            page_no = page_image.page
            print(f"[INFO] Vision analysis of page {page_no} ({page_image.width_px}x{page_image.height_px}px)...")

            # Prepare image for API
            image_url = f"data:image/png;base64,{page_image.image_base64}"

            prompt = f"""
Page {page_no} of a scanned form (image coordinates: origin top-left, {page_image.width_px}x{page_image.height_px}px).

User Instructions:
{user_instructions}
{profile_context}

Analyze the form image and identify where to place each requested piece of information.
Match labels using the synonyms dictionary and strictly adhere to the exclusion rules from your system instructions:
1. PERSONAS EXPUESTAS POLÍTICAMENTE (PEP): Ignora y NO respondas ni marques casillas en secciones como '6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)', 'PEP', 'PEPs' o preguntas sobre PEP; déjalas totalmente vacías.
2. APELLIDOS Y NOMBRES COMPLETOS: Cuando un campo pida 'Apellidos y Nombres' o 'Nombres y Apellidos' en una sola casilla o renglón, escribe el nombre completo: '{self.company_profile.get('representante_legal', 'Guillermo Humberto Cañón Sarria')}'.
3. NÚMERO ID Y LUGAR DE EXPEDICIÓN ('DE'): Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID', 'CÉDULA', llénalo con '{self.company_profile.get('numero_cedula', '98555384')}'. Si inmediatamente después hay una casilla que dice 'de' o 'De' (ej. No. ID: _____ de _____), pon el lugar de expedición: '{self.company_profile.get('lugar_expedicion_rep', 'Envigado')}'.
4. NACIONALIDAD: Cuando un campo pida 'Nacionalidad', hace referencia al país y debe escribirse '{self.company_profile.get('nacionalidad', 'Colombiana')}'.
5. CONTACTO PRINCIPAL: Cuando una sección solicite datos de 'Contacto Principal' o 'Persona de Contacto', llena los campos con los datos del contacto/representante (Nombre: {self.company_profile.get('representante_legal')}, Teléfono/Celular: {self.company_profile.get('celular_rep')}, Correo: {self.company_profile.get('correo_rep')}, Cargo: Representante Legal).
6. TABLAS CON MÚLTIPLES FILAS (SOLO PRIMERA FILA): En tablas o bloques con varias filas o líneas en blanco repetidas (ej. socios, accionistas, referencias, junta directiva), estampa ÚNICAMENTE en la primera fila (Fila 1). NUNCA repitas los datos en las filas 2, 3, 4 ni siguientes.
7. NO DUPLICACIÓN: No repitas el mismo dato en casillas contiguas de la misma página.
8. DO NOT fill sections for foreigners, counterparty, or exclusive use of the entity.
9. OTRA / OTRO: If a field or label mentions 'OTRA', 'OTRO', 'OTRAS', or 'OTROS', DO NOT put data (leave it completely empty).
10. OPCIONES MÚLTIPLES: If a field or group represents multiple choice options ('opciones múltiples') or generic option lists, IGNORE and write nothing.
For each field or checkbox to fill on THIS PAGE, provide:
- "page": {page_no}
- "rect_px": [x0, y0, x1, y1] in IMAGE PIXELS (top-left origin)
- "text": the text to insert (or "X" for checkboxes)
- "font_size": 8.5
- "align": 0 (left) or 1 (center)

Return ONLY a valid JSON object with key "placements". If nothing on this page, return {{"placements": []}}.
Example:
{{
  "placements": [
    {{
      "page": {page_no},
      "rect_px": [125, 195, 480, 220],
      "text": "Empresa Ejemplo S.A.S",
      "font_size": 8.5,
      "align": 0
    }}
  ]
}}
"""

            raw_text = None
            for token_limit in [4000, 2500]:
                try:
                    raw_text = self._call_llm([
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]}
                    ], token_limit=token_limit)
                    break
                except Exception as err:
                    if "402" in str(err) and token_limit > 2500:
                        print(f"[WARN] Credit constraint, retrying with fewer tokens...")
                        continue
                    else:
                        print(f"[WARN] Vision error on page {page_no}: {err}")
                        break

            if raw_text:
                data = self._safe_parse_json(raw_text)
                placements_data = data.get("placements", []) if isinstance(data, dict) else []
                for p in placements_data:
                    if isinstance(p, dict):
                        text_val = p.get("text") or p.get("value") or ""
                        rect_px_val = p.get("rect_px") or p.get("bbox") or p.get("rect")
                        if text_val and rect_px_val and isinstance(rect_px_val, list) and len(rect_px_val) == 4:
                            rect_pts = self.visual_processor.rect_pixels_to_points(page_image, [float(c) for c in rect_px_val])
                            all_placements.append(VisualPlacement(
                                page=page_no,
                                rect=rect_pts,
                                text=str(text_val),
                                font_size=float(p.get("font_size", 8.5)),
                                align=p.get("align", 0),
                                field_description=p.get("field_description") or p.get("label") or p.get("field", "")
                            ))

        print(f"[INFO] Vision mode: total {len(all_placements)} placements generated")
        for p in all_placements:
            print(f"  - Page {p.page}: '{p.text}' at rect {p.rect}")

        return self.visual_processor.apply_visual_placements(pdf_path, all_placements)

    def _safe_parse_json(self, raw_text: str) -> Dict[str, Any]:
        """Safely extract and parse JSON from LLM response text."""
        if not raw_text or not raw_text.strip():
            return {}

        # 1. Direct or stripped parsing
        clean = re.sub(r'^```(?:json)?\s*', '', raw_text.strip(), flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean.strip(), flags=re.MULTILINE).strip()

        try:
            return json.loads(clean)
        except Exception:
            pass

        # 2. Search for codeblock content
        block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
        if block_match:
            try:
                return json.loads(block_match.group(1))
            except Exception:
                pass

        # 3. Greedy search for outermost curly braces
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                last_obj_idx = candidate.rfind('}')
                if last_obj_idx != -1:
                    repaired = candidate[:last_obj_idx + 1] + "\n]}"
                    try:
                        return json.loads(repaired)
                    except Exception:
                        pass
        return {}


    def _heuristic_acroform_fill(self, pdf_path: str, user_instructions: str) -> str:
        """Fallback method for standard AcroForm fields using rich label extraction & dictionary matching."""
        doc = fitz.open(pdf_path)
        rich_widgets = self._extract_rich_acro_widgets(doc)
        field_values = self._deterministic_acroform_match(rich_widgets)
        doc.close()
        return self.pdf_processor.fill_pdf(pdf_path, field_values)
"""
Turns a PDF into reusable, LLM-free knowledge: labelled fields with position, section,
neighbours, example values, instructions and a master-model concept when one is known.

Reuses the existing analysis stack instead of re-implementing it:
- AcroForm widgets  -> form_analysis.extract_rich_acro_widgets
- Flat/visual forms -> cv_detector.CVFormDetector
- Concept (master model key) -> FillingValidator.score_field over FIELD_SYNONYMS
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import fitz

from ..cv_detector import CVFormDetector
from ..field_dictionary import FIELD_SYNONYMS
from ..form_analysis import extract_rich_acro_widgets
from ..validator import FillingValidator
from .embeddings import normalize_text

EXTRACTOR_VERSION = 1
CONCEPT_MIN_SCORE = 0.75  # stricter than the ADR-0003 0.60 floor: these become few-shot examples, precision matters

_PLACEHOLDER = re.compile(
    r"^(haga\s+clic\s+o\s+pulse\s+aqu[ií]\s+para\s+escribir|clic\s+para\s+escribir|"
    r"haga\s+clic\s+para\s+escribir|indique|escriba|ingrese|digite)\s+",
    re.IGNORECASE,
)
_GENERIC_NAME = re.compile(
    r"^(celda|cell|textfield|datetimefield|field|fila|row|tabla|table|texto|text|check\s*box|"
    r"casilla|independiente|listabotonesradio|campo)[\s_\d\[\]]*$",
    re.IGNORECASE,
)
_INSTRUCTION_HINTS = ("diligenci", "instruccion", "favor ", "adjunt", "debe ", "deberá", "obligatori", "anexar")


@dataclass
class ExtractedField:
    label: str
    section: str = ""
    page: int = 0
    rect: List[float] = field(default_factory=list)
    field_type: str = "Text"
    field_name: str = ""
    in_table: bool = False
    concept: Optional[str] = None
    concept_source: str = ""
    concept_score: float = 0.0
    example_value: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedForm:
    n_pages: int
    n_widgets: int
    is_acroform: bool
    fields: List[ExtractedField]
    sections: List[str]
    instructions: List[str]
    structure: List[Dict[str, Any]]


def clean_label(label: str, field_name: str = "") -> str:
    """Strip Word/Acrobat placeholder boilerplate; fall back to a descriptive field name; "" if neither is real text."""
    def usable(t: str) -> bool:
        return bool(re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{3,}", t)) and not _GENERIC_NAME.match(t)

    text = _PLACEHOLDER.sub("", re.sub(r"\s+", " ", (label or "")).strip()).strip(" :*_.")
    if not usable(text) or text == field_name:
        name = re.sub(r"\s+\d+$", "", _PLACEHOLDER.sub("", field_name.replace("_", " ")).strip())
        if usable(name):
            text = name
        elif not usable(text):
            return ""
    return text[:120]


_SYNONYM_TOKENS = {t for syns in FIELD_SYNONYMS.values() for s in syns for t in normalize_text(s).split() if len(t) > 1}
_concept_cache: Dict[str, tuple] = {}


def _concept_for(validator: FillingValidator, label: str, field_type: str = "Text") -> tuple:
    if field_type in ("CheckBox", "RadioButton"):  # option values ("Proveedor", "Renovación"), not master-model fields
        return None, 0.0
    key = normalize_text(label)
    if key not in _concept_cache:
        # score_field is O(synonyms x difflib): only call it when the label shares a token with the dictionary
        if _SYNONYM_TOKENS.isdisjoint(key.split()):
            _concept_cache[key] = (None, 0.0)
        else:
            cat, score, _ = validator.score_field(label, "", FIELD_SYNONYMS)
            _concept_cache[key] = (cat, score) if score >= CONCEPT_MIN_SCORE else (None, score)
    return _concept_cache[key]


def _link_neighbours(fields: List[ExtractedField]) -> None:
    """Reading-order neighbours inside the same page/section ("relaciones entre campos")."""
    ordered = sorted(fields, key=lambda f: (f.page, round(f.rect[1] / 8) if f.rect else 0, f.rect[0] if f.rect else 0))
    for i, f in enumerate(ordered):
        same = lambda o: o.page == f.page and o.section == f.section
        prev = ordered[i - 1].label if i and same(ordered[i - 1]) else ""
        nxt = ordered[i + 1].label if i + 1 < len(ordered) and same(ordered[i + 1]) else ""
        f.context["previous"], f.context["next"] = prev, nxt


def fields_from_rich_widgets(rich_widgets: List[Dict[str, Any]], validator: Optional[FillingValidator] = None) -> List[ExtractedField]:
    """Rich widgets (form_analysis) -> reference fields. Lets callers reuse an extraction they already did."""
    validator = validator or FillingValidator()
    out: List[ExtractedField] = []
    seen_checkbox_rows = set()
    for rw in rich_widgets:
        if rw["is_secondary_row"]:
            continue
        label = clean_label(rw["label"], rw["field_name"])
        if not label:
            continue
        r = rw["rect"]
        rect = [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]
        ftype = rw["field_type"]
        if ftype in ("CheckBox", "RadioButton"):  # one example per (label, section) is enough
            key = (normalize_text(label), rw["section"], rw["page"])
            if key in seen_checkbox_rows:
                continue
            seen_checkbox_rows.add(key)
        concept, score = _concept_for(validator, label, ftype)
        value = rw["current_value"] if rw["is_prefilled"] else ""
        out.append(ExtractedField(
            label=label, section=(rw["section"] or "")[:120], page=rw["page"], rect=rect,
            field_type=ftype, field_name=rw["field_name"],
            in_table=bool(re.search(r"(?:tabla|fila|cell|celda|grid|table|row)[\d_\[]", rw["field_name"], re.I)),
            concept=concept, concept_source="synonyms" if concept else "", concept_score=score if concept else 0.0,
            example_value=value[:80],
            context={"left_text": rw["left_text"][:80], "above_text": rw["above_text"][:80]},
        ))
    _link_neighbours(out)
    return out


def form_from_rich_widgets(rich_widgets: List[Dict[str, Any]], n_pages: int) -> ExtractedForm:
    fields = fields_from_rich_widgets(rich_widgets)
    sections = list(dict.fromkeys(f.section for f in fields if f.section))
    return ExtractedForm(n_pages, len(rich_widgets), True, fields, sections, [], [])


def _flat_fields(doc: fitz.Document, validator: FillingValidator) -> List[ExtractedField]:
    out: List[ExtractedField] = []
    seen = set()
    detector = CVFormDetector()
    for pno in range(len(doc)):
        page = doc[pno]
        try:
            matched = detector.map_labels_to_boxes(page, pno)["matched_fields"]
        except Exception as ex:
            print(f"[WARN] Flat-form detection failed on page {pno}: {ex}")
            matched = []
        for m in matched:
            label = clean_label(m["label"].replace("\n", " "))
            key = (normalize_text(label), pno, tuple(round(c) for c in m["target_rect"]))
            if not label or len(label) > 100 or key in seen:
                continue
            seen.add(key)
            concept, score = _concept_for(validator, label, "CheckBox" if m["type"] == "checkbox" else "Cell")
            out.append(ExtractedField(
                label=label, page=pno, rect=[round(c, 1) for c in m["target_rect"]],
                field_type="CheckBox" if m["type"] == "checkbox" else "Cell", concept=concept,
                concept_source="synonyms" if concept else "", concept_score=score if concept else 0.0,
            ))
    return out


def extract_reference(pdf_path: str) -> ExtractedForm:
    validator = FillingValidator()
    doc = fitz.open(pdf_path)
    try:
        n_widgets = sum(len(list(p.widgets())) for p in doc)
        is_acro = n_widgets > 0
        fields = fields_from_rich_widgets(extract_rich_acro_widgets(doc), validator) if is_acro else _flat_fields(doc, validator)

        if not is_acro:
            _link_neighbours(fields)

        sections: List[str] = []
        for f in fields:
            if f.section and f.section not in sections:
                sections.append(f.section)

        instructions: List[str] = []
        for page in doc:
            for b in page.get_text("blocks"):
                txt = re.sub(r"\s+", " ", b[4]).strip()
                if 60 <= len(txt) <= 400 and any(h in txt.lower() for h in _INSTRUCTION_HINTS) and txt not in instructions:
                    instructions.append(txt)
        structure = [
            {"page": i, "fields": sum(1 for f in fields if f.page == i),
             "sections": [s for s in dict.fromkeys(f.section for f in fields if f.page == i and f.section)]}
            for i in range(len(doc))
        ]
        return ExtractedForm(len(doc), n_widgets, is_acro, fields, sections, instructions[:15], structure)
    finally:
        doc.close()

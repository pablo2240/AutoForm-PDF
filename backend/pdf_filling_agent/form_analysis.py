"""
Structural analysis of PDF forms shared by the filling agent and the reference library.

Pure PyMuPDF (no LLM, no credentials): extracts every AcroForm widget with the visual
label, local/above text, closest section header and table-row metadata.
"""

import re
import unicodedata
from typing import Any, Dict, List

import fitz


def normalize_label(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower().strip()


def extract_rich_acro_widgets(doc: fitz.Document) -> List[Dict[str, Any]]:
    """Extract all widgets with their precise visual labels from the PDF pages."""
    rich_widgets = []
    for pno in range(len(doc)):
        page = doc[pno]
        widgets = list(page.widgets())
        if not widgets:
            continue
        words = page.get_text("words")
        blocks = page.get_text("blocks")

        # Identify section candidates on this page
        section_candidates = []
        for b in blocks:
            txt = b[4].strip().replace("\n", " ")
            norm_b = normalize_label(txt)
            if len(txt) > 3 and (
                re.match(r'^\d+(\.\d+)*\.?\s*[A-ZÁÉÍÓÚÑ]', txt) or
                any(norm_b.startswith(h) or h in norm_b for h in [
                    "anexo",
                    "anexos",
                    "apendice",
                    "firma del representante legal",
                    "habeas data",
                    "manifiesto de cumplimiento",
                    "datos de contacto",
                    "datos contacto",
                    "ariba",
                    "informacion general",
                    "datos representante legal",
                    "datos del representante legal",
                    "datos contacto comercial",
                    "declaracion de prevencion",
                    "anexos obligatorios",
                    "informacion referente a los accionistas",
                    "miembros de la junta directiva",
                    "informacion de revisores fiscales",
                    "referencias bancarias",
                    "datos de contacto del contratante",
                    "composicion de capital",
                    "tipo de actividad",
                    "relacione o indique a continuacion",
                    "datos de la persona que esta a cargo",
                    "proceso de relacionamiento",
                    "relacionamiento o de contratacion",
                    "persona que esta a cargo"
                ])
            ):
                section_candidates.append((b[1], b[3], txt))
        section_candidates.sort(key=lambda x: x[0])

        for w in widgets:
            wr = w.rect
            attr_label = getattr(w, 'field_label', '') or ''
            if re.match(r'^(celda|cell|textfield|datetimefield|field|fila|row|tabla|table|texto|independiente|listabotonesradio)\d*$', attr_label.strip(), re.IGNORECASE) or re.match(r'^\d+\.?$', attr_label.strip()):
                attr_label = ""

            # Words immediately above the widget strictly overlapping its column width (up to 35pt for table column headers)
            # Allows up to 4pt vertical overlap for descenders, and excludes words separated by an intervening widget in the same column
            cands = [wd for wd in words if wd[1] <= wr.y0 + 2 and wr.y0 - wd[3] >= -4 and (wr.y0 - wd[1]) < 35 and (wd[2] >= wr.x0 - 4 and wd[0] <= wr.x1 + 4)]
            cands = [wd for wd in cands if not any(other.field_name != w.field_name and (other.rect.x0 <= wr.x1 and other.rect.x1 >= wr.x0) and (wd[1] < other.rect.y0 and other.rect.y0 < wr.y0 - 2) for other in widgets)]
            if cands:
                cands_sorted = sorted(cands, key=lambda x: (round(x[1] / 6), x[0]))
                above_str = " ".join(wd[4] for wd in cands_sorted)
            else:
                above_str = ""

            # Words to the left on the same horizontal baseline band
            left_words = [nw[4] for nw in sorted([wd for wd in words if abs(wd[1] - wr.y0) < 10 and wd[2] <= wr.x0 + 2 and (wr.x0 - wd[2]) < 130], key=lambda x: (x[1], x[0]))]
            left_str = " ".join(left_words)

            # Closest preceding section header
            section_header = ""
            for cand_y0, cand_y1, cand_txt in section_candidates:
                if cand_y0 <= wr.y0 + 5:
                    section_header = cand_txt

            # Pre-filled status (strict detection so pre-existing values are never overwritten)
            val = w.field_value
            val_str = str(val).strip() if val is not None else ""
            is_prefilled = bool(val_str and val_str not in ["Off", "0", "None"])

            is_table_cell = bool(re.search(r'(?:tabla|fila|cell|celda|grid|table|row)[\d_\[]', w.field_name, re.IGNORECASE))
            label = attr_label or (above_str if (is_table_cell and above_str) else (left_str or above_str)) or w.field_name
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
                "page": pno,
                "is_prefilled": is_prefilled,
                "current_value": val_str,
                "is_secondary_row": False
            })

    # Identify table secondary rows across widgets
    for rw in rich_widgets:
        fn = rw["field_name"]
        wr = rw["rect"]
        sec_norm = normalize_label(rw.get("section", ""))

        # 1. Explicit row indices in field name: Fila1[1], Row[2], Item[3]
        m_brk = re.search(r'(?:Fila|Row|Item|Tabla\d*)\[(\d+)\]', fn, re.IGNORECASE)
        if m_brk and int(m_brk.group(1)) > 0:
            rw["is_secondary_row"] = True
            continue
        m_num = re.search(r'(?:fila|row|item)(\d+)', fn, re.IGNORECASE)
        if m_num and int(m_num.group(1)) > 1:
            rw["is_secondary_row"] = True
            continue
        if re.search(r'(?:accionistas|junta|revisor|patente|publicacion|profesionales|vinculo|contrat)[\w\s]*_([2-9]|\d{2,})$', fn, re.IGNORECASE):
            rw["is_secondary_row"] = True
            continue
        # Table/list secondary rows with explicit numerical suffixes (e.g. 'beneficiario final 2', 'Tipo Ident. 2', 'número de identificación 2')
        if re.search(r'(?:beneficiario|accionista|socio|miembro|directivo|tipo\s+ident\.?|identificaci[oó]n)[\w\s\.]*?\s+([2-9]|\d{2,})$', fn, re.IGNORECASE):
            rw["is_secondary_row"] = True
            continue

        # 2. Table grid sections with unindexed cell IDs (e.g. Composición Accionaria in F-UC 01)
        is_composicion_sec = any(k in sec_norm for k in [
            "composicion accionaria", "anexo de composicion", "socios con participacion"
        ])
        if is_composicion_sec and (wr.y0 > 235 or (fn.isdigit() and int(fn) not in [1, 2, 38, 57])):
            rw["is_secondary_row"] = True
            continue

    # Cross-widget counterpart detection (e.g. SI/NO pairs or Radio options where one is already answered)
    prefilled_names = {rw["field_name"] for rw in rich_widgets if rw["is_prefilled"]}
    for rw in rich_widgets:
        fn = rw["field_name"]
        if not rw["is_prefilled"]:
            m_no = re.match(r'^NO(\d+)$', fn, re.IGNORECASE)
            m_si = re.match(r'^SI(\d+)$', fn, re.IGNORECASE)
            if m_no and f"SI{m_no.group(1)}" in prefilled_names:
                rw["is_prefilled"] = True
            elif m_si and f"NO{m_si.group(1)}" in prefilled_names:
                rw["is_prefilled"] = True
            elif re.match(r'^OP\d+$', fn, re.IGNORECASE) and any(re.match(r'^OP\d+$', pn, re.IGNORECASE) for pn in prefilled_names):
                rw["is_prefilled"] = True

    return rich_widgets

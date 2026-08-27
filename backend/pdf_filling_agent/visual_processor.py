"""
Visual PDF processor for handling flat / non-interactive PDFs.
Extracts geometry, coordinates, overlays text, formatting, marks, and images/signatures.
"""

import os
import base64
import io
import re
from typing import Dict, Any, List, Optional, Tuple
import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from .cv_detector import CVFormDetector, DetectedBox


class VisualPlacement(BaseModel):
    """Model representing where and how to place text or images on a flat PDF."""
    page: int = Field(description="0-indexed page number where text should be placed")
    rect: Optional[List[float]] = Field(
        default=None,
        description="[x0, y0, x1, y1] bounding rectangle where text or image should be fitted"
    )
    point: Optional[List[float]] = Field(
        default=None,
        description="[x, y] coordinates for text insertion if rect is not used"
    )
    text: str = Field(default="", description="Text value or mark (e.g., 'X') to insert")
    font_size: float = Field(default=10.0, description="Font size for inserted text")
    font_family: Optional[str] = Field(default="Arial", description="Font family name (Arial, Calibri, Helvetica, Times New Roman, Courier)")
    bold: bool = Field(default=False, description="Whether text should be bold")
    color_rgb: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="RGB color tuple normalized 0.0 to 1.0")
    align: int = Field(default=0, description="0=Left, 1=Center, 2=Right alignment")
    field_description: Optional[str] = Field(default="", description="Description of the field being filled")
    item_type: str = Field(default="text", description="'text' or 'image'")
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded image or signature")


class PageImage(BaseModel):
    """Model representing a rendered page image with metadata."""
    page: int
    image_base64: str
    width_px: int
    height_px: int
    page_width_pts: float
    page_height_pts: float
    scale_x: float
    scale_y: float
    dpi: int


class VisualPDFProcessor:
    """Handles text extraction with coordinates, font matching, and visual overlay onto PDFs."""

    def __init__(self, output_dir: str = "output", dpi: int = 150):
        self.output_dir = output_dir
        self.dpi = dpi
        os.makedirs(output_dir, exist_ok=True)
        self.detector = CVFormDetector(dpi=dpi)

    def detect_dominant_font(self, page: fitz.Page) -> str:
        """
        Detects the dominant font family of existing text in the PDF
        and maps it to standard Base-14 PDF fonts ('helv', 'hebo', 'times', 'tibo', 'couri', 'cobo').
        """
        try:
            text_page = page.get_text("dict")
            font_counts: Dict[str, int] = {}
            for block in text_page.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line.get("spans", []):
                            font_name = span.get("font", "").lower()
                            t_len = len(span.get("text", "").strip())
                            if t_len > 0:
                                font_counts[font_name] = font_counts.get(font_name, 0) + t_len

            if not font_counts:
                return "helv"

            dom_font = max(font_counts, key=font_counts.get)
            is_bold = any(w in dom_font for w in ["bold", "black", "heavy", "medium"])

            if any(w in dom_font for w in ["times", "roman", "serif", "cambria", "garamond"]):
                return "tibo" if is_bold else "times"
            elif any(w in dom_font for w in ["courier", "mono", "consolas", "typewriter"]):
                return "cobo" if is_bold else "couri"
            else:
                return "hebo" if is_bold else "helv"
        except Exception:
            return "helv"

    def map_font_family(self, font_name: Optional[str], is_bold: bool = False) -> str:
        """Map user font family to Base-14 PDF font name."""
        if not font_name:
            return "hebo" if is_bold else "helv"
        
        fn = font_name.lower()
        if "times" in fn or "roman" in fn or "serif" in fn:
            return "tibo" if is_bold else "times"
        elif "courier" in fn or "mono" in fn:
            return "cobo" if is_bold else "couri"
        else:
            # Arial, Calibri, Helvetica, Roboto, etc.
            return "hebo" if is_bold else "helv"

    def render_page_to_image(self, pdf_path: str, page_num: int, dpi: int = 150) -> PageImage:
        """
        Render a single PDF page to a PNG image, returning base64 and coordinate metadata.
        """
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            raise ValueError(f"Page {page_num} out of bounds (total pages: {len(doc)})")

        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode()

        page_rect = page.rect
        scale_x = page_rect.width / pix.width
        scale_y = page_rect.height / pix.height

        doc.close()

        return PageImage(
            page=page_num,
            image_base64=img_b64,
            width_px=pix.width,
            height_px=pix.height,
            page_width_pts=page_rect.width,
            page_height_pts=page_rect.height,
            scale_x=scale_x,
            scale_y=scale_y,
            dpi=dpi
        )

    def render_all_pages(self, pdf_path: str, dpi: int = 150) -> List[PageImage]:
        """
        Render all pages of a PDF to images.
        """
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(len(doc)):
            doc.close()
            images.append(self.render_page_to_image(pdf_path, page_num, dpi))
            doc = fitz.open(pdf_path)
        doc.close()
        return images

    def _fit_text_to_rect(self, page: fitz.Page, rect: fitz.Rect, text: str, 
                          fontname: str = "helv",
                          max_font_size: float = 11.0, min_font_size: float = 5.5) -> float:
        """
        Find the largest font size that fits the text within the rect.
        """
        if not text:
            return min_font_size
        
        font_size = max_font_size
        while font_size >= min_font_size:
            text_width = fitz.get_text_length(text, fontname=fontname, fontsize=font_size)
            cell_width = rect.width
            cell_height = rect.height
            line_height = font_size * 1.15
            
            if text_width <= cell_width * 0.98 and line_height <= cell_height * 0.95:
                return font_size
            font_size -= 0.5
        
        return min_font_size

    def apply_cell_placement(self, page: fitz.Page, rect: List[float], text: str, 
                             font_size: float = 10.0, is_checkbox: bool = False,
                             fontname: str = "helv", color: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        """
        Place text cleanly in a cell rectangle with font-size fitting and selected font.
        """
        if not text:
            return
        
        r = fitz.Rect(rect)

        if is_checkbox:
            opt_size = min(r.width, r.height) * 0.75
            opt_size = max(8.5, min(opt_size, 14.0))
            page.insert_textbox(
                r,
                text,
                fontsize=opt_size,
                fontname="hebo",
                align=1,  # center
                color=color
            )
        else:
            fitted_size = self._fit_text_to_rect(page, r, text, fontname=fontname, max_font_size=font_size, min_font_size=5.5)
            page.insert_textbox(
                r,
                text,
                fontsize=fitted_size,
                fontname=fontname,
                align=0,  # left-aligned with padding
                color=color
            )

    def apply_visual_placements(self, input_pdf_path: str, placements: List[VisualPlacement], 
                                output_path: Optional[str] = None) -> str:
        """
        Apply visual placements (text, formatting, images, marks) onto PDF pages and save.
        """
        if not output_path:
            input_filename = os.path.basename(input_pdf_path)
            output_filename = f"filled_{input_filename}"
            output_path = os.path.join(self.output_dir, output_filename)

        doc = fitz.open(input_pdf_path)

        for placement in placements:
            if placement.page < 0 or placement.page >= len(doc):
                continue

            page = doc[placement.page]
            r = fitz.Rect(placement.rect) if placement.rect and len(placement.rect) == 4 else None

            # Handle Image/Signature Placement
            if placement.item_type == "image" and placement.image_base64 and r:
                try:
                    # Strip base64 prefix if present
                    b64_str = placement.image_base64
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64_str)
                    page.insert_image(r, stream=img_bytes, keep_proportion=True)
                except Exception as e:
                    print(f"[ERROR] Failed to insert image on page {placement.page}: {e}")
                continue

            # Handle Text Placement
            text = placement.text
            fontname = self.map_font_family(placement.font_family, placement.bold)
            color = placement.color_rgb

            if r:
                is_checkbox = (text.strip() == "X" or text.strip() == "x")
                self.apply_cell_placement(
                    page=page,
                    rect=placement.rect,
                    text=text,
                    font_size=placement.font_size,
                    is_checkbox=is_checkbox,
                    fontname=fontname,
                    color=color
                )
            elif placement.point and len(placement.point) == 2:
                p = fitz.Point(placement.point)
                page.insert_text(
                    p,
                    text,
                    fontsize=placement.font_size,
                    fontname=fontname,
                    color=color
                )

        doc.save(output_path, incremental=False)
        doc.close()
        return output_path
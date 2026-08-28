import fitz  # PyMuPDF
import base64
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class PageImage:
    page: int
    image_base64: str
    width_px: int
    height_px: int
    page_width_pts: float
    page_height_pts: float
    scale_x: float
    scale_y: float
    dpi: int

@dataclass
class VisualPlacement:
    page: int
    rect: Optional[List[float]] = None  # [x0, y0, x1, y1] in PDF points
    text: str = ""
    font_size: float = 10.0
    font_family: str = "Arial"
    bold: bool = False
    color_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    align: str = "left"  # "left", "center", "right"
    item_type: str = "text"  # "text", "checkbox", "image"
    image_base64: Optional[str] = None
    field_description: str = ""

class VisualPDFProcessor:
    def __init__(self, output_dir: str = "output", dpi: int = 150):
        self.output_dir = output_dir
        self.dpi = dpi
        os.makedirs(self.output_dir, exist_ok=True)

    def map_font_family(self, font_family: Optional[str], is_bold: bool = False) -> str:
        """
        Map CSS font names to standard PDF Base-14 font names in PyMuPDF.
        helv (Helvetica/Arial), times (Times-Roman), couri (Courier), etc.
        """
        if not font_family:
            return "hebo" if is_bold else "helv"
        
        fn = font_family.lower()
        if "times" in fn or "roman" in fn or "serif" in fn:
            return "tibo" if is_bold else "tiro"
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

    def extract_page_layouts(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract text blocks with bounding boxes for all pages in PDF.
        """
        doc = fitz.open(pdf_path)
        layouts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            rect = page.rect
            blocks = []
            for b in page.get_text("blocks"):
                if b[6] == 0 and b[4].strip():
                    blocks.append({
                        "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                        "text": b[4].strip()
                    })
            layouts.append({
                "page": page_num,
                "width": round(rect.width, 2),
                "height": round(rect.height, 2),
                "blocks": blocks
            })
        doc.close()
        return layouts

    def rect_pixels_to_points(self, page_image: PageImage, rect_px: List[float]) -> List[float]:
        """
        Convert pixel coordinates to PDF point coordinates.
        """
        return [
            rect_px[0] * page_image.scale_x,
            rect_px[1] * page_image.scale_y,
            rect_px[2] * page_image.scale_x,
            rect_px[3] * page_image.scale_y
        ]


    def apply_cell_placement(self, page: fitz.Page, rect: List[float], text: str, 
                             font_size: float = 10.0, is_checkbox: bool = False,
                             align: str = "left",
                             fontname: str = "helv", color: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        """
        Place text cleanly in a cell rectangle with WYSIWYG alignment (Left, Center, Right)
        and EXACT user-chosen font sizing. Ensures 1:1 match between screen drawing 
        and final PDF output.
        """
        if not text:
            return
        
        # Normalize rectangle coordinates
        x0 = min(rect[0], rect[2])
        y0 = min(rect[1], rect[3])
        x1 = max(rect[0], rect[2])
        y1 = max(rect[1], rect[3])
        
        if (x1 - x0) < 4:
            x1 = x0 + 4
        if (y1 - y0) < 4:
            y1 = y0 + 4
            
        r = fitz.Rect(x0, y0, x1, y1)

        # PyMuPDF align values: 0 = Left, 1 = Center, 2 = Right
        if is_checkbox or align == "center":
            align_mode = 1
        elif align == "right":
            align_mode = 2
        else:
            align_mode = 0

        if is_checkbox:
            opt_size = min(r.width, r.height) * 0.8
            opt_size = max(7.0, min(opt_size, 16.0))
            rc = page.insert_textbox(
                r,
                text,
                fontsize=opt_size,
                fontname="hebo",
                align=1,  # center
                color=color
            )
            if rc < 0:
                text_w = fitz.get_text_length(text, fontname="hebo", fontsize=opt_size)
                start_x = max(r.x0, r.x0 + (r.width - text_w) / 2)
                page.insert_text(
                    fitz.Point(start_x, r.y0 + (r.height * 0.8)),
                    text,
                    fontsize=opt_size,
                    fontname="hebo",
                    color=color
                )
        else:
            # Respect user's chosen font size directly without downscaling
            actual_size = float(font_size) if (font_size and font_size > 0) else 10.0
            
            # Ensure target rect has enough vertical room for the requested font size
            min_height_needed = actual_size * 1.3
            target_rect = r
            if r.height < min_height_needed:
                extra_h = (min_height_needed - r.height) / 2.0
                target_rect = fitz.Rect(r.x0, r.y0 - extra_h, max(r.x1, r.x0 + 10), r.y1 + extra_h)
            
            rc = page.insert_textbox(
                target_rect,
                text,
                fontsize=actual_size,
                fontname=fontname,
                align=align_mode,
                color=color
            )
            
            # If insert_textbox fails for any reason (e.g. narrow text bounds), use resilient insert_text at the EXACT font_size
            if rc < 0:
                text_w = fitz.get_text_length(text, fontname=fontname, fontsize=actual_size)
                if align_mode == 1:
                    start_x = r.x0 + (r.width - text_w) / 2
                elif align_mode == 2:
                    start_x = r.x1 - text_w - 2
                else:
                    start_x = r.x0 + 2
                
                # Baseline calculated to center text vertically in the bounding box
                baseline_y = r.y0 + (r.height + actual_size * 0.75) / 2
                page.insert_text(
                    fitz.Point(start_x, baseline_y),
                    text,
                    fontsize=actual_size,
                    fontname=fontname,
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
            
            # Normalize rect
            r = None
            if placement.rect and len(placement.rect) == 4:
                x0 = min(placement.rect[0], placement.rect[2])
                y0 = min(placement.rect[1], placement.rect[3])
                x1 = max(placement.rect[0], placement.rect[2])
                y1 = max(placement.rect[1], placement.rect[3])
                if (x1 - x0) < 4:
                    x1 = x0 + 4
                if (y1 - y0) < 4:
                    y1 = y0 + 4
                r = fitz.Rect(x0, y0, x1, y1)

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
            text = str(placement.text or "")
            if not text:
                continue

            fontname = self.map_font_family(placement.font_family, placement.bold)
            color = placement.color_rgb

            if r:
                is_checkbox = (text.strip() == "X" or text.strip() == "x")
                self.apply_cell_placement(
                    page=page,
                    rect=[r.x0, r.y0, r.x1, r.y1],
                    text=text,
                    font_size=placement.font_size,
                    is_checkbox=is_checkbox,
                    align=placement.align,
                    fontname=fontname,
                    color=color
                )

        doc.save(output_path, garbage=3, deflate=True)
        doc.close()
        return output_path
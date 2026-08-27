"""
Computer Vision form and cell detector using OpenCV + PyMuPDF.
Detects tables, cells, text fields, and checkboxes in flat PDFs.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
import fitz  # PyMuPDF
import cv2
import numpy as np
from pydantic import BaseModel, Field


class DetectedBox(BaseModel):
    """Represents a detected cell or checkbox on a PDF page."""
    box_type: str = Field(description="'cell' or 'checkbox'")
    rect: List[float] = Field(description="[x0, y0, x1, y1] in PDF point coordinates")
    center: List[float] = Field(description="[x, y] center point in PDF coordinates")
    width: float
    height: float
    page: int


class CVFormDetector:
    """Detects table cells, inputs, and checkboxes on PDF pages using OpenCV."""

    def __init__(self, dpi: int = 150):
        self.dpi = dpi

    def detect_boxes(self, page: fitz.Page, page_no: int = 0) -> List[DetectedBox]:
        """
        Render a PDF page to an image and detect all rectangular cells and checkboxes.
        """
        # 1. Render page to image pixmap
        pix = page.get_pixmap(dpi=self.dpi)
        pdf_w, pdf_h = page.rect.width, page.rect.height

        scale_x = pdf_w / pix.width
        scale_y = pdf_h / pix.height

        # Convert pixmap to numpy OpenCV image (RGB -> Grayscale)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n >= 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # 2. Binary thresholding (invert so lines are white)
        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)

        # 3. Detect horizontal lines
        h_size = max(int(pix.width / 40), 10)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=2)

        # 4. Detect vertical lines
        v_size = max(int(pix.height / 50), 10)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
        v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=2)

        # 5. Combine lines to create table grid mask
        table_mask = cv2.add(h_lines, v_lines)

        # 6. Find contours in the grid mask
        contours, hierarchy = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        detected_boxes: List[DetectedBox] = []
        seen_rects = set()

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)

            # Filter out tiny noise and full page boundaries
            if w < 10 or h < 10:
                continue
            if w > pix.width * 0.98 and h > pix.height * 0.98:
                continue

            # Convert to PDF coordinates
            x0 = round(x * scale_x, 1)
            y0 = round(y * scale_y, 1)
            x1 = round((x + w) * scale_x, 1)
            y1 = round((y + h) * scale_y, 1)
            pw = round(w * scale_x, 1)
            ph = round(h * scale_y, 1)
            cx = round((x0 + x1) / 2.0, 1)
            cy = round((y0 + y1) / 2.0, 1)

            # Avoid duplicates
            key = (round(x0, -1), round(y0, -1), round(pw, -1), round(ph, -1))
            if key in seen_rects:
                continue
            seen_rects.add(key)

            # Classify as checkbox or general table cell
            aspect_ratio = pw / ph if ph > 0 else 0
            if 8 <= pw <= 35 and 8 <= ph <= 35 and 0.65 <= aspect_ratio <= 1.5:
                box_type = "checkbox"
            else:
                box_type = "cell"

            detected_boxes.append(DetectedBox(
                box_type=box_type,
                rect=[x0, y0, x1, y1],
                center=[cx, cy],
                width=pw,
                height=ph,
                page=page_no
            ))

        return detected_boxes

    def map_labels_to_boxes(self, page: fitz.Page, page_no: int = 0) -> Dict[str, Any]:
        """
        Extract text labels and match them with adjacent empty cells or checkboxes.
        """
        boxes = self.detect_boxes(page, page_no)
        blocks = page.get_text("blocks")

        cells = [b for b in boxes if b.box_type == "cell"]
        checkboxes = [b for b in boxes if b.box_type == "checkbox"]

        matched_fields = []

        for block in blocks:
            text = block[4].strip()
            if not text:
                continue

            bx0, by0, bx1, by1 = block[0], block[1], block[2], block[3]
            bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0

            # Check if this text block is adjacent to a checkbox (e.g. "SI", "NO", "Proveedor")
            for cb in checkboxes:
                # Check horizontal adjacency (checkbox near label on same vertical line)
                if abs(bcy - cb.center[1]) < 12 and 0 < (cb.center[0] - bx1) < 45:
                    matched_fields.append({
                        "label": text,
                        "type": "checkbox",
                        "target_rect": cb.rect,
                        "center": cb.center,
                        "page": page_no
                    })
                elif abs(bcy - cb.center[1]) < 12 and 0 < (bx0 - cb.center[0]) < 45:
                    matched_fields.append({
                        "label": text,
                        "type": "checkbox",
                        "target_rect": cb.rect,
                        "center": cb.center,
                        "page": page_no
                    })

            # Check if this text is a table label and find the adjacent empty value cell
            for cell in cells:
                cx0, cy0, cx1, cy1 = cell.rect
                # Value cell immediately to the right of label cell
                if abs(by0 - cy0) < 10 and 0 <= (cx0 - bx1) < 30 and cell.width > 40:
                    matched_fields.append({
                        "label": text,
                        "type": "cell_right",
                        "target_rect": cell.rect,
                        "page": page_no
                    })
                # Value cell immediately below the label
                elif abs(bx0 - cx0) < 15 and 0 <= (cy0 - by1) < 20 and cell.height > 12:
                    matched_fields.append({
                        "label": text,
                        "type": "cell_below",
                        "target_rect": cell.rect,
                        "page": page_no
                    })

        return {
            "page": page_no,
            "total_cells": len(cells),
            "total_checkboxes": len(checkboxes),
            "cells": cells,
            "checkboxes": checkboxes,
            "matched_fields": matched_fields
        }

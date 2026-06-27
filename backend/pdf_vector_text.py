"""
Vector-PDF direct text extraction.

For CAD-exported (vector) PDFs the exact dimension text is stored in the file,
so we can read it directly instead of OCR-ing a rasterized crop. This is far more
accurate (no misreads) and also handles rotated / vertical dimensions, because
PyMuPDF returns the glyph text regardless of orientation.

The YOLO detection boxes are in the rasterized image pixel space produced by
PdfToPreprocessedImage (page points * zoom). We map each pixel box back to PDF
points using the rasterized image size vs. the PDF page size, then read the text
inside that rectangle.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency guard
    fitz = None


def is_pdf(path: str) -> bool:
    return bool(path) and os.path.splitext(path)[1].lower() == ".pdf"


def pdf_has_vector_text(pdf_path: str, page_num: int = 0, min_chars: int = 3) -> bool:
    """True when the PDF page contains selectable text (i.e. a vector/CAD export)."""
    if fitz is None or not is_pdf(pdf_path) or not os.path.isfile(pdf_path):
        return False
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return False
        page = doc[page_num]
        txt = page.get_text("text") or ""
        doc.close()
        return len(txt.strip()) >= min_chars
    except Exception:
        return False


def extract_box_texts(
    pdf_path: str,
    img_w: int,
    img_h: int,
    boxes: list,
    page_num: int = 0,
    pad_frac: float = 0.04,
) -> list[Optional[str]]:
    """
    Return the exact PDF text inside each pixel-space bbox (or None when empty/unavailable).

    boxes: list of dicts with a "bbox" = [x1, y1, x2, y2] in the rasterized image's
           full-resolution pixel space, or a raw [x1, y1, x2, y2] list.
    img_w / img_h: size of that rasterized image (must match the box coordinate space).
    """
    n = len(boxes or [])
    out: list[Optional[str]] = [None] * n
    if (
        fitz is None
        or not is_pdf(pdf_path)
        or not os.path.isfile(pdf_path)
        or img_w <= 0
        or img_h <= 0
        or n == 0
    ):
        return out
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return out
        page = doc[page_num]
        pr = page.rect
        if pr.width <= 0 or pr.height <= 0:
            doc.close()
            return out
        sx = pr.width / float(img_w)   # PDF points per pixel (x)
        sy = pr.height / float(img_h)  # PDF points per pixel (y)
        for i, d in enumerate(boxes):
            bb = (d.get("bbox") if isinstance(d, dict) else d) or []
            if len(bb) < 4:
                continue
            try:
                x1, y1, x2, y2 = [float(v) for v in bb[:4]]
            except (TypeError, ValueError):
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            pw = (x2 - x1) * pad_frac
            ph = (y2 - y1) * pad_frac
            rect = fitz.Rect(
                (x1 - pw) * sx,
                (y1 - ph) * sy,
                (x2 + pw) * sx,
                (y2 + ph) * sy,
            )
            try:
                txt = page.get_textbox(rect) or ""
            except Exception:
                txt = ""
            txt = " ".join(txt.split())
            out[i] = txt or None
        doc.close()
    except Exception:
        pass
    return out

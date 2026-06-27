"""Drawing analysis: file type, vector vs scan, sheet size, resolution, balloon density."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import cv2
    import fitz  # PyMuPDF
    import numpy as np
except Exception:  # pragma: no cover
    cv2 = fitz = np = None  # type: ignore

import pdf_vector_text

# ISO A-series long side in mm
_SHEET_MM = {"A4": 297, "A3": 420, "A2": 594, "A1": 841, "A0": 1189}


def _sheet_from_mm(long_mm: float) -> str:
    if long_mm <= 0:
        return "UNKNOWN"
    for name in ("A4", "A3", "A2", "A1", "A0"):
        if long_mm <= _SHEET_MM[name] * 1.08:
            return name
    return "A0+"


def analyze_drawing_input(
    file_path: str,
    image_bgr=None,
    dpi: float = 600.0,
    page_num: int = 0,
) -> dict[str, Any]:
    """
    Classify input and estimate sheet size / scan quality signals.
    Returns metadata consumed by adaptive detection + preprocessing.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    is_pdf = ext == ".pdf"
    is_raster = ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")

    out: dict[str, Any] = {
        "file_type": "pdf" if is_pdf else ("raster" if is_raster else "unknown"),
        "is_pdf": is_pdf,
        "is_raster": is_raster,
        "vector_pdf": False,
        "scan_like": True,
        "sheet_size": "UNKNOWN",
        "render_dpi": float(dpi),
        "page_width_mm": 0.0,
        "page_height_mm": 0.0,
        "image_width_px": 0,
        "image_height_px": 0,
        "estimated_balloon_density": 0.0,
        "detection_strategy": "yolo_full",
    }

    if is_pdf and fitz is not None and path.is_file():
        try:
            doc = fitz.open(str(path))
            if page_num < len(doc):
                page = doc[page_num]
                pr = page.rect
                # points → mm
                w_mm = pr.width * 25.4 / 72.0
                h_mm = pr.height * 25.4 / 72.0
                out["page_width_mm"] = round(w_mm, 1)
                out["page_height_mm"] = round(h_mm, 1)
                out["sheet_size"] = _sheet_from_mm(max(w_mm, h_mm))
                out["vector_pdf"] = pdf_vector_text.pdf_has_vector_text(str(path), page_num)
                out["scan_like"] = not out["vector_pdf"]
            doc.close()
        except Exception:
            pass

    if image_bgr is not None and cv2 is not None:
        h, w = image_bgr.shape[:2]
        out["image_width_px"] = int(w)
        out["image_height_px"] = int(h)
        if out["sheet_size"] == "UNKNOWN" and dpi > 0:
            long_mm = max(w, h) * 25.4 / dpi
            out["sheet_size"] = _sheet_from_mm(long_mm)
            out["page_width_mm"] = round(w * 25.4 / dpi, 1)
            out["page_height_mm"] = round(h * 25.4 / dpi, 1)

    # Balloon density heuristic: dark ink fraction × resolution factor
    if image_bgr is not None and cv2 is not None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        ink = float(np.mean(gray < 180))
        out["estimated_balloon_density"] = round(min(1.0, ink * 12.0), 3)

    sheet = out["sheet_size"]
    if sheet in ("A4", "A3"):
        out["detection_strategy"] = "yolo_full"
    elif sheet == "A2":
        out["detection_strategy"] = "yolo_multiscale"
    elif sheet in ("A1", "A0", "A0+"):
        out["detection_strategy"] = "sahi_yolo"
    else:
        long_px = max(out["image_width_px"], out["image_height_px"])
        out["detection_strategy"] = "sahi_yolo" if long_px > 4500 else "yolo_full"

    return out

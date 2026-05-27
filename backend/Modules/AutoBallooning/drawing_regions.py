"""View-region tagging for per-region Claude gap-fill (reduces cross-region duplicates)."""
from __future__ import annotations

import re
from typing import Any


def _center(bb: list) -> tuple[float, float]:
    if len(bb) < 4:
        return 0.0, 0.0
    return (float(bb[0]) + float(bb[2])) / 2.0, (float(bb[1]) + float(bb[3])) / 2.0


def point_in_region(cx: float, cy: float, region: dict, margin: float = 0.0) -> bool:
    bb = region.get("bbox") or []
    if len(bb) < 4:
        return False
    x1, y1, x2, y2 = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
    if margin:
        x1 -= margin
        y1 -= margin
        x2 += margin
        y2 += margin
    return x1 <= cx <= x2 and y1 <= cy <= y2


def tag_detections_with_regions(detections: list, regions: list) -> None:
    """Set region_name / region_id on each detection from bbox center."""
    if not regions:
        return
    for d in detections or []:
        bb = (d or {}).get("bbox") or []
        cx, cy = _center(bb)
        matched = None
        for reg in regions:
            if point_in_region(cx, cy, reg, margin=8):
                matched = reg
                break
        if matched:
            d["region_name"] = str(matched.get("name") or matched.get("id") or "")
            d["region_id"] = matched.get("id") or matched.get("name")
        else:
            d["region_name"] = ""
            d["region_id"] = ""


def detections_in_region(detections: list, region: dict, margin: float = 12) -> list:
    out = []
    for d in detections or []:
        bb = (d or {}).get("bbox") or []
        cx, cy = _center(bb)
        if point_in_region(cx, cy, region, margin=margin):
            out.append(d)
    return out


def normalize_region_entry(entry: dict, img_w: int, img_h: int) -> dict | None:
    if not isinstance(entry, dict):
        return None
    name = str(entry.get("name") or entry.get("region") or entry.get("label") or "").strip()
    if not name:
        name = "Region"
    bb = entry.get("bbox")
    if not isinstance(bb, list) or len(bb) < 4:
        x1 = int(entry.get("x_min") or entry.get("x1") or 0)
        y1 = int(entry.get("y_min") or entry.get("y1") or 0)
        x2 = int(entry.get("x_max") or entry.get("x2") or img_w)
        y2 = int(entry.get("y_max") or entry.get("y2") or img_h)
        bb = [x1, y1, x2, y2]
    x1, y1, x2, y2 = [int(v) for v in bb[:4]]
    x1 = max(0, min(img_w - 1, x1))
    y1 = max(0, min(img_h - 1, y1))
    x2 = max(x1 + 1, min(img_w, x2))
    y2 = max(y1 + 1, min(img_h, y2))
    rid = re.sub(r"[^\w\-]+", "_", name.lower()).strip("_") or "region"
    return {
        "id": rid,
        "name": name,
        "bbox": [x1, y1, x2, y2],
        "description": str(entry.get("description") or "")[:200],
    }


def parse_regions_from_llm(parsed: Any, img_w: int, img_h: int) -> list[dict]:
    rows: list = []
    if isinstance(parsed, dict):
        rows = parsed.get("regions") or parsed.get("views") or []
    elif isinstance(parsed, list):
        rows = parsed
    out: list[dict] = []
    for entry in rows or []:
        reg = normalize_region_entry(entry, img_w, img_h)
        if reg:
            out.append(reg)
    return out

"""Quality control + coverage verification."""
from __future__ import annotations

import re
from typing import Any


def _bbox_area(bb: list) -> float:
    if not bb or len(bb) < 4:
        return 0.0
    return max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])


def _combined_text(item: dict) -> str:
    return " ".join(
        str(item.get(k) or "")
        for k in ("nominal_value", "tolerance", "others", "raw_ocr", "detected_text")
    ).strip()


def run_quality_control(payload: dict) -> dict[str, Any]:
    """
    QC Engine: duplicates, OCR conflicts, low-confidence review flags.
    """
    items = list(payload.get("balloon_items") or [])
    dets = list(payload.get("detections") or payload.get("detections_full") or [])
    iou_dup = 0.55
    duplicates: list[int] = []
    conflicts: list[int] = []
    low_conf: list[int] = []

    for i in range(len(items)):
        it = items[i]
        bb_i = it.get("bbox_pixels") or (dets[i].get("bbox") if i < len(dets) else None)
        for j in range(i + 1, len(items)):
            bb_j = items[j].get("bbox_pixels") or (dets[j].get("bbox") if j < len(dets) else None)
            if not bb_i or not bb_j:
                continue
            from drawing_pipeline.detection import _bbox_iou

            if _bbox_iou(bb_i, bb_j) >= iou_dup:
                duplicates.append(j)
        txt_i = _combined_text(it)
        nom = str(it.get("nominal_value") or "")
        raw = str(it.get("raw_ocr") or "")
        if nom and raw and nom not in raw and raw not in nom:
            if re.search(r"\d", nom) and re.search(r"\d", raw):
                if re.sub(r"\D", "", nom) != re.sub(r"\D", "", raw):
                    conflicts.append(i)
        conf = it.get("confidence")
        try:
            if conf is not None and float(conf) < 0.45:
                low_conf.append(i)
        except (TypeError, ValueError):
            pass

    qc = {
        "duplicate_indices": sorted(set(duplicates)),
        "ocr_conflict_indices": sorted(set(conflicts)),
        "low_confidence_indices": sorted(set(low_conf)),
        "passed": not duplicates and not conflicts,
    }
    payload["quality_control"] = qc
    return qc


def compute_coverage_metrics(payload: dict, analysis: dict | None = None) -> dict[str, Any]:
    """
    Coverage verification: balloon count, estimated density, quality score.
    """
    items = list(payload.get("balloon_items") or [])
    dets = list(payload.get("detections") or [])
    img_w = int(payload.get("width") or analysis.get("image_width_px") or 0)
    img_h = int(payload.get("height") or analysis.get("image_height_px") or 0)
    img_area = max(1.0, img_w * img_h)

    ink_regions = 0
    for it in items:
        bb = it.get("bbox_pixels") or []
        if _bbox_area(bb) > img_area * 0.00002:
            ink_regions += 1

    expected = float((analysis or {}).get("estimated_balloon_density") or 0.15) * 80
    expected = max(3.0, expected)
    coverage_pct = min(100.0, 100.0 * len(items) / expected) if expected else 100.0

    qc = payload.get("quality_control") or {}
    penalty = len(qc.get("duplicate_indices") or []) * 5
    penalty += len(qc.get("ocr_conflict_indices") or []) * 8
    penalty += len(qc.get("low_confidence_indices") or []) * 3
    quality_score = max(0.0, min(100.0, coverage_pct - penalty))

    cov = {
        "balloon_count": len(items),
        "detection_count": len(dets),
        "coverage_percent": round(coverage_pct, 1),
        "quality_score": round(quality_score, 1),
        "expected_balloons_estimate": round(expected, 1),
        "missing_regions_hint": coverage_pct < 65.0,
    }
    payload["coverage_metrics"] = cov
    return cov

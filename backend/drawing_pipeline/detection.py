"""Adaptive YOLO / multi-scale / SAHI (300×300 tiles) + detection fusion."""
from __future__ import annotations

import os
import tempfile
from typing import Any

import cv2
import numpy as np


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)).strip())
    except ValueError:
        return default


SAHI_TILE = _env_int("BALLOON_SAHI_TILE", 300)
SAHI_OVERLAP = _env_float("BALLOON_SAHI_OVERLAP", 0.0)  # 0% overlap default


def _bbox_iou(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = [float(v) for v in a[:4]]
    bx1, by1, bx2, by2 = [float(v) for v in b[:4]]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    bb = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aa + bb - inter
    return inter / union if union > 0 else 0.0


def _run_yolo_on_image(
    tasks_mod,
    image_path: str,
    imgsz: int,
    conf: float,
    long_side: int,
    is_pdf: bool,
) -> list[dict]:
    pad = max(5, min(18, int(long_side * 0.003)))
    web_class_conf = tasks_mod.yolo_web_class_conf_thresholds()
    preds = tasks_mod.RunInference(
        None,
        image_path,
        imgsz=imgsz,
        conf_thres=conf,
        CustomNms_threshold=0.82,
        bbox_padding=pad,
        class_conf_thres=web_class_conf,
        apply_legacy_merges=False,
    )
    out = []
    for d in preds:
        bb = d.get("bbox")
        if not bb or len(bb) < 4:
            continue
        out.append(
            {
                "class_name": d.get("class_name"),
                "confidence": float(d.get("conf") or 0),
                "bbox": [int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])],
                "source": "yolo",
            }
        )
    return out


def _run_yolo_on_bgr(tasks_mod, bgr: np.ndarray, imgsz: int, conf: float, is_pdf: bool) -> list[dict]:
    h, w = bgr.shape[:2]
    long_side = max(h, w)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        cv2.imwrite(path, bgr)
        return _run_yolo_on_image(tasks_mod, path, imgsz, conf, long_side, is_pdf)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _sahi_tiles(h: int, w: int, tile: int, overlap_ratio: float) -> list[tuple[int, int, int, int]]:
    step = max(1, int(tile * (1.0 - overlap_ratio)))
    tiles = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            x2 = min(w, x + tile)
            y2 = min(h, y + tile)
            x1 = max(0, x2 - tile)
            y1 = max(0, y2 - tile)
            tiles.append((x1, y1, x2, y2))
    return tiles


def _sahi_detect(tasks_mod, bgr: np.ndarray, imgsz: int, conf: float, is_pdf: bool) -> list[dict]:
    h, w = bgr.shape[:2]
    tile = max(128, SAHI_TILE)
    overlap = max(0.0, min(0.5, SAHI_OVERLAP))
    all_dets: list[dict] = []
    for x1, y1, x2, y2 in _sahi_tiles(h, w, tile, overlap):
        crop = bgr[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        local = _run_yolo_on_bgr(tasks_mod, crop, min(imgsz, max(tile, 320)), conf, is_pdf)
        for d in local:
            bb = d["bbox"]
            all_dets.append(
                {
                    "class_name": d["class_name"],
                    "confidence": d["confidence"],
                    "bbox": [bb[0] + x1, bb[1] + y1, bb[2] + x1, bb[3] + y1],
                    "source": "sahi_yolo",
                }
            )
    return all_dets


def _multiscale_detect(
    tasks_mod, bgr: np.ndarray, imgsz: int, conf: float, is_pdf: bool, *, large: bool = False
) -> list[dict]:
    scales = [0.75, 1.0] if large else [0.75, 1.0, 1.25]
    h, w = bgr.shape[:2]
    all_dets: list[dict] = []
    for sc in scales:
        nh, nw = max(1, int(h * sc)), max(1, int(w * sc))
        scaled = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR if sc >= 1 else cv2.INTER_AREA)
        local = _run_yolo_on_bgr(tasks_mod, scaled, imgsz, conf, max(nh, nw), is_pdf)
        inv = 1.0 / sc
        for d in local:
            bb = d["bbox"]
            all_dets.append(
                {
                    "class_name": d["class_name"],
                    "confidence": d["confidence"],
                    "bbox": [
                        int(bb[0] * inv),
                        int(bb[1] * inv),
                        int(bb[2] * inv),
                        int(bb[3] * inv),
                    ],
                    "source": "multiscale_yolo",
                }
            )
    return all_dets


def fuse_detection_sets(
    detection_lists: list[list[dict]],
    iou_thresh: float | None = None,
) -> list[dict]:
    """Detection Fusion Engine — merge multi-view / SAHI / scale results."""
    iou = iou_thresh if iou_thresh is not None else _env_float("BALLOON_FUSION_IOU", 0.45)
    merged: list[dict] = []
    for dets in detection_lists:
        for d in dets or []:
            bb = d.get("bbox") or []
            if len(bb) < 4:
                continue
            dup = False
            for i, m in enumerate(merged):
                if _bbox_iou(bb, m["bbox"]) >= iou:
                    dup = True
                    if float(d.get("confidence") or 0) > float(m.get("confidence") or 0):
                        merged[i] = dict(d)
                    break
            if not dup:
                merged.append(dict(d))
    return merged


def adaptive_yolo_detect(
    tasks_mod,
    bgr: np.ndarray,
    analysis: dict[str, Any],
    is_pdf: bool,
) -> tuple[list[dict], dict[str, Any]]:
    """
    Adaptive Detection Strategy Engine:
      A4/A3 → full image YOLO
      A2    → multi-scale YOLO
      A1/A0 → SAHI 300×300 + YOLO
    Also runs YOLO on multi-view variants and fuses.
    """
    from drawing_pipeline.preprocess import generate_multi_views, is_large_image

    h, w = bgr.shape[:2]
    large = is_large_image(bgr)
    long_side = max(h, w)
    imgsz, conf = tasks_mod.yolo_autoballoon_inference_params(long_side, is_pdf)
    strategy = (analysis or {}).get("detection_strategy") or "yolo_full"

    meta: dict[str, Any] = {
        "strategy": strategy,
        "sahi_tile_px": SAHI_TILE,
        "sahi_overlap": SAHI_OVERLAP,
        "yolo_imgsz": imgsz,
        "yolo_conf": conf,
    }

    lists: list[list[dict]] = []
    views = generate_multi_views(bgr)
    primary = views.get("enhanced_original") or bgr

    if strategy == "sahi_yolo":
        lists.append(_sahi_detect(tasks_mod, primary, imgsz, conf, is_pdf))
        meta["sahi_tiles"] = len(_sahi_tiles(h, w, max(128, SAHI_TILE), SAHI_OVERLAP))
    elif strategy == "yolo_multiscale":
        lists.append(_multiscale_detect(tasks_mod, primary, imgsz, conf, is_pdf, large=large))
    else:
        lists.append(_run_yolo_on_bgr(tasks_mod, primary, imgsz, conf, is_pdf))

    if not large:
        for key in ("edge_enhanced", "high_contrast"):
            view = views.get(key)
            if view is None:
                continue
            extra = _run_yolo_on_bgr(tasks_mod, view, imgsz, conf * 0.95, is_pdf)
            for d in extra:
                d["source"] = f"yolo_{key}"
            lists.append(extra)

    fused = fuse_detection_sets(lists)
    meta["raw_detections"] = sum(len(x) for x in lists)
    meta["fused_detections"] = len(fused)
    return fused, meta

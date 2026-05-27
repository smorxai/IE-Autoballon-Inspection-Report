"""OpenCV extension-line / dimension-line candidates (any angle) for Claude gap-fill."""
from __future__ import annotations

import math
from typing import List, Tuple

import cv2
import numpy as np


def _line_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0


def _angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def detect_dim_line_candidates(
    image_path: str,
    max_candidates: int = 80,
) -> List[dict]:
    """
    Find parallel extension-line pairs via Hough transform; return tight bboxes
    for dimension callout regions (horizontal and vertical).
    """
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return []
    h, w = gray.shape[:2]
    if h < 40 or w < 40:
        return []

    scale = 1.0
    max_side = max(h, w)
    if max_side > 2400:
        scale = 2400.0 / max_side
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = gray.shape[:2]

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)
    min_len = max(18, int(min(h, w) * 0.018))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=55,
        minLineLength=min_len,
        maxLineGap=8,
    )
    if lines is None:
        return []

    segments: List[Tuple[float, float, float, float, float, float]] = []
    for ln in lines.reshape(-1, 4):
        x1, y1, x2, y2 = [float(v) for v in ln]
        length = math.hypot(x2 - x1, y2 - y1)
        if length < min_len:
            continue
        ang = _line_angle(x1, y1, x2, y2)
        segments.append((x1, y1, x2, y2, length, ang))

    pairs: List[Tuple[Tuple, Tuple, float]] = []
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            s1, s2 = segments[i], segments[j]
            if _angle_diff(s1[5], s2[5]) > 6.0:
                continue
            mid1 = ((s1[0] + s1[2]) / 2, (s1[1] + s1[3]) / 2)
            mid2 = ((s2[0] + s2[2]) / 2, (s2[1] + s2[3]) / 2)
            sep = math.hypot(mid1[0] - mid2[0], mid1[1] - mid2[1])
            if sep < 12 or sep > min(h, w) * 0.35:
                continue
            d1 = _dist_point_to_segment(mid2[0], mid2[1], s1[0], s1[1], s1[2], s1[3])
            d2 = _dist_point_to_segment(mid1[0], mid1[1], s2[0], s2[1], s2[2], s2[3])
            if max(d1, d2) > sep * 0.55:
                continue
            pairs.append((s1, s2, sep))

    pairs.sort(key=lambda p: -p[2])
    candidates: List[dict] = []
    used_centers: List[Tuple[float, float]] = []

    def to_full(bb: List[int]) -> List[int]:
        if abs(scale - 1.0) < 0.001:
            return bb
        inv = 1.0 / scale
        return [int(bb[0] * inv), int(bb[1] * inv), int(bb[2] * inv), int(bb[3] * inv)]

    orig_h = int(gray.shape[0] / scale) if scale != 1.0 else h
    orig_w = int(gray.shape[1] / scale) if scale != 1.0 else w

    for s1, s2, _sep in pairs:
        xs = [s1[0], s1[2], s2[0], s2[2]]
        ys = [s1[1], s1[3], s2[1], s2[3]]
        cx = sum(xs) / 4.0
        cy = sum(ys) / 4.0
        if any(math.hypot(cx - u[0], cy - u[1]) < 28 for u in used_centers):
            continue
        pad = max(14, int(_sep * 0.35))
        x1 = int(min(xs) - pad)
        y1 = int(min(ys) - pad)
        x2 = int(max(xs) + pad)
        y2 = int(max(ys) + pad)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue
        bb = to_full([x1, y1, x2, y2])
        bb[0] = max(0, min(orig_w - 1, bb[0]))
        bb[1] = max(0, min(orig_h - 1, bb[1]))
        bb[2] = max(bb[0] + 1, min(orig_w, bb[2]))
        bb[3] = max(bb[1] + 1, min(orig_h, bb[3]))
        candidates.append(
            {
                "class_name": "Dimensions",
                "confidence": 0.55,
                "bbox": bb,
                "source": "opencv_dim_line",
                "description": "extension-line pair",
            }
        )
        used_centers.append((cx, cy))
        if len(candidates) >= max_candidates:
            break

    return candidates

"""Image analysis metrics + adaptive preprocessing + multi-view generation."""
from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np


def _large_image_pixel_threshold() -> int:
    try:
        return int(os.environ.get("BALLOON_LARGE_IMAGE_PIXELS", "35000000"))
    except ValueError:
        return 35_000_000


def is_large_image(bgr: np.ndarray) -> bool:
    h, w = bgr.shape[:2]
    return h * w > _large_image_pixel_threshold()


def _laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _noise_estimate(gray: np.ndarray) -> float:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    return float(np.std(gray.astype(np.float32) - blur.astype(np.float32)))


def _contrast_score(gray: np.ndarray) -> float:
    return float(gray.std())


def _skew_angle_deg(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=120, minLineLength=80, maxLineGap=10)
    if lines is None or len(lines) < 4:
        return 0.0
    angles = []
    for ln in lines[:80]:
        x1, y1, x2, y2 = ln[0]
        if abs(x2 - x1) < 8:
            continue
        angles.append(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
    if not angles:
        return 0.0
    return float(np.median(angles))


def _border_ink_ratio(gray: np.ndarray, frac: float = 0.04) -> float:
    h, w = gray.shape[:2]
    t = max(2, int(min(h, w) * frac))
    bands = [
        gray[:t, :],
        gray[h - t :, :],
        gray[:, :t],
        gray[:, w - t :],
    ]
    return float(np.mean([np.mean(b < 200) for b in bands if b.size]))


def analyze_image_quality(bgr: np.ndarray) -> dict[str, Any]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if is_large_image(bgr):
        return {
            "blur_score": 200.0,
            "is_blurry": False,
            "noise_score": 0.0,
            "is_noisy": False,
            "contrast_score": round(_contrast_score(gray), 2),
            "low_contrast": _contrast_score(gray) < 35.0,
            "skew_deg": 0.0,
            "needs_deskew": False,
            "border_ink_ratio": 0.0,
            "has_heavy_border": False,
            "resolution_px": [int(w), int(h)],
            "line_quality": 0.5,
            "large_image_fast_metrics": True,
        }
    blur = _laplacian_variance(gray)
    return {
        "blur_score": round(blur, 2),
        "is_blurry": blur < 80.0,
        "noise_score": round(_noise_estimate(gray), 2),
        "is_noisy": _noise_estimate(gray) > 18.0,
        "contrast_score": round(_contrast_score(gray), 2),
        "low_contrast": _contrast_score(gray) < 35.0,
        "skew_deg": round(_skew_angle_deg(gray), 2),
        "needs_deskew": abs(_skew_angle_deg(gray)) > 0.8,
        "border_ink_ratio": round(_border_ink_ratio(gray), 4),
        "has_heavy_border": _border_ink_ratio(gray) > 0.35,
        "resolution_px": [int(w), int(h)],
        "line_quality": round(min(1.0, blur / 400.0), 3),
    }


def _deskew(bgr: np.ndarray, angle_deg: float) -> np.ndarray:
    if abs(angle_deg) < 0.5:
        return bgr
    h, w = bgr.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(
        bgr, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )


def _remove_border(bgr: np.ndarray, frac: float = 0.025) -> np.ndarray:
    h, w = bgr.shape[:2]
    t = max(2, int(min(h, w) * frac))
    out = bgr.copy()
    out[:t, :] = 255
    out[h - t :, :] = 255
    out[:, :t] = 255
    out[:, w - t :] = 255
    return out


def _denoise(bgr: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(bgr, None, 6, 6, 7, 21)


def _clahe(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,  8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _enhance_lines(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = cv2.bitwise_not(th)
    kernel = np.ones((2, 2), np.uint8)
    thick = cv2.dilate(inv, kernel, iterations=1)
    final = cv2.bitwise_not(thick)
    return cv2.cvtColor(final, cv2.COLOR_GRAY2BGR)


def _sharpen(bgr: np.ndarray) -> np.ndarray:
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    return cv2.filter2D(bgr, -1, kernel)


def adaptive_preprocess_drawing(bgr: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Image Analysis Agent + Adaptive Processing Decision Engine.
    Returns enhanced BGR image and decision log.
    """
    large = is_large_image(bgr)
    metrics = analyze_image_quality(bgr)
    decisions: list[str] = []
    out = bgr if large else bgr.copy()

    if metrics.get("needs_deskew") and not large:
        out = _deskew(out, metrics["skew_deg"])
        decisions.append("deskew")
    if metrics.get("has_heavy_border") and not large:
        out = _remove_border(out)
        decisions.append("border_removal")
    if metrics.get("is_noisy") and not large:
        out = _denoise(out)
        decisions.append("noise_removal")
    if metrics.get("low_contrast"):
        out = _clahe(out)
        decisions.append("clahe")
    if metrics.get("line_quality", 0) < 0.35 and not large:
        out = _enhance_lines(out)
        decisions.append("line_enhancement")
    if metrics.get("is_blurry") and not large:
        out = _sharpen(out)
        decisions.append("sharpening")
    if (metrics.get("low_contrast") or metrics.get("is_blurry")) and not large:
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if float(np.mean(th)) < 127:
            th = cv2.bitwise_not(th)
        blend = cv2.addWeighted(out, 0.65, cv2.cvtColor(th, cv2.COLOR_GRAY2BGR), 0.35, 0)
        out = blend
        decisions.append("threshold_blend")
    if large:
        decisions.append("large_image_light_path")

    meta = {"image_analysis": metrics, "preprocess_applied": decisions}
    return out, meta


def generate_multi_views(bgr: np.ndarray) -> dict[str, np.ndarray]:
    """Multi Image Generator: enhanced, binary, edge, high-contrast."""
    if is_large_image(bgr):
        return {"enhanced_original": bgr}

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(gray, 40, 120)
    edge_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    hi = clahe.apply(gray)
    hi_bgr = cv2.cvtColor(hi, cv2.COLOR_GRAY2BGR)
    return {
        "enhanced_original": bgr,
        "binary": cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR),
        "edge_enhanced": edge_bgr,
        "high_contrast": hi_bgr,
    }

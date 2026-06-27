"""
Full drawing analysis → detection → OCR → QC pipeline.

Stages (excluding pgVector, AS9102 FAIR, Gemini, Surya per product scope):
  analysis → preprocess → adaptive YOLO/SAHI → fusion → OCR normalize →
  engineering parse → feature association → QC/coverage → balloon placement.
"""
from drawing_pipeline.analysis import analyze_drawing_input
from drawing_pipeline.preprocess import adaptive_preprocess_drawing, generate_multi_views
from drawing_pipeline.detection import adaptive_yolo_detect, fuse_detection_sets
from drawing_pipeline.ocr_normalize import normalize_ocr_item
from drawing_pipeline.engineering import parse_engineering_item, associate_features
from drawing_pipeline.quality import run_quality_control, compute_coverage_metrics

__all__ = [
    "analyze_drawing_input",
    "adaptive_preprocess_drawing",
    "generate_multi_views",
    "adaptive_yolo_detect",
    "fuse_detection_sets",
    "normalize_ocr_item",
    "parse_engineering_item",
    "associate_features",
    "run_quality_control",
    "compute_coverage_metrics",
]

"""Engineering parser + feature association."""
from __future__ import annotations

import re
from typing import Any


def _feature_type_from_text(text: str, class_name: str) -> str:
    t = (text or "").upper()
    cls = (class_name or "").lower()
    if "gdt" in cls or "gd" in cls:
        return "GD&T"
    if "datum" in cls:
        return "Datum"
    if "weld" in cls:
        return "Weld"
    if "surface" in cls or re.search(r"\bRa\b|\bRz\b", t):
        return "Surface Finish"
    if "note" in cls:
        return "Note"
    if re.search(r"[Ø⌀∅]|DIA", t):
        return "Diameter"
    if re.search(r"\bR\d", t):
        return "Radius"
    if re.search(r"°|DEG|C\d", t):
        return "Angular"
    if re.search(r"\bM\d|\bUNC|\bUNF|THREAD", t):
        return "Thread"
    return "Linear"


def parse_engineering_item(item: dict) -> dict:
    """Structured engineering fields from normalized OCR."""
    out = dict(item or {})
    blob = " ".join(
        str(out.get(k) or "")
        for k in ("nominal_value", "tolerance", "others", "raw_ocr", "detected_text")
    ).strip()
    cls = str(out.get("class_name") or "Dimensions")
    out["feature_type"] = out.get("feature_type") or _feature_type_from_text(blob, cls)
    m = re.search(r"(\d+\s*[xX×])", blob)
    if m:
        out["quantity_notation"] = m.group(1).strip()
    if re.search(r"\bTHRU\b", blob, re.I):
        out["hole_type"] = "THRU"
    elif re.search(r"\bCB\b|COUNTERBORE", blob, re.I):
        out["hole_type"] = "Counterbore"
    elif re.search(r"\bCSK\b|COUNTERSINK", blob, re.I):
        out["hole_type"] = "Countersink"
    if re.search(r"\(\s*\d+\.?\d*\s*\)", blob) or out.get("tolerance_type") == "Reference":
        out["tolerance_type"] = "Reference"
    if re.match(r"^a\s+\d", blob, re.I) or "weld" in cls:
        out["feature_type"] = out.get("feature_type") or "Weld"
    return out


def associate_features(items: list[dict]) -> list[dict]:
    """
    Feature Association: link balloons to dimension / GD&T / notes / features.
    """
    out: list[dict] = []
    gdt_items = []
    dim_items = []
    note_items = []
    for it in items or []:
        row = dict(it)
        ft = str(row.get("feature_type") or "").lower()
        cls = str(row.get("class_name") or "").lower()
        if "gd" in ft or "gdt" in cls:
            row["association"] = "gdt"
            gdt_items.append(row)
        elif "note" in cls or "note" in ft:
            row["association"] = "note"
            note_items.append(row)
        else:
            row["association"] = "dimension"
            dim_items.append(row)
        out.append(row)

    # Simple datum reference propagation for GD&T rows
    for g in gdt_items:
        refs = re.findall(r"\b[A-Z]\b", str(g.get("tolerance") or "") + " " + str(g.get("others") or ""))
        if refs:
            g["datum_refs"] = list(dict.fromkeys(refs))

    return out

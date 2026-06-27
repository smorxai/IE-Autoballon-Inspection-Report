"""OCR normalization: symbols, GD&T, correction, multi-number split."""
from __future__ import annotations

import re
from typing import Any


def _recover_symbols(text: str) -> str:
    t = text or ""
    t = t.replace("⌀", "Ø").replace("∅", "Ø")
    t = re.sub(r"%%[cC]", "Ø", t)
    t = re.sub(r"\bDIA\.?\s*", "Ø", t, flags=re.IGNORECASE)
    t = re.sub(r"(^|\s)[@OQ](?=\d)", lambda m: m.group(1) + "Ø", t)
    t = re.sub(r"\bR\s*(\d)", r"R\1", t)
    return t


def _recover_gdt(text: str) -> str:
    t = text or ""
    repl = {
        "POSITION": "⌖",
        "FLATNESS": "⏥",
        "PARALLELISM": "∥",
        "PERPENDICULARITY": "⊥",
        "CIRCULARITY": "○",
        "CYLINDRICITY": "⌭",
    }
    for k, sym in repl.items():
        t = re.sub(rf"\b{k}\b", sym, t, flags=re.IGNORECASE)
    return t


def _recover_reference_dim(text: str) -> str:
    """Reference dimension (1500) → 1500 for parsing; keep parens in raw_ocr."""
    t = (text or "").strip()
    m = re.match(r"^\(\s*(\d+\.?\d*)\s*\)$", t)
    if m:
        return m.group(1)
    return t


def _recover_weld_notation(text: str) -> str:
    """Normalize fillet weld throat: a5 → a 5; dedupe mirrored a 5 a 5."""
    t = _normalize_european_decimal((text or "").strip())
    if not t:
        return t
    vals = re.findall(r"\ba\s*(\d+\.?\d*)\b", t, re.IGNORECASE)
    if vals:
        return f"a {vals[0]}"
    m = re.match(r"^a(\d+\.?\d*)$", t, re.IGNORECASE)
    if m:
        return f"a {m.group(1)}"
    return t


def _merge_stacked_tolerance_fields(item: dict) -> dict:
    """Fuse nominal + stacked tol when OCR splits +2 and 0 across fields."""
    out = dict(item or {})
    nom = str(out.get("nominal_value") or "").strip()
    tol = str(out.get("tolerance") or "").strip()
    others = str(out.get("others") or "").strip()
    if nom and re.match(r"^\+\d", tol) and re.match(r"^\d+\.?\d*$", others):
        out["tolerance"] = f"{tol}/{others}"
        out["others"] = ""
    elif nom and not tol and re.match(r"^\+\d+\.?\d*\s*/\s*\d+\.?\d*$", others):
        out["tolerance"] = others
        out["others"] = ""
    elif nom and not tol and re.match(r"^\+\d+\.?\d*\s+\d+\.?\d*$", others):
        parts = others.split()
        if len(parts) == 2:
            out["tolerance"] = f"+{parts[0].lstrip('+')}/{parts[1]}"
            out["others"] = ""
    return out


def _recover_surface_finish(text: str, class_name: str = "") -> str:
    """Ra6.3 → Ra 6.3; fix OCR 'a 6' → 'Ra 6' on surface-finish crops."""
    t = (text or "").strip()
    t = re.sub(r"^R([azt])(\d+)", r"R\1 \2", t, flags=re.IGNORECASE)
    cls = (class_name or "").lower()
    if "surface" in cls and re.match(r"^a\s+\d", t, re.IGNORECASE):
        t = re.sub(r"^a\s+", "Ra ", t, flags=re.IGNORECASE)
    return t


def _normalize_european_decimal(text: str) -> str:
    """Comma as decimal: 30,5 → 30.5, (686,8) → (686.8)."""
    t = (text or "").strip()
    if not t:
        return t
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"(\d),(\d{1,3})(?!\d)", r"\1.\2", t)
    return t


def _ocr_corrections(text: str) -> str:
    t = _normalize_european_decimal(text or "")
    fixes = [
        (r"(^|\s)[O](?=\d)", r"\1Ø"),
        (r"(?<=\d)\s*[lI]\s*(?=\d)", "1"),
        (r"\s+", " "),
    ]
    for pat, rep in fixes:
        t = re.sub(pat, rep, t)
    return t.strip()


def _split_multi_numbers(text: str) -> list[str]:
    """Split fused OCR like '45 22' or '2X Ø11' into separate tokens."""
    t = (text or "").strip()
    if not t:
        return []
    if re.match(r"^a\s+\d", t, re.IGNORECASE):
        return [t]
    parts = re.findall(
        r"(?:\d+\s*[xX×]\s*)?[ØøΦφ⌀∅]?R?\d+\.?\d*|[±+\-]\d+\.?\d*|\d+\.?\d*",
        t,
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if p.strip()]


def normalize_ocr_item(item: dict) -> dict:
    """Apply OCR normalization layer to a balloon item."""
    out = dict(item or {})
    out = _merge_stacked_tolerance_fields(out)
    fields = ("nominal_value", "tolerance", "others", "raw_ocr", "detected_text")
    for key in fields:
        val = str(out.get(key) or "").strip()
        if not val:
            continue
        val = _recover_symbols(val)
        val = _recover_gdt(val)
        val = _recover_weld_notation(val)
        cls = str(out.get("class_name") or "").lower()
        val = _recover_surface_finish(val, cls)
        if key != "raw_ocr":
            val = _recover_reference_dim(val)
        val = _ocr_corrections(val)
        out[key] = val

    blob = " ".join(str(out.get(k) or "") for k in fields)
    splits = _split_multi_numbers(blob)
    if splits and not out.get("nominal_value"):
        out["nominal_value"] = splits[0]
    if len(splits) > 1 and not out.get("others"):
        out["others"] = " ".join(splits[1:])
    out["ocr_normalized"] = True
    out["ocr_tokens"] = splits
    return out

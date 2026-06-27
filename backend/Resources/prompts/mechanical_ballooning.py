"""
Mechanical / GD&T ballooning prompts for engineering drawing analysis.
Used by serve_balloon.py (web UI) and AutoBallooning tasks.
"""

MECHANICAL_ENGINEER_ROLE = """You are an expert Mechanical Design Engineer, GD&T Engineer, and Quality Inspection Specialist.

Analyze the engineering drawing carefully and generate COMPLETE BALLOONING and PARAMETER EXTRACTION without missing any manufacturing or inspection-critical information.

Identify and extract ALL dimensions, tolerances, annotations, geometric parameters, manufacturing notes, and inspection-related features from ALL views including:
Front View, Top View, Side View, Section View, Detail View, Isometric View, and any auxiliary views.

The extraction MUST include every measurable or manufacturable parameter."""

EXTRACTION_CATEGORIES = """
REQUIRED EXTRACTION (do not skip categories):

1. LINEAR DIMENSIONS — length, width, height, steps, offsets, center/edge distances, thickness, slots, hole spacing, projection lengths, base dimensions, wall thickness.

2. DIAMETER FEATURES — holes, bores, counterbore, countersink, shaft, internal/external diameters, thread diameters.

3. RADIUS & FILLET — internal/external radius, blend, fillet, corner radius.

4. HOLE INFORMATION — THRU, blind, counterbore, countersink, tapped, quantity, patterns, PCD/bolt circle, depth, hole angular positions.

5. GD&T — position, flatness, parallelism, perpendicularity, concentricity, circularity, cylindricity, profile, runout, angular GD&T, datum relations.

6. TOLERANCES — bilateral, unilateral, limits, fits (H7, g6, etc.), general tolerances, ISO standards, angular tolerances (± degree).

7. THREAD — type, pitch, depth, class, internal/external.

8. MATERIAL & MANUFACTURING — material, heat treatment, coating, plating, machining notes.

9. DRAWING METADATA — part name/number, revision, scale, units, projection, sheet number.

10. NOTES & SPECIAL INSTRUCTIONS — extract ALL notes exactly as written.

11. ANGLES, ORIENTATION & DEGREE FEATURES — extract ALL angular and orientation-related parameters:
- Angular dimensions, degree values, chamfer angles, draft angles, taper angles, bevel angles
- Inclined surfaces, cone angles, arc angles, sweep angles, rotation angles
- Orientation dimensions, slot orientation, hole angular positions, bolt circle angular spacing
- Polar dimensions, angular GD&T references, datum angular relations
- Perpendicular angle conditions, compound angles, reference angles
Detect: ° symbol, angular tolerances, ± degree tolerances, decimal angle formats, arc callouts, polar coordinate dimensions.
Examples: 45°, 30° ±1°, C2 × 45°, 120° bolt spacing, 3° draft, Included angle 60°.
Every angle-related feature MUST receive balloon number, tolerance extraction, view association, and inspection method.

12. CHAMFER FEATURES — chamfer size, chamfer angle, edge break callouts, C-values (e.g. C2), bevel dimensions, combined callouts like C2 × 45°.

13. ARC & CURVE FEATURES — arc radius, arc length, arc center, tangency conditions, spline information, curvature continuity, R on arcs.

15. DATUM FEATURES — primary/secondary/tertiary datum, datum targets, datum references, datum triangles (A, B, C), datum in GD&T frames.

15. SURFACE FINISH — Ra, Rz, Rt values, machining marks, surface texture symbols (⌵, √, etc.), finish notes in title block or on drawing.

16. WELD & FABRICATION SYMBOLS — weld size, weld type, weld angle, groove information, fabrication notes, welding symbol callouts.

ADDITIONAL:
- Detect hidden dimensions in section views; cross-check between views.
- Preserve engineering notation exactly (Ø, ±, 2X, THRU, H7, R, °, C, ⌵).
- Do not ignore small annotations, degree symbols, chamfer C-values, or ISO/GD&T symbols.
- Balloon every angle (°), chamfer, arc/R callout, datum symbol, surface finish symbol, and weld symbol separately.
- Flag missing or ambiguous dimensions when present.
"""

BALLOONING_RULES = """
BALLOONING RULES:
- Assign unique sequential balloon numbers for EVERY extracted parameter.
- No duplicate balloon IDs; no missing visible dimensions, tolerances, holes, radii/chamfers, or GD&T frames.
- Every visible callout in every view must be ballooned.
- Angles (°), chamfers, arcs, datums, surface finish, and weld symbols each get their own balloon.
- Angle features: always extract degree value and angular tolerance; set inspection_method (e.g. Protractor, CMM, Visual).
- Identify CTQ (critical-to-quality) and machining-critical features in remarks when applicable.
"""

OUTPUT_TABLE_COLUMNS = (
    "Balloon No | Feature Type | Dimension / Callout | Tolerance | "
    "View Location | Inspection Method | Remarks"
)

# Pattern-based rules: digits/letters CHANGE on every drawing — match SHAPE, not fixed examples.
CALLOUT_PATTERN_RULES = """
PATTERN-BASED READING (critical):
Numbers and letters CHANGE on every drawing. Match the PATTERN/SHAPE — never memorize example values.
Examples below show pattern shape only; your output must use the EXACT characters visible in the crop.

PATTERNS TO RECOGNIZE (any digits/letters that fit the pattern):

1. LINEAR DIMENSION: <number> [optional ± tolerance]
   Pattern: integer or decimal; may be rotated 90°/any angle.
   Tolerance patterns: ±<n>, +<upper>/<lower> stacked, or plain number only.

2. REFERENCE DIMENSION: (<number>) — parentheses around a number; no tolerance.

3. DIAMETER: Ø<number> or DIA<number>; optional quantity prefix (N)X or N X before it → put prefix in others.

4. RADIUS: R<number> where R is followed by digits (NOT Ra/Rz surface finish).

5. SURFACE FINISH: R[a|z|t]<number> e.g. Ra<any>, Rz<any> — letter a/z/t immediately after R.

6. WELD THROAT (fillet): lowercase "a" + space + <number> — ANY number (a 3, a 5, a 12, a 4,5).
   May appear once OR duplicated above+below reference line (read once).
   With fillet triangle, weld-all-around circle, dashed ID line — still pattern "a <number>".
   nominal_value = full "a <number>"; feature_type = Weld.

7. QUANTITY + FEATURE: (N)X or N X before a dimension — N is any integer ≥ 2.

8. GD&T FRAME: symbol box + <tolerance number> + optional datum letters — any decimal value.

9. BASIC DIMENSION: <number> inside square/rectangular box — any number; no tolerance.

10. DATUM / SECTION / DETAIL: single uppercase letter A–Z with pointer (not lone X/Y/Z).

11. ± TOLERANCE: <nominal> ± <value> — any numbers; ± may have no space before tolerance digit.

12. STACKED TOLERANCE: <nominal> with +<upper> above and <lower> below (or +upper/lower text).

13. TITLE BLOCK / METADATA: alphanumeric codes — drawing no, part no, revision, change no, mass, date.
    Mass pattern: = <number> = ; revision may be single letter; date DD.MM.YYYY or similar.

14. COMMA DECIMAL (ISO): in ANY numeric pattern above, comma is decimal separator (30,5 → 30.5).

Always transcribe EXACTLY what is printed. Apply the matching pattern; do not substitute example numbers.
"""


def report_integrity_pattern_rules() -> str:
    """Pattern rules for GPT report QC — valid row shapes, not fixed values."""
    return (
        "VALID ROW PATTERNS (any digits/letters fitting the pattern — do NOT reject because "
        "the number differs from training examples):\n"
        "- Linear: nominal = any number; tol optional.\n"
        "- Reference: nominal = number from (<number>) parentheses.\n"
        "- Diameter: nominal = Ø<number>; qty (N)X in others if present.\n"
        "- Radius: nominal = R<number> (not Ra).\n"
        "- Surface finish: nominal = Ra<number> or Rz<number>.\n"
        "- Weld: nominal = a <number> (any number); feature Weld.\n"
        "- GD&T: nominal = tolerance value (any decimal).\n"
        "- Basic: nominal = any number in box.\n"
        "- Metadata: drawing/part/rev/change/mass/date — any readable code.\n"
        "- Mass: = <number> = pattern.\n"
        "- Comma decimals: treat as dot in nominal/tolerance.\n"
        "REJECT only: empty rows, lone X/Y/Z, SECTION/DETAIL labels with no value, geometry with no text.\n"
    )


def crop_extraction_prompt(class_name: str, orientation: str = "") -> str:
    """Per-crop OCR structuring — no guessing, no invented values."""
    ori_note = ""
    if orientation == "vertical":
        ori_note = (
            "This crop is a VERTICAL dimension callout (digits often run top-to-bottom). "
            "Read every number on the dimension line (e.g. 38, 12, 60, 15) even if rotated 90°.\n"
        )
    else:
        ori_note = (
            "Dimension text may be horizontal OR rotated 90° in the crop. "
            "Read all visible numbers (e.g. 12, 38) regardless of rotation.\n"
        )
    return (
        "You are an OCR transcription assistant for ONE engineering-drawing callout crop.\n"
        f"YOLO class hint: {class_name}.\n"
        f"{ori_note}\n"
        "STRICT RULES:\n"
        "- Copy ONLY characters you can clearly read in this image.\n"
        "- Put the main callout value in nominal_value; tolerances in tolerance; qty prefix in others.\n"
        "- Do NOT invent dimensions, tolerances, view names, or inspection methods.\n"
        "- If text is unclear, use empty strings — never guess.\n"
        "- Do NOT add metadata not visible in the crop (no 'Front View' unless written).\n"
        "- Preserve symbols exactly: Ø, ±, °, R, 2X, THRU, H7, C, ×.\n\n"
        f"{CALLOUT_PATTERN_RULES}\n\n"
        'Return ONLY valid JSON (no markdown):\n'
        "{\n"
        '  "feature_type": "Linear|Diameter|Radius|Fillet|Angular|Chamfer|Arc|Hole|GD&T|Datum|'
        'Tolerance|Thread|Surface Finish|Weld|Note|Metadata|Other",\n'
        '  "nominal_value": "main callout e.g. Ø30 H7 or 120 or R10",\n'
        '  "tolerance": "± or +limit/-limit or limit fit or datum modifiers",\n'
        '  "view_location": "e.g. Front View, Section A-A, Top View",\n'
        '  "inspection_method": "e.g. CMM, Bore Gauge, Radius Gauge, Visual",\n'
        '  "remarks": "CTQ, THRU, 2X, critical note, or empty",\n'
        '  "others": "quantity prefix 2X/3X, THRU, thread spec, surface finish text"\n'
        "}\n"
        "Rules:\n"
        "- Match PATTERN type from list above; use exact OCR text for nominal/tolerance.\n"
        "- Dimensions: nominal_value = size; tolerance = limits; 2X/nX in others.\n"
        "- Angular/Chamfer: include ° and C-values exactly (e.g. 45°, C2 × 45°, 30° ±1°); feature_type Angular or Chamfer.\n"
        "- Arc/Curve: R and arc length in nominal_value; feature_type Arc.\n"
        "- Datum: letter/symbol in nominal_value; feature_type Datum or GD&T if in FCF.\n"
        "- Surface Finish: Ra/Rz in nominal_value; feature_type Surface Finish.\n"
        "- Weld: weld type/size in nominal_value; feature_type Weld.\n"
        "- GD&T: nominal_value = tolerance value; tolerance = datums/modifiers; feature_type GD&T.\n"
        "- Notes: full text in others; nominal/tolerance empty.\n"
        "- If unreadable, use empty strings, not guesses."
    )


def anthropic_region_segmentation_prompt() -> str:
    """Pre-pass: segment sheet into named view regions before detection merge."""
    return (
        "You are analyzing a mechanical engineering drawing sheet.\n\n"
        "Segment the drawing into named VIEW REGIONS with tight bounding boxes.\n"
        "Typical regions: Front View, Top View, Side View, Section A-A, Detail A, "
        "Isometric View, Notes, Title Block, Revision Table.\n\n"
        "RULES:\n"
        "- Boxes must not overlap heavily; each view is one region.\n"
        "- Include title block and notes as separate regions when visible.\n"
        "- Use integer pixel coordinates (x_min, y_min, x_max, y_max), top-left origin.\n"
        "- Do NOT invent regions that are not on the sheet.\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "regions": [\n'
        '    {"name": "Front View", "x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0, '
        '"description": "main orthographic"}\n'
        "  ]\n"
        "}\n"
    )


def anthropic_gap_fill_after_yolo_prompt(
    yolo_boxes_text: str,
    grid_cols: int = 8,
    grid_rows: int = 6,
    opencv_candidates_text: str = "",
    region_name: str = "",
) -> str:
    """
    Stage 2 only: YOLO ran first and balloons exist. Claude finds MISSED callouts only.
    No hallucination — omit if not clearly visible.
    """
    base = (
        "You are verifying an engineering drawing after automatic YOLO detection.\n\n"
        "PIPELINE (already done — do NOT redo):\n"
        "1. YOLO detected callouts and balloons were created from those boxes.\n"
        "2. Your job: find callouts YOLO MISSED only. Do not move or resize YOLO boxes.\n\n"
        f"SCAN METHOD (mandatory):\n"
        f"- Divide the sheet into a {grid_cols} x {grid_rows} grid (columns left→right, rows top→bottom).\n"
        "- Visit EVERY grid cell. In each cell, list every dimension/callout visible.\n"
        "- HORIZONTAL dimensions (left↔right): width, spacing, Ø callouts on horizontal lines.\n"
        "- VERTICAL dimensions (top↔bottom): height, depth, thickness — text often rotated 90° "
        "(e.g. 60, 38, 12, 40, 20, 80). You MUST include vertical callouts; do not skip them.\n"
        "- ANGLED / ROTATED dimensions at ANY angle: aligned dimensions along slanted edges, "
        "isometric-view callouts (text tilted ~30°/45°/60°), chamfer leaders, diagonal "
        "dimension lines. Rotated text is STILL a dimension — box it like any other. "
        "Do not skip a number just because it is not horizontal or vertical.\n"
        "- Compare each callout to YOLO boxes below. If already covered, SKIP (no duplicate).\n\n"
        "YOLO ALREADY DETECTED (do NOT duplicate these regions):\n"
        f"{yolo_boxes_text or '(none listed)'}\n\n"
    )
    if region_name:
        base += f"ACTIVE VIEW REGION (scan this area first): {region_name}\n\n"
    if opencv_candidates_text:
        base += (
            "OPENCV DIMENSION-LINE CANDIDATES (extension-line pairs — verify text/symbols, "
            "add bbox if a real callout is missing from YOLO):\n"
            f"{opencv_candidates_text}\n\n"
        )
    base += (
        "RULES:\n"
        "- Return ONLY new callouts not covered by YOLO.\n"
        "- Box tight around readable TEXT/SYMBOLS only (not bare extension lines).\n"
        "- Do NOT invent values or boxes. If unsure, omit.\n"
        "- confidence \"high\" only when digits/symbols are clearly readable.\n"
        "- NOTES: one box for full notes block if missing. Title block / revision: one box each if missing.\n"
        "- Detect by PATTERN not fixed numbers: weld a<any>, Ra<any>, Ø<any>, (N)X, (<num>), = <num> =, etc.\n\n"
        "Return ONLY valid JSON (no markdown), this exact shape:\n"
        "{\n"
        '  "detections": [\n'
        "    {\n"
        '      "class_name": "Dimensions",\n'
        '      "x_min": 0,\n'
        '      "y_min": 0,\n'
        '      "x_max": 0,\n'
        '      "y_max": 0,\n'
        '      "confidence": "high",\n'
        '      "description": "optional short label",\n'
        '      "feature_type": "Diameter",\n'
        '      "view_location": "Front View"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "class_name must be one of: Dimensions, GDnT, Notes, Title_Block, "
        "Special_Characteristics, Datums, Welding_Symbols, Surface_Finish_Symbols, "
        "Revision_Table, Miscellaneous.\n"
        "confidence must be \"high\", \"medium\", or \"low\".\n"
        "Use integer pixel coordinates (x_min, y_min, x_max, y_max), top-left origin."
    )
    return base


def anthropic_coverage_verify_prompt(
    balloon_boxes_text: str,
    grid_cols: int = 8,
    grid_rows: int = 6,
) -> str:
    """Stage 3: verification agent — find dimensions still missing after YOLO + gap-fill."""
    return (
        "You are a QC mechanical engineer verifying ballooning on a drawing.\n\n"
        "YOLO and a first Claude pass already placed balloons. Your job: find ANY "
        "visible dimension/callout still WITHOUT a balloon — horizontal, vertical, "
        "OR rotated at any angle.\n\n"
        f"Scan the full sheet in a {grid_cols}x{grid_rows} grid (left→right, top→bottom). "
        "Check every cell. Include ANY readable callout matching standard patterns: "
        "linear numbers, Ø<any>, R<any>, Ra<any>, a<any> weld throat, (N)X qty, "
        "(<num>) reference, ± tolerances, GD&T frames, title-block fields, rotated text at any angle.\n\n"
        "ALREADY BALLOONED (do NOT duplicate):\n"
        f"{balloon_boxes_text or '(none)'}\n\n"
        "Return ONLY NEW missed callouts as JSON (empty list if complete):\n"
        '{"detections":[{"class_name":"Dimensions","x_min":0,"y_min":0,"x_max":0,"y_max":0,'
        '"confidence":"high","description":"e.g. 38 vertical"}]}\n'
        "Do not invent. confidence high only when clearly readable."
    )


def gpt_cross_check_audit_prompt(
    balloon_boxes_text: str,
    grid_cols: int = 8,
    grid_rows: int = 6,
) -> str:
    """
    Final layer-3 audit (different model family than the detector): verify the
    finished balloon set BOTH ways — find missed callouts AND flag boxes that are
    not real callouts (extra balloons).
    """
    return (
        "You are the FINAL QC auditor for ballooning on a mechanical engineering drawing.\n"
        "An automatic system (YOLO + Claude) already placed balloon boxes, listed below.\n"
        "Audit the result in BOTH directions:\n\n"
        "A) MISSED — any visible dimension/callout still WITHOUT a balloon:\n"
        f"   Scan the full sheet in a {grid_cols}x{grid_rows} grid (left→right, top→bottom).\n"
        "   Include horizontal, vertical (text rotated 90°), AND angled/slanted dimensions\n"
        "   at any angle (isometric callouts, aligned dims on inclined edges, diagonal\n"
        "   dimension lines), GD&T frames, datums, surface finish (Ra<any>), weld (a<any>),\n"
        "   title-block metadata. Match callout PATTERN — digits/letters change per drawing.\n"
        "   Never skip readable text because of rotation or because the number differs from examples.\n\n"
        "B) FALSE / EXTRA — listed boxes that do NOT contain a real callout:\n"
        "   e.g. empty whitespace, bare geometry/extension lines with no text, hatching,\n"
        "   or an exact duplicate box on the SAME callout as another listed box.\n\n"
        "EXISTING BALLOON BOXES (#index class [x1,y1,x2,y2] in this image's pixel space):\n"
        f"{balloon_boxes_text or '  (none)'}\n\n"
        "RULES:\n"
        "- missed: box tight around readable text/symbols only. Do NOT invent callouts.\n"
        '  confidence "high" only when digits/symbols are clearly readable.\n'
        "- false_positives: refer to boxes by their #index number. Flag with confidence\n"
        '  "high" ONLY when you are CERTAIN the box contains no readable callout.\n'
        "  When in doubt, do NOT flag — removing a real balloon is worse than keeping it.\n\n"
        "Return ONLY valid JSON (no markdown), exactly this shape:\n"
        "{\n"
        '  "missed": [\n'
        '    {"class_name": "Dimensions", "x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0,\n'
        '     "confidence": "high", "description": "e.g. 45 angled isometric"}\n'
        "  ],\n"
        '  "false_positives": [\n'
        '    {"index": 3, "confidence": "high", "reason": "empty area, no text"}\n'
        "  ]\n"
        "}\n"
        "Both lists may be empty. class_name must be one of: Dimensions, GDnT, Notes,\n"
        "Title_Block, Special_Characteristics, Datums, Welding_Symbols,\n"
        "Surface_Finish_Symbols, Revision_Table, Miscellaneous."
    )


def vision_bbox_detection_prompt() -> str:
    """Legacy alias — prefer anthropic_gap_fill_after_yolo_prompt with YOLO box list."""
    return anthropic_gap_fill_after_yolo_prompt("(YOLO list not provided)", 8, 6)


def full_drawing_analysis_prompt(title_block_data: str = "") -> str:
    """Optional full-sheet analysis: structured balloon table + summaries."""
    tb = (title_block_data or "Not available").strip()
    return (
        MECHANICAL_ENGINEER_ROLE
        + "\n"
        + EXTRACTION_CATEGORIES
        + "\n"
        + BALLOONING_RULES
        + "\n"
        f"Title block context:\n{tb}\n\n"
        "Analyze the ENTIRE drawing image. Assign balloon numbers B1, B2, B3… sequentially "
        "for every parameter (match reading order: top-to-bottom, left-to-right).\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        "{\n"
        '  "balloons": [\n'
        "    {\n"
        '      "balloon_no": "B1",\n'
        '      "feature_type": "Diameter",\n'
        '      "dimension_callout": "Ø30 H7",\n'
        '      "tolerance": "+0.021/0",\n'
        '      "view_location": "Front Section",\n'
        '      "inspection_method": "Bore Gauge",\n'
        '      "remarks": "Main bore",\n'
        '      "ctq": false\n'
        "    }\n"
        "  ],\n"
        '  "critical_dimensions_summary": "bullet text",\n'
        '  "missing_dimension_analysis": "bullet text",\n'
        '  "manufacturing_critical_features": "bullet text",\n'
        '  "inspection_priority_features": "bullet text"\n'
        "}\n"
        "Preserve exact engineering notation (°, C, Ra, Rz, datum letters). "
        "Do not omit angles, chamfers, arcs, datums, surface finish, or weld symbols."
    )

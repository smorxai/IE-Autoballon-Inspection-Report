/**
 * Shared parsing for balloon nominal / tolerance (Detected details + Inspection report).
 */
(function (global) {
  function parseDetectedText(raw) {
    const text = (raw || "").trim();
    if (!text) return { nominal: "", tolLow: "", tolHigh: "" };

    let s = text.replace(/^[ØøΦφ]\s*/i, "").replace(/\s+/g, " ");

    let m = s.match(/^([+-]?\d+\.?\d*)\s*[±]\s*(\d+\.?\d*)/);
    if (m) {
      const tol = parseFloat(m[2]);
      return { nominal: m[1], tolLow: String(-tol), tolHigh: String(tol) };
    }

    m = s.match(/^([+-]?\d+\.?\d*)\s*([+-]\d+\.?\d*)\s*\/\s*([+-]\d+\.?\d*)/);
    if (m) {
      return { nominal: m[1], tolLow: m[3], tolHigh: m[2].replace(/^\+/, "") };
    }

    m = s.match(/^([+-]?\d+\.?\d*)\s*\+\s*(\d+\.?\d*)\s*\/\s*-?\s*(\d+\.?\d*)/);
    if (m) {
      return { nominal: m[1], tolLow: "-" + m[3], tolHigh: m[2] };
    }

    m = s.match(/^([+-]?\d+\.?\d*)\s*([+-]\d+\.?\d*)\s+([+-]\d+\.?\d*)/);
    if (m) {
      return { nominal: m[1], tolLow: m[3], tolHigh: m[2].replace(/^\+/, "") };
    }

    m = s.match(/^([+-]?\d+\.?\d*)\s*$/);
    if (m) return { nominal: m[1], tolLow: "", tolHigh: "" };

    m = s.match(/([+-]?\d+\.?\d*)/);
    if (m) return { nominal: m[1], tolLow: "", tolHigh: "" };

    return { nominal: text, tolLow: "", tolHigh: "" };
  }

  function buildDetectedText(nominal, tolerance) {
    const n = (nominal || "").trim();
    const t = (tolerance || "").trim();
    if (n && t) {
      if (/^[±+-]/.test(t)) return n + " " + t;
      return n + " ± " + t;
    }
    return n || t;
  }

  function enrichBalloonItem(it) {
    if (!it) return it;
    let nom = it.nominal_value != null ? String(it.nominal_value).trim() : "";
    let tol = it.tolerance != null ? String(it.tolerance).trim() : "";
    const others = it.others != null ? String(it.others).trim() : "";

    if (!nom && !tol) {
      const src = others || (it.detected_text || "").trim();
      if (src) {
        const p = parseDetectedText(src);
        nom = p.nominal || "";
        if (p.tolLow !== "" || p.tolHigh !== "") {
          const lo = parseFloat(p.tolLow);
          const hi = parseFloat(p.tolHigh);
          if (Number.isFinite(lo) && Number.isFinite(hi) && Math.abs(lo + hi) < 1e-6) {
            tol = "±" + String(hi).replace(/^\+/, "");
          } else if (p.tolHigh) {
            tol = "+" + p.tolHigh + (p.tolLow ? "/" + p.tolLow : "");
          }
        }
      }
    }

    it.nominal_value = nom;
    it.tolerance = tol;
    it.detected_text = buildDetectedText(nom, tol);
    return it;
  }

  function parseBalloonItem(it) {
    enrichBalloonItem(it);
    const nom = (it.nominal_value || "").trim();
    const tol = (it.tolerance || "").trim();
    if (nom || tol) return parseDetectedText(buildDetectedText(nom, tol));
    return parseDetectedText(it.detected_text || "");
  }

  /**
   * Balloon must have at least one of: crop image, nominal value, or tolerance.
   * Otherwise it is hidden on drawing, table, and inspection report.
   */
  function balloonHasExtractedData(it) {
    if (!it) return false;
    var nom = String(it.nominal_value != null ? it.nominal_value : "").trim();
    var tol = String(it.tolerance != null ? it.tolerance : "").trim();
    var crop = String(it.crop_preview_base64 || it.crop_save_base64 || "").trim();
    if (crop.length > 40) return true;
    if (nom && nom.toLowerCase() !== "empty") return true;
    if (tol && tol.toLowerCase() !== "empty") return true;
    return false;
  }

  function findItemForDetectionIndex(det, idx) {
    var items = (det && det.balloon_items) || [];
    var i;
    for (i = 0; i < items.length; i++) {
      if (detectionIndexForItem(det, items[i]) === idx) return items[i];
    }
    return null;
  }

  function hideIncompleteBalloons(det) {
    if (!det) return det;
    ensureDrawingAnnotations(det);
    var items = det.balloon_items || [];
    var dets = det.detections || [];
    var anns = det.drawing_annotations || [];
    var kept = [];
    var keptDi = {};
    var i;
    for (i = 0; i < items.length; i++) {
      if (!balloonHasExtractedData(items[i])) continue;
      kept.push(items[i]);
      var di = detectionIndexForItem(det, items[i]);
      if (di != null) keptDi[di] = true;
    }
    det.balloon_items = kept;
    var hidden = 0;
    for (i = 0; i < dets.length; i++) {
      if (!keptDi[i]) {
        hidden += 1;
        if (i < anns.length) {
          anns[i] = Object.assign({}, anns[i], { canvas_skip: true });
        }
      }
    }
    det.drawing_annotations = anns;
    det.balloons_hidden_no_data = hidden;
    return det;
  }

  function balloonItemText(it) {
    if (!it) return "";
    return [
      it.nominal_value,
      it.tolerance,
      it.others,
      it.detected_text,
      it.multiplier_notation,
      it.class_name,
      it.raw_ocr,
    ]
      .filter(function (p) {
        return p != null && String(p).trim();
      })
      .join(" ");
  }

  /** e.g. "8X", "4 X", "2×" → 8 */
  function parseMultiplierCount(text) {
    const blob = (text || "").trim();
    if (!blob) return 0;
    const m = blob.match(/(\d+)\s*[xX×]/);
    if (!m) return 0;
    const n = parseInt(m[1], 10);
    return Number.isFinite(n) && n >= 2 ? n : 0;
  }

  function multiplierCountFromItem(it) {
    if (!it) return 0;
    const stored = parseInt(it.multiplier_count, 10);
    if (Number.isFinite(stored) && stored >= 2) return stored;
    const textFields = [
      it.others,
      it.nominal_value,
      it.tolerance,
      it.raw_ocr,
      it.detected_text,
      it.multiplier_notation,
    ]
      .filter(function (p) {
        return p != null && String(p).trim();
      })
      .join(" ");
    const fromText = parseMultiplierCount(textFields);
    if (fromText >= 2) return fromText;
    return 0;
  }

  function isSubBalloonItem(it) {
    if (!it) return false;
    if (it.is_sub_balloon) return true;
    const bn = String(it.balloon_number != null ? it.balloon_number : "");
    return /\.\d+$/.test(bn);
  }

  function parentBalloonNumber(it) {
    if (!it) return "";
    if (it.parent_balloon_number != null && String(it.parent_balloon_number).trim() !== "") {
      return String(it.parent_balloon_number);
    }
    const bn = String(it.balloon_number != null ? it.balloon_number : "");
    const dot = bn.indexOf(".");
    return dot > 0 ? bn.slice(0, dot) : bn;
  }

  /** Whole number for red circle on drawing only (15 not 15.1). Table keeps sub-rows. */
  /**
   * Tight balloon: place circle just outside the detection box with a clear leader target.
   * Returns image-space { ax, ay, px, py } (anchor on box edge, preferred balloon center).
   */
  function tightBalloonPlacement(bb, gapPx, orientation, balloonSide) {
    if (!bb || bb.length < 4) {
      return { ax: 0, ay: 0, px: 0, py: 0, side: "below" };
    }
    const x1 = bb[0];
    const y1 = bb[1];
    const x2 = bb[2];
    const y2 = bb[3];
    const w = x2 - x1;
    const h = y2 - y1;
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    const gap =
      gapPx != null ? gapPx : Math.max(16, Math.min(w, h) * 0.18, Math.max(w, h) * 0.08);
    const ori =
      orientation ||
      (h >= w * 1.15 ? "vertical" : w >= h * 1.15 ? "horizontal" : "square");
    const side = (balloonSide || "").toLowerCase();
    if (ori === "vertical" || (ori !== "horizontal" && h >= w * 1.15)) {
      if (side === "left") {
        return { ax: x1, ay: cy, px: x1 - gap, py: cy, side: "left" };
      }
      return { ax: x2, ay: cy, px: x2 + gap, py: cy, side: "right" };
    }
    if (ori === "horizontal" || w >= h * 1.15) {
      if (side === "above") {
        return { ax: cx, ay: y1, px: cx, py: y1 - gap, side: "above" };
      }
      return { ax: cx, ay: y2, px: cx, py: y2 + gap, side: "below" };
    }
    return { ax: cx, ay: y2, px: cx, py: y2 + gap, side: "below" };
  }

  function tightTextPosForBbox(bb) {
    const t = tightBalloonPlacement(bb, null);
    return [t.px, t.py];
  }

  function wholeBalloonNumber(bn) {
    const s = String(bn != null ? bn : "").trim();
    if (!s) return "";
    const m = s.match(/^(\d+)\.\d+$/);
    return m ? m[1] : s;
  }

  function drawingCanvasLabel(ann) {
    if (!ann) return "";
    if (ann.display_id != null && String(ann.display_id).trim() !== "") {
      return wholeBalloonNumber(ann.display_id);
    }
    if (ann.parent_balloon_number != null && String(ann.parent_balloon_number).trim() !== "") {
      return String(ann.parent_balloon_number);
    }
    return wholeBalloonNumber(ann.id != null ? ann.id : "");
  }

  /** Canvas label must match Detected details balloon_number for the same detection_index. */
  function canvasLabelForDetection(det, di) {
    const items = (det && det.balloon_items) || [];
    let parentLabel = "";
    let subParent = "";
    for (let j = 0; j < items.length; j++) {
      const it = items[j];
      if (detectionIndexForItem(det, it) !== di) continue;
      if (isSubBalloonItem(it)) {
        if (!subParent) subParent = String(parentBalloonNumber(it) || "");
      } else {
        parentLabel = wholeBalloonNumber(it.balloon_number);
      }
    }
    if (parentLabel) return parentLabel;
    if (subParent) return subParent;
    const ann = (det.drawing_annotations || [])[di];
    const fromAnn = drawingCanvasLabel(ann);
    if (fromAnn) return fromAnn;
    return String(di + 1);
  }

  function findBalloonItem(det, it) {
    if (!det || !it) return null;
    const bn = String(it.balloon_number != null ? it.balloon_number : "");
    const items = det.balloon_items || [];
    for (let i = 0; i < items.length; i++) {
      if (String(items[i].balloon_number) === bn) return items[i];
    }
    return null;
  }

  /**
   * One canvas balloon per visible detection, keyed by detection_index (same as Detected details).
   */
  function detectionEntriesForCanvas(det) {
    if (!det) return [];
    ensureDrawingAnnotations(det);
    const dets = det.detections || [];
    const anns = det.drawing_annotations || [];
    const out = [];
    for (let i = 0; i < dets.length; i++) {
      const ann = anns[i] || {};
      if (ann.canvas_skip || ann.report_only || ann.is_parent_balloon) continue;
      const rowItem = findItemForDetectionIndex(det, i);
      if (rowItem && !balloonHasExtractedData(rowItem)) continue;
      const d = dets[i] || {};
      const bb =
        d.bbox && d.bbox.length >= 4
          ? d.bbox.slice()
          : ann.BBox && ann.BBox.length >= 4
            ? ann.BBox.slice()
            : null;
      if (!bb) continue;
      out.push({
        detectionIndex: i,
        bbox: bb,
        label: canvasLabelForDetection(det, i),
        ann: ann,
        dimension_orientation: d.dimension_orientation || ann.dimension_orientation,
        balloon_side: d.balloon_side || ann.balloon_side,
      });
    }
    return out;
  }

  function annotationsForCanvas(det) {
    var dets = det.detections || [];
    var anns = det.drawing_annotations || [];
    if (dets.length && anns.length !== dets.length && ensureDrawingAnnotations) {
      ensureDrawingAnnotations(det);
      anns = det.drawing_annotations || [];
    }
    return anns.filter(function (a) {
      return a && !a.canvas_skip && !a.report_only && !a.is_parent_balloon;
    });
  }

  function isAlreadyMultiplierExpanded(det) {
    const items = (det && det.balloon_items) || [];
    return items.some(function (it) {
      return isSubBalloonItem(it);
    });
  }

  function multiplierNotation(text, count) {
    const m = (text || "").match(/(\d+)\s*[xX×]/);
    if (m) return m[0].replace(/\s+/g, "");
    return count >= 2 ? count + "X" : "";
  }

  /** Table-only: remove prior sub rows before re-expand. */
  function stripSubBalloons(det) {
    const items = det.balloon_items || [];
    const keepIdx = [];
    for (let i = 0; i < items.length; i++) {
      if (!isSubBalloonItem(items[i]) && !items[i].is_parent_balloon) keepIdx.push(i);
    }
    det.balloon_items = keepIdx.map(function (i) {
      return items[i];
    });
    return det;
  }

  function ensureMultiplierInItem(it) {
    if (!it || multiplierCountFromItem(it) >= 2) return;
    const blob = balloonItemText(it);
    const m = blob.match(/(\d+)\s*[xX×]/);
    if (!m) return;
    const prefix = m[0].replace(/\s+/g, "");
    const others = (it.others || "").trim();
    const compact = others.replace(/\s+/g, "").toLowerCase();
    if (prefix.toLowerCase() !== compact && compact.indexOf(prefix.toLowerCase()) < 0) {
      it.others = (prefix + (others ? " " + others : "")).trim();
    }
  }

  /**
   * Hide parent rows in Detected details only (15.1, 15.2 — not 15).
   * Does not change drawing_annotations (drawing keeps one balloon per detection).
   */
  function pruneParentBalloonsWithSubs(det) {
    if (!det || !det.balloon_items || !det.balloon_items.length) return det;
    const items = det.balloon_items || [];
    const basesWithSubs = new Set();
    items.forEach(function (it) {
      if (!isSubBalloonItem(it)) return;
      const p = parentBalloonNumber(it);
      if (p) basesWithSubs.add(p);
    });
    if (!basesWithSubs.size) return det;

    det.balloon_items = items.filter(function (it) {
      if (isSubBalloonItem(it)) return true;
      if (it.is_parent_balloon) return false;
      const bn = String(it.balloon_number != null ? it.balloon_number : "");
      if (basesWithSubs.has(bn)) return false;
      if (multiplierCountFromItem(it) >= 2) return false;
      return true;
    });
    return det;
  }

  function bboxForBalloonRow(det, i, it) {
    if (it && it.bbox_pixels && it.bbox_pixels.length >= 4) return it.bbox_pixels;
    const anns = det.drawing_annotations || [];
    const dets = det.detections || [];
    const a = anns[i];
    if (a && a.BBox && a.BBox.length >= 4) return a.BBox;
    if (a && a.bbox && a.bbox.length >= 4) return a.bbox;
    if (dets[i] && dets[i].bbox && dets[i].bbox.length >= 4) return dets[i].bbox;
    return null;
  }

  function bboxOverlap(a, b) {
    if (!a || !b || a.length < 4 || b.length < 4) return 0;
    const x1 = Math.max(a[0], b[0]);
    const y1 = Math.max(a[1], b[1]);
    const x2 = Math.min(a[2], b[2]);
    const y2 = Math.min(a[3], b[3]);
    if (x2 <= x1 || y2 <= y1) return 0;
    const inter = (x2 - x1) * (y2 - y1);
    const areaA = Math.max(1, (a[2] - a[0]) * (a[3] - a[1]));
    const areaB = Math.max(1, (b[2] - b[0]) * (b[3] - b[1]));
    return inter / Math.min(areaA, areaB);
  }

  /** Same callout split into multiple YOLO boxes (side-by-side, same band on drawing). */
  function bboxNearDuplicate(primaryBb, thisBb) {
    if (!primaryBb || !thisBb || primaryBb.length < 4 || thisBb.length < 4) return false;
    if (bboxOverlap(primaryBb, thisBb) >= 0.15) return true;
    const yOverlap =
      Math.min(primaryBb[3], thisBb[3]) - Math.max(primaryBb[1], thisBb[1]);
    const spanY = Math.max(
      primaryBb[3] - primaryBb[1],
      thisBb[3] - thisBb[1],
      12
    );
    if (yOverlap < spanY * 0.35) return false;
    const span = Math.max(
      primaryBb[2] - primaryBb[0],
      primaryBb[3] - primaryBb[1],
      thisBb[2] - thisBb[0],
      thisBb[3] - thisBb[1],
      48
    );
    const pcx = (primaryBb[0] + primaryBb[2]) / 2;
    const pcy = (primaryBb[1] + primaryBb[3]) / 2;
    const tcx = (thisBb[0] + thisBb[2]) / 2;
    const tcy = (thisBb[1] + thisBb[3]) / 2;
    return Math.hypot(pcx - tcx, pcy - tcy) < span * 2.5;
  }

  /** Hide only duplicate YOLO slot on same nX callout (heavy overlap), not nearby dimensions. */
  function bboxNearMultiplierDuplicate(primaryBb, thisBb) {
    if (!primaryBb || !thisBb || primaryBb.length < 4 || thisBb.length < 4) return false;
    return bboxOverlap(primaryBb, thisBb) >= 0.72;
  }

  function detectionIndexForItem(det, it) {
    const dets = det.detections || [];
    if (it.detection_index != null) return it.detection_index;
    const bp = it.bbox_pixels;
    if (!bp || bp.length < 4) return null;
    for (let i = 0; i < dets.length; i++) {
      const bb = dets[i] && dets[i].bbox;
      if (bb && bb.length >= 4 && bb[0] === bp[0] && bb[1] === bp[1] && bb[2] === bp[2] && bb[3] === bp[3]) {
        return i;
      }
    }
    return null;
  }

  function itemAtDetectionIndex(det, di) {
    const items = det.balloon_items || [];
    for (let j = 0; j < items.length; j++) {
      if (detectionIndexForItem(det, items[j]) === di) return items[j];
    }
    return items[di] || null;
  }

  function multiplierPrimaryDetectionIndices(det) {
    const items = det.balloon_items || [];
    const primaries = new Set();
    items.forEach(function (it) {
      if (!isSubBalloonItem(it)) return;
      const di = detectionIndexForItem(det, it);
      if (di != null) primaries.add(di);
    });
    const n = (det.detections || []).length;
    for (let i = 0; i < n; i++) {
      const it = itemAtDetectionIndex(det, i);
      if (it && multiplierCountFromItem(it) >= 2) primaries.add(i);
    }
    return primaries;
  }

  /**
   * Drop extra YOLO detection slots beside an nX callout so only one drawing balloon (e.g. 15, not 16).
   */
  function removeDuplicateYoloDetectionsNearMultiplier(det) {
    if (!det) return det;
    const dets = det.detections || [];
    if (dets.length < 2) return det;
    ensureDrawingAnnotations(det);
    const primaries = multiplierPrimaryDetectionIndices(det);
    if (!primaries.size) return det;

    const toRemove = new Set();
    primaries.forEach(function (primaryDi) {
      const primaryBb = bboxForBalloonRow(det, primaryDi, itemAtDetectionIndex(det, primaryDi));
      if (!primaryBb) return;
      for (let j = 0; j < dets.length; j++) {
        if (j === primaryDi || primaries.has(j) || toRemove.has(j)) continue;
        const thisBb = bboxForBalloonRow(det, j, itemAtDetectionIndex(det, j));
        if (thisBb && bboxNearMultiplierDuplicate(primaryBb, thisBb)) toRemove.add(j);
      }
    });
    if (!toRemove.size) return det;

    const mapOldToNew = {};
    const newDets = [];
    const newAnns = [];
    const anns = det.drawing_annotations || [];
    const oldDets = dets;
    for (let i = 0; i < dets.length; i++) {
      if (toRemove.has(i)) continue;
      mapOldToNew[i] = newDets.length;
      newDets.push(dets[i]);
      if (anns[i]) newAnns.push(anns[i]);
    }
    det.detections = newDets;
    det.drawing_annotations = newAnns;
    det.count = newDets.length;

    const items = det.balloon_items || [];
    det.balloon_items = items
      .filter(function (it) {
        const di = detectionIndexForItem(det, it);
        return di == null || !toRemove.has(di);
      })
      .map(function (it) {
        const di = detectionIndexForItem(det, it);
        if (di == null || mapOldToNew[di] == null) return it;
        const copy = Object.assign({}, it);
        copy.detection_index = mapOldToNew[di];
        if (copy.bbox_pixels && oldDets[di] && oldDets[di].bbox) {
          copy.bbox_pixels = oldDets[di].bbox.slice();
        }
        return copy;
      });
    delete det.canvas_balloon_annotations;
    return det;
  }

  /** Drop extra table rows from duplicate YOLO boxes on one nX callout. */
  function pruneOverlappingDuplicateDetections(det) {
    if (!det || !det.balloon_items) return det;
    const dets = det.detections || [];
    const items = det.balloon_items || [];

    const primaryDetByParent = {};
    items.forEach(function (it) {
      if (!isSubBalloonItem(it)) return;
      const p = parentBalloonNumber(it);
      const di = detectionIndexForItem(det, it);
      if (!p || di == null) return;
      if (primaryDetByParent[p] == null || di < primaryDetByParent[p]) {
        primaryDetByParent[p] = di;
      }
    });

    if (!Object.keys(primaryDetByParent).length) return det;

    det.balloon_items = items.filter(function (it) {
      if (isSubBalloonItem(it)) return true;
      const di = detectionIndexForItem(det, it);
      if (di == null) return true;
      const thisBb = bboxForBalloonRow(det, di, it);
      if (!thisBb) return true;
      let keep = true;
      Object.keys(primaryDetByParent).forEach(function (p) {
        const primaryDi = primaryDetByParent[p];
        if (di === primaryDi) {
          keep = false;
          return;
        }
        const primaryBb = bboxForBalloonRow(det, primaryDi, itemAtDetectionIndex(det, primaryDi));
        if (primaryBb && bboxNearMultiplierDuplicate(primaryBb, thisBb)) keep = false;
      });
      return keep;
    });
    return det;
  }

  function ensureDrawingAnnotations(det) {
    const dets = det.detections || [];
    let anns = det.drawing_annotations || [];
    if (!dets.length) return;
    if (anns.length === dets.length) return;
    anns = dets.map(function (d, i) {
      const bb = (d && d.bbox) || [];
      return {
        id: i + 1,
        AnnotationType: (d && d.class_name) || "Dimensions",
        BBox: bb.length >= 4 ? bb.slice() : [],
        TextPos: bb.length >= 4 ? tightTextPosForBbox(bb) : [],
      };
    });
    det.drawing_annotations = anns;
  }

  /** Fix drawing ann id = whole number (15) when table has 15.1 / 15.2. */
  function repairMultiplierDrawingAnnotations(det) {
    if (!det) return det;
    ensureDrawingAnnotations(det);
    const dets = det.detections || [];
    const items = det.balloon_items || [];
    if (!dets.length) return det;

    const primaryDetByParent = {};
    items.forEach(function (it) {
      if (!isSubBalloonItem(it)) return;
      const p = parentBalloonNumber(it);
      const di = detectionIndexForItem(det, it);
      if (!p || di == null) return;
      if (primaryDetByParent[p] == null || di < primaryDetByParent[p]) {
        primaryDetByParent[p] = di;
      }
    });

    const newAnns = [];
    const preserveLegacyPos = det.balloon_placement === "legacy";
    for (let i = 0; i < dets.length; i++) {
      const d = dets[i];
      const bb = (d && d.bbox) || [];
      const old = (det.drawing_annotations || [])[i] || {};
      const ann = Object.assign({}, old);
      delete ann.draw_suppress;
      delete ann.report_only;
      delete ann.is_parent_balloon;

      let pid = ann.id != null ? ann.id : i + 1;
      let canvasSkip = false;
      const thisBb = bboxForBalloonRow(det, i, itemAtDetectionIndex(det, i));
      const parentKeys = Object.keys(primaryDetByParent);
      for (let pi = 0; pi < parentKeys.length; pi++) {
        const p = parentKeys[pi];
        const primaryDi = primaryDetByParent[p];
        if (i === primaryDi) {
          pid = p;
          break;
        }
        const primaryBb = bboxForBalloonRow(det, primaryDi, itemAtDetectionIndex(det, primaryDi));
        if (primaryBb && thisBb && bboxNearMultiplierDuplicate(primaryBb, thisBb)) {
          canvasSkip = true;
          break;
        }
      }

      ann.id = pid;
      ann.display_id = drawingCanvasLabel({ id: pid, display_id: pid });
      ann.canvas_skip = canvasSkip;
      if (bb.length >= 4) {
        ann.AnnotationType = (d && d.class_name) || ann.AnnotationType || "Dimensions";
        ann.BBox = bb.slice();
        var keepLegacy = preserveLegacyPos && ann.TextPos && ann.TextPos.length >= 2;
        if (!keepLegacy) {
          const pl = tightBalloonPlacement(
            bb,
            null,
            (d && d.dimension_orientation) || ann.dimension_orientation,
            (d && d.balloon_side) || ann.balloon_side
          );
          ann.TextPos = [pl.px, pl.py];
        }
        if (d && d.dimension_orientation) ann.dimension_orientation = d.dimension_orientation;
        if (d && d.balloon_side) ann.balloon_side = d.balloon_side;
      }
      newAnns.push(ann);
    }
    det.drawing_annotations = newAnns;
    delete det.canvas_balloon_annotations;
    return det;
  }

  /**
   * nX: split balloon_items only (15.1, 15.2 in table).
   * drawing_annotations stay 1:1 with detections — balloon 15 on drawing.
   */
  /**
   * Ensure Detected details / Inspection report list every detection balloon number.
   */
  function syncBalloonItemsFromDetections(det) {
    if (!det) return det;
    const dets = det.detections || [];
    if (!dets.length) return det;
    ensureDrawingAnnotations(det);
    const anns = det.drawing_annotations || [];
    const items = det.balloon_items || [];
    const byDi = {};

    items.forEach(function (it) {
      let di = detectionIndexForItem(det, it);
      if (di == null) {
        const parent = parentBalloonNumber(it) || String(it.balloon_number || "");
        for (let i = 0; i < anns.length; i++) {
          const lid = String(drawingCanvasLabel(anns[i]) || anns[i].id || "");
          if (lid === String(parent)) {
            di = i;
            break;
          }
        }
      }
      if (di == null) return;
      if (!byDi[di]) byDi[di] = [];
      byDi[di].push(it);
    });

    const out = [];
    for (let i = 0; i < dets.length; i++) {
      const group = byDi[i];
      if (group && group.length) {
        group.sort(function (a, b) {
          const sa = isSubBalloonItem(a);
          const sb = isSubBalloonItem(b);
          if (sa !== sb) return sa ? 1 : -1;
          return String(a.balloon_number).localeCompare(String(b.balloon_number), undefined, {
            numeric: true,
          });
        });
        group.forEach(function (it) {
          const row = Object.assign({}, it);
          row.detection_index = i;
          const db = (dets[i] || {}).bbox;
          if (db && db.length >= 4) row.bbox_pixels = db.slice();
          if (!isSubBalloonItem(row)) {
            const lid = canvasLabelForDetection(det, i);
            if (lid) row.balloon_number = lid;
          }
          enrichBalloonItem(row);
          out.push(row);
        });
        continue;
      }
      const d = dets[i] || {};
      const ann = anns[i] || {};
      const bn = drawingCanvasLabel(ann) || String(ann.id != null ? ann.id : i + 1);
      const bb = d.bbox && d.bbox.length >= 4 ? d.bbox.slice() : [];
      out.push(
        enrichBalloonItem({
          balloon_number: bn,
          detection_index: i,
          class_name: d.class_name || "",
          confidence: d.confidence != null ? d.confidence : "",
          nominal_value: "",
          tolerance: "",
          others: "",
          detected_text: "",
          bbox_pixels: bb,
        })
      );
    }
    det.balloon_items = out;
    return det;
  }

  /** Detection indices that have a visible balloon on the drawing canvas. */
  function visibleDetectionIndexSet(det) {
    const set = {};
    detectionEntriesForCanvas(det).forEach(function (e) {
      if (e.detectionIndex != null) set[e.detectionIndex] = true;
    });
    return set;
  }

  /** Top→bottom, then left→right (same as server tblr reorder). */
  function sortBalloonItemsTblr(items) {
    return (items || []).slice().sort(function (a, b) {
      const bbA = a.bbox_pixels || [];
      const bbB = b.bbox_pixels || [];
      if (bbA.length >= 4 && bbB.length >= 4) {
        const yA = Number(bbA[1]);
        const yB = Number(bbB[1]);
        if (yA !== yB) return yA - yB;
        return Number(bbA[0]) - Number(bbB[0]);
      }
      const na = parseInt(a.balloon_number, 10);
      const nb = parseInt(b.balloon_number, 10);
      if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
      return String(a.balloon_number || "").localeCompare(String(b.balloon_number || ""), undefined, {
        numeric: true,
      });
    });
  }

  /** Table + confirm UI: one row per visible balloon (not every raw YOLO detection). */
  function itemsForTable(det) {
    if (!det) return [];
    const dets = det.detections || [];
    if (!dets.length && det.balloon_items && det.balloon_items.length) {
      return sortBalloonItemsTblr(
        (det.balloon_items || []).filter(function (it) {
          return (
            !isSubBalloonItem(it) && !it.is_parent_balloon && balloonHasExtractedData(it)
          );
        })
      );
    }
    syncBalloonItemsFromDetections(det);
    const vis = visibleDetectionIndexSet(det);
    return sortBalloonItemsTblr(
      (det.balloon_items || []).filter(function (it) {
        if (isSubBalloonItem(it) || it.is_parent_balloon) return false;
        const di = detectionIndexForItem(det, it);
        return di != null && vis[di];
      })
    );
  }

  function visibleBalloonCount(det) {
    return detectionEntriesForCanvas(det).length;
  }

  /** Inspection report: visible balloons with extracted data (no confirm step). */
  function itemsForDisplay(det) {
    return itemsForTable(det).filter(function (it) {
      return balloonHasExtractedData(it);
    });
  }

  function expandMultiplierBalloons(det) {
    if (!det || !det.balloon_items || !det.balloon_items.length) return det;
    if (isAlreadyMultiplierExpanded(det)) {
      pruneParentBalloonsWithSubs(det);
      repairMultiplierDrawingAnnotations(det);
      return syncBalloonItemsFromDetections(det);
    }
    stripSubBalloons(det);

    const items = det.balloon_items || [];
    const newItems = [];

    for (let i = 0; i < items.length; i++) {
      if (isSubBalloonItem(items[i])) continue;

      const it = Object.assign({}, items[i] || {});
      const detIdx = it.detection_index != null && it.detection_index >= 0 ? it.detection_index : i;
      it.detection_index = detIdx;
      const parentNum = it.balloon_number != null ? it.balloon_number : detIdx + 1;

      ensureMultiplierInItem(it);
      enrichBalloonItem(it);
      const mult = multiplierCountFromItem(it);

      if (mult >= 2) {
        it.multiplier_count = mult;
        it.multiplier_notation = multiplierNotation(balloonItemText(it), mult);
        for (let k = 1; k <= mult; k++) {
          const subNum = parentNum + "." + k;
          newItems.push(
            Object.assign({}, it, {
              balloon_number: subNum,
              parent_balloon_number: parentNum,
              sub_balloon_index: k,
              is_sub_balloon: true,
              is_parent_balloon: false,
              detection_index: detIdx,
            })
          );
        }
        continue;
      }

      it.balloon_number = parentNum;
      newItems.push(it);
    }

    det.balloon_items = newItems;
    pruneParentBalloonsWithSubs(det);
    repairMultiplierDrawingAnnotations(det);
    return syncBalloonItemsFromDetections(det);
  }

  function syncBalloonItemsFromDetectionIds(det, detIndexToNewId) {
    const items = det.balloon_items || [];
    items.forEach(function (it) {
      if (!it) return;
      const di = it.detection_index;
      if (di == null || detIndexToNewId[di] == null) return;
      const newParent = detIndexToNewId[di];
      if (isSubBalloonItem(it)) {
        const k = it.sub_balloon_index || 1;
        it.parent_balloon_number = newParent;
        it.balloon_number = String(newParent) + "." + k;
      } else {
        it.balloon_number = newParent;
      }
    });
    det.balloon_items = items;
    return det;
  }

  function saveInspectionMetaFromDetection(det) {
    const tb = (det && det.title_block_meta) || {};
    let existing = {};
    if (window.InspectionStore && InspectionStore.getMeta) {
      existing = InspectionStore.getMeta() || {};
    }
    const meta = {
      partNumber: tb.part_number || tb.partNumber || existing.partNumber || "",
      partName: tb.part_name || tb.partName || existing.partName || "",
      revision: tb.revision || existing.revision || "",
      material: tb.material || existing.material || "",
      mass: tb.mass || existing.mass || "",
      finish: tb.finish_treatment || tb.finish || existing.finish || "",
      measuredColCount: existing.measuredColCount,
    };
    if (window.InspectionStore && InspectionStore.setMeta) {
      InspectionStore.setMeta(meta);
    } else {
      localStorage.setItem("smorx_inspection_meta", JSON.stringify(meta));
    }
  }

  /** YOLO class → box colors on the ballooning canvas (stroke + translucent fill). */
  var DETECTION_CLASS_COLORS = {
    Dimensions: {
      label: "Dimensions",
      stroke: "#0891b2",
      fill: "rgba(8, 145, 178, 0.22)",
    },
    GDnT: {
      label: "GD&T",
      stroke: "#c026d3",
      fill: "rgba(192, 38, 211, 0.18)",
    },
    Notes: {
      label: "Notes",
      stroke: "#ca8a04",
      fill: "rgba(202, 138, 4, 0.18)",
    },
    Surface_Finish_Symbols: {
      label: "Surface finish",
      stroke: "#059669",
      fill: "rgba(5, 150, 105, 0.18)",
    },
    Special_Characteristics: {
      label: "Special characteristic",
      stroke: "#dc2626",
      fill: "rgba(220, 38, 38, 0.16)",
    },
    _default: {
      label: "Other",
      stroke: "#6366f1",
      fill: "rgba(99, 102, 241, 0.16)",
    },
  };

  function normalizeDetectionClass(cls) {
    const s = String(cls || "").trim();
    if (!s) return "Dimensions";
    if (/^dimension/i.test(s)) return "Dimensions";
    if (/^gdt$/i.test(s) || /^gd&?t$/i.test(s) || /^gdn?t$/i.test(s)) return "GDnT";
    if (/^note/i.test(s)) return "Notes";
    if (/surface/i.test(s) && /finish/i.test(s)) return "Surface_Finish_Symbols";
    if (/special/i.test(s) && /char/i.test(s)) return "Special_Characteristics";
    if (DETECTION_CLASS_COLORS[s]) return s;
    return s;
  }

  function detectionClassPalette(cls) {
    const key = normalizeDetectionClass(cls);
    return DETECTION_CLASS_COLORS[key] || DETECTION_CLASS_COLORS._default;
  }

  /** Human-readable label for canvas/table (never DIM/GDT abbreviations). */
  function formatDetectionClassLabel(cls) {
    const raw = String(cls || "").trim();
    const pal = detectionClassPalette(raw);
    if (pal && pal.label && pal.label !== "Other") {
      return pal.label;
    }
    if (raw) {
      return raw.replace(/_/g, " ");
    }
    return "Dimensions";
  }

  function detectionClassLegendList() {
    return [
      "Dimensions",
      "GDnT",
      "Notes",
      "Surface_Finish_Symbols",
      "Special_Characteristics",
    ].map(function (key) {
      const p = DETECTION_CLASS_COLORS[key];
      return { key: key, label: p.label, stroke: p.stroke, fill: p.fill };
    });
  }

  global.BalloonParse = {
    DETECTION_CLASS_COLORS: DETECTION_CLASS_COLORS,
    normalizeDetectionClass: normalizeDetectionClass,
    detectionClassPalette: detectionClassPalette,
    formatDetectionClassLabel: formatDetectionClassLabel,
    detectionClassLegendList: detectionClassLegendList,
    parseDetectedText: parseDetectedText,
    parseBalloonItem: parseBalloonItem,
    enrichBalloonItem: enrichBalloonItem,
    balloonHasExtractedData: balloonHasExtractedData,
    hideIncompleteBalloons: hideIncompleteBalloons,
    findItemForDetectionIndex: findItemForDetectionIndex,
    buildDetectedText: buildDetectedText,
    parseMultiplierCount: parseMultiplierCount,
    expandMultiplierBalloons: expandMultiplierBalloons,
    removeDuplicateYoloDetectionsNearMultiplier: removeDuplicateYoloDetectionsNearMultiplier,
    pruneParentBalloonsWithSubs: pruneParentBalloonsWithSubs,
    ensureDrawingAnnotations: ensureDrawingAnnotations,
    drawingCanvasLabel: drawingCanvasLabel,
    wholeBalloonNumber: wholeBalloonNumber,
    canvasLabelForDetection: canvasLabelForDetection,
    detectionEntriesForCanvas: detectionEntriesForCanvas,
    findBalloonItem: findBalloonItem,
    tightBalloonPlacement: tightBalloonPlacement,
    tightTextPosForBbox: tightTextPosForBbox,
    annotationsForCanvas: annotationsForCanvas,
    repairMultiplierDrawingAnnotations: repairMultiplierDrawingAnnotations,
    syncBalloonItemsFromDetectionIds: syncBalloonItemsFromDetectionIds,
    isAlreadyMultiplierExpanded: isAlreadyMultiplierExpanded,
    saveInspectionMetaFromDetection: saveInspectionMetaFromDetection,
    syncBalloonItemsFromDetections: syncBalloonItemsFromDetections,
    itemsForTable: itemsForTable,
    itemsForDisplay: itemsForDisplay,
    sortBalloonItemsTblr: sortBalloonItemsTblr,
    visibleBalloonCount: visibleBalloonCount,
    visibleDetectionIndexSet: visibleDetectionIndexSet,
  };
})(typeof window !== "undefined" ? window : globalThis);

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
    const fromText = parseMultiplierCount(balloonItemText(it));
    if (fromText >= 2) return fromText;
    return parseMultiplierCount(it.multiplier_notation || "");
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
  function drawingCanvasLabel(ann) {
    if (!ann) return "";
    if (ann.display_id != null && String(ann.display_id).trim() !== "") {
      const d = String(ann.display_id);
      const dm = d.match(/^(\d+)\.\d+$/);
      return dm ? dm[1] : d;
    }
    if (ann.parent_balloon_number != null && String(ann.parent_balloon_number).trim() !== "") {
      return String(ann.parent_balloon_number);
    }
    const id = String(ann.id != null ? ann.id : "");
    const m = id.match(/^(\d+)\.\d+$/);
    return m ? m[1] : id;
  }

  function annotationsForCanvas(det) {
    return (det.drawing_annotations || []).filter(function (a) {
      return a && !a.draw_suppress && !a.canvas_skip && !a.report_only && !a.is_parent_balloon;
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

  /** Looser match for extra YOLO boxes on the same nX callout (text + leader line). */
  function bboxNearMultiplierDuplicate(primaryBb, thisBb) {
    if (!primaryBb || !thisBb || primaryBb.length < 4 || thisBb.length < 4) return false;
    if (bboxOverlap(primaryBb, thisBb) >= 0.08) return true;
    if (bboxNearDuplicate(primaryBb, thisBb)) return true;
    const pcx = (primaryBb[0] + primaryBb[2]) / 2;
    const pcy = (primaryBb[1] + primaryBb[3]) / 2;
    const tcx = (thisBb[0] + thisBb[2]) / 2;
    const tcy = (thisBb[1] + thisBb[3]) / 2;
    const w = Math.max(primaryBb[2] - primaryBb[0], thisBb[2] - thisBb[0], 60);
    const h = Math.max(primaryBb[3] - primaryBb[1], thisBb[3] - thisBb[1], 20);
    if (Math.abs(pcy - tcy) > h * 2.5) return false;
    return Math.abs(pcx - tcx) < w * 3.5;
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
        TextPos: bb.length >= 4 ? [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2] : [],
      };
    });
    det.drawing_annotations = anns;
  }

  /** Fix drawing ann id = whole number (15) when table has 15.1 / 15.2. */
  function repairMultiplierDrawingAnnotations(det) {
    if (!det) return det;
    ensureDrawingAnnotations(det);
    const dets = det.detections || [];
    const anns = det.drawing_annotations || [];
    const items = det.balloon_items || [];
    if (!dets.length || !anns.length) return det;

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

    const hasSubs = Object.keys(primaryDetByParent).length > 0;

    for (let i = 0; i < anns.length; i++) {
      const ann = anns[i];
      if (!ann) continue;
      delete ann.draw_suppress;
      delete ann.canvas_skip;
      delete ann.display_id;
      delete ann.report_only;

      let pid = ann.id != null ? ann.id : i + 1;
      if (hasSubs) {
        const parentKeys = Object.keys(primaryDetByParent);
        for (let pi = 0; pi < parentKeys.length; pi++) {
          const p = parentKeys[pi];
          const primaryDi = primaryDetByParent[p];
          if (i === primaryDi) {
            pid = p;
            break;
          }
          const primaryBb = bboxForBalloonRow(det, primaryDi, itemAtDetectionIndex(det, primaryDi));
          const thisBb = bboxForBalloonRow(det, i, itemAtDetectionIndex(det, i));
          if (primaryBb && thisBb && bboxOverlap(primaryBb, thisBb) >= 0.3) {
            ann.draw_suppress = true;
            det.drawing_annotations[i] = ann;
            break;
          }
        }
        if (ann.draw_suppress) continue;
      }
      ann.id = pid;
      ann.display_id = drawingCanvasLabel({ id: pid, display_id: pid });
      if (ann.BBox && ann.BBox.length >= 4) {
        const bb = ann.BBox;
        ann.TextPos = [(bb[0] + bb[2]) / 2, bb[1] - 12];
      }
      det.drawing_annotations[i] = ann;
    }
    det.drawing_annotations = anns;
    delete det.canvas_balloon_annotations;
    return det;
  }

  /**
   * nX: split balloon_items only (15.1, 15.2 in table).
   * drawing_annotations stay 1:1 with detections — balloon 15 on drawing.
   */
  function expandMultiplierBalloons(det) {
    if (!det || !det.balloon_items || !det.balloon_items.length) return det;
    if (isAlreadyMultiplierExpanded(det)) {
      pruneParentBalloonsWithSubs(det);
      pruneOverlappingDuplicateDetections(det);
      return repairMultiplierDrawingAnnotations(det);
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
    pruneOverlappingDuplicateDetections(det);
    return repairMultiplierDrawingAnnotations(det);
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

  global.BalloonParse = {
    parseDetectedText: parseDetectedText,
    parseBalloonItem: parseBalloonItem,
    enrichBalloonItem: enrichBalloonItem,
    buildDetectedText: buildDetectedText,
    parseMultiplierCount: parseMultiplierCount,
    expandMultiplierBalloons: expandMultiplierBalloons,
    removeDuplicateYoloDetectionsNearMultiplier: removeDuplicateYoloDetectionsNearMultiplier,
    pruneParentBalloonsWithSubs: pruneParentBalloonsWithSubs,
    ensureDrawingAnnotations: ensureDrawingAnnotations,
    drawingCanvasLabel: drawingCanvasLabel,
    annotationsForCanvas: annotationsForCanvas,
    repairMultiplierDrawingAnnotations: repairMultiplierDrawingAnnotations,
    syncBalloonItemsFromDetectionIds: syncBalloonItemsFromDetectionIds,
    isAlreadyMultiplierExpanded: isAlreadyMultiplierExpanded,
    saveInspectionMetaFromDetection: saveInspectionMetaFromDetection,
  };
})(typeof window !== "undefined" ? window : globalThis);

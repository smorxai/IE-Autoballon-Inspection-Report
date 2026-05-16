(function () {
  const ORIGIN = window.location.origin;
  const cred = { credentials: "same-origin" };
  const apiBaseEl = document.getElementById("apiBase");
  if (apiBaseEl) apiBaseEl.textContent = ORIGIN;

  const fileInput = document.getElementById("file");
  const runBtn = document.getElementById("runBtn");
  const statusEl = document.getElementById("status");
  const panelInput = document.getElementById("panelInput");
  const panelDetect = document.getElementById("panelDetect");
  const panelBalloon = document.getElementById("panelBalloon");
  const jsonOut = document.getElementById("jsonOut");
  const resultBody = document.getElementById("resultBody");
  const downloadInput = document.getElementById("downloadInput");
  const downloadBalloon = document.getElementById("downloadBalloon");
  const downloadExcel = document.getElementById("downloadExcel");
  const inspectionReport = document.getElementById("inspectionReport");
  const INSPECTION_STORAGE_KEY = "smorx_inspection_payload";
  const adminLink = document.getElementById("adminLink");
  const logoutBtn = document.getElementById("logoutBtn");

  let lastFile = null;
  let lastJson = null;
  let lastBalloonCanvas = null;
  let lastInputPreviewUrl = null;

  function revokeInputPreviewUrl() {
    if (lastInputPreviewUrl) {
      URL.revokeObjectURL(lastInputPreviewUrl);
      lastInputPreviewUrl = null;
    }
  }

  function setInputDownloadEnabled(on) {
    if (downloadInput) downloadInput.disabled = !on;
  }

  const balloonSave = document.getElementById("balloonSave");

  function setBalloonDownloadEnabled(on) {
    if (downloadBalloon) downloadBalloon.disabled = !on;
    if (balloonSave) balloonSave.disabled = !on;
  }

  function setExcelDownloadEnabled(on) {
    if (downloadExcel) downloadExcel.disabled = !on;
  }

  function setInspectionReportEnabled(on) {
    if (!inspectionReport) return;
    inspectionReport.disabled = !on;
    inspectionReport.setAttribute("aria-pressed", on ? "true" : "false");
  }

  function setStatus(t) {
    statusEl.textContent = t || "";
  }

  function authRedirect(status) {
    if (status === 401) {
      window.location.href = "/login";
      return true;
    }
    if (status === 402) {
      window.location.href = "/payment";
      return true;
    }
    return false;
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      fetch(ORIGIN + "/api/auth/logout", Object.assign({ method: "POST" }, cred)).then(function () {
        window.location.href = "/login";
      });
    });
  }

  fetch(ORIGIN + "/api/auth/me", cred)
    .then(function (r) {
      return r.json();
    })
    .then(function (me) {
      if (me && me.ok && me.role === "admin" && adminLink) {
        adminLink.style.display = "inline-block";
      }
    })
    .catch(function () {});

  function renderResultTable(data) {
    if (!resultBody) return;
    const items = ((data || {}).detection || {}).balloon_items || [];
    if (!items.length) {
      resultBody.innerHTML = "<tr><td colspan=\"4\">No extracted values found.</td></tr>";
      return;
    }
    resultBody.innerHTML = "";
    items.forEach(function (it) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + (it.balloon_number != null ? it.balloon_number : "") + "</td>" +
        "<td>" + (it.class_name || "") + "</td>" +
        "<td>" + (it.detected_text || "") + "</td>" +
        "<td>" + (it.confidence != null ? it.confidence : "") + "</td>";
      resultBody.appendChild(tr);
    });
  }

  function clearPanel(el, placeholder) {
    if (!el) return;
    if (el === panelInput) revokeInputPreviewUrl();
    el.innerHTML = "";
    if (placeholder) {
      const p = document.createElement("p");
      p.className = "placeholder";
      p.textContent = placeholder;
      el.appendChild(p);
    }
  }

  function showInputPreview(file) {
    clearPanel(panelInput);
    setInputDownloadEnabled(!!file);
    if (!file) return;
    if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) {
      const embed = document.createElement("embed");
      embed.className = "pdf-preview";
      embed.type = "application/pdf";
      lastInputPreviewUrl = URL.createObjectURL(file);
      embed.src = lastInputPreviewUrl;
      panelInput.appendChild(embed);
      return;
    }
    const img = document.createElement("img");
    img.alt = "Input";
    lastInputPreviewUrl = URL.createObjectURL(file);
    img.src = lastInputPreviewUrl;
    panelInput.appendChild(img);
  }

  function showInputRaster(img, det) {
    if (!panelInput) return;
    revokeInputPreviewUrl();
    clearPanel(panelInput);
    panelInput.appendChild(makeCanvasFromImage(img, det, function () {}));
  }

  function loadImageForDraw(det) {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      if (det.preview_image_base64) {
        img.src = det.preview_image_base64;
      } else if (lastFile) {
        img.src = URL.createObjectURL(lastFile);
      } else {
        reject(new Error("No image source"));
        return;
      }
      img.onload = function () {
        resolve(img);
      };
      img.onerror = reject;
    });
  }

  function makeCanvasFromImage(img, det, drawFn) {
    const iw = Number(det.width) || img.naturalWidth;
    const ih = Number(det.height) || img.naturalHeight;
    const maxW = Math.min(1100, iw);
    const sx = maxW / iw;
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(iw * sx);
    canvas.height = Math.floor(ih * sx);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    drawFn(ctx, sx, det);
    return canvas;
  }

  function drawDetections(ctx, scale, det) {
    (det.detections || []).forEach(function (d) {
      const bb = d.bbox;
      if (!bb || bb.length < 4) return;
      ctx.strokeStyle = "#34d399";
      ctx.lineWidth = 2;
      ctx.strokeRect(bb[0] * scale, bb[1] * scale, (bb[2] - bb[0]) * scale, (bb[3] - bb[1]) * scale);
    });
  }

  function drawBalloons(ctx, scale, det) {
    const anns = det.drawing_annotations || [];
    const BALLOON_DIAMETER_MM = 5;
    const CSS_DPI = 96;
    const pxPerMm = CSS_DPI / 25.4;
    const r = (BALLOON_DIAMETER_MM * pxPerMm) / 2;
    const darkRed = "#8b0000";
    const placed = [];
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    const laneGap = r * 2.6;
    const laneMargin = r + 8;
    const laneY = { left: laneMargin, right: laneMargin };
    let imageData = null;
    try {
      imageData = ctx.getImageData(0, 0, w, h).data;
    } catch (e) {
      imageData = null;
    }

    function clamp(v, lo, hi) {
      return Math.max(lo, Math.min(hi, v));
    }

    function chooseCenter(ann, x1, y1, x2, y2) {
      let cx = (x1 + x2) / 2;
      let cy = (y1 + y2) / 2;
      const t = ann.TextPos;
      if (Array.isArray(t) && t.length >= 2 && Number.isFinite(t[0]) && Number.isFinite(t[1])) {
        cx = t[0] * scale;
        cy = t[1] * scale;
      }
      // Keep the balloon inside canvas bounds.
      cx = clamp(cx, r + 1, w - r - 1);
      cy = clamp(cy, r + 1, h - r - 1);
      return { cx: cx, cy: cy };
    }

    function nudgeAway(cx, cy) {
      const minDist = r * 2.2;
      let tries = 0;
      while (tries < 24) {
        let moved = false;
        for (let i = 0; i < placed.length; i++) {
          const p = placed[i];
          const dx = cx - p.cx;
          const dy = cy - p.cy;
          const d = Math.hypot(dx, dy) || 0.0001;
          if (d < minDist) {
            const push = (minDist - d) + 1;
            cx += (dx / d) * push;
            cy += (dy / d) * push;
            cx = clamp(cx, r + 1, w - r - 1);
            cy = clamp(cy, r + 1, h - r - 1);
            moved = true;
          }
        }
        if (!moved) break;
        tries += 1;
      }
      return { cx: cx, cy: cy };
    }

    function getInkRatio(cx, cy) {
      if (!imageData) return 0;
      const rr = Math.max(2, Math.floor(r * 0.9));
      const step = 2;
      let dark = 0;
      let total = 0;
      for (let yy = -rr; yy <= rr; yy += step) {
        for (let xx = -rr; xx <= rr; xx += step) {
          if (xx * xx + yy * yy > rr * rr) continue;
          const px = Math.round(cx + xx);
          const py = Math.round(cy + yy);
          if (px < 0 || py < 0 || px >= w || py >= h) continue;
          const idx = (py * w + px) * 4;
          const rv = imageData[idx];
          const gv = imageData[idx + 1];
          const bv = imageData[idx + 2];
          // Count mostly dark drawing/text pixels.
          if (rv < 165 && gv < 165 && bv < 165) dark += 1;
          total += 1;
        }
      }
      return total > 0 ? dark / total : 0;
    }

    function overlapPenalty(cx, cy) {
      let pen = 0;
      const minDist = r * 2.2;
      for (let i = 0; i < placed.length; i++) {
        const p = placed[i];
        const d = Math.hypot(cx - p.cx, cy - p.cy);
        if (d < minDist) pen += (minDist - d) / minDist;
      }
      return pen;
    }

    function chooseBestNearby(cx, cy) {
      const baseStep = Math.max(10, Math.round(r * 2.2));
      const candidates = [[0, 0]];
      // Ring search in cardinal + diagonal directions.
      for (let ring = 1; ring <= 10; ring++) {
        const d = ring * baseStep;
        candidates.push([d, 0], [-d, 0], [0, -d], [0, d]);
        candidates.push([d, -d], [-d, -d], [d, d], [-d, d]);
        // Slight offsets so we can escape dense note areas.
        const s = Math.round(d * 0.5);
        candidates.push([d, s], [d, -s], [-d, s], [-d, -s], [s, d], [-s, d], [s, -d], [-s, -d]);
      }
      let best = { cx: cx, cy: cy };
      let bestScore = Number.POSITIVE_INFINITY;
      for (let i = 0; i < candidates.length; i++) {
        const dx = candidates[i][0];
        const dy = candidates[i][1];
        const tx = clamp(cx + dx, r + 1, w - r - 1);
        const ty = clamp(cy + dy, r + 1, h - r - 1);
        const ink = getInkRatio(tx, ty);
        const overlap = overlapPenalty(tx, ty);
        // Prefer white areas first, then avoid overlap, then smaller movement.
        const dist = Math.hypot(dx, dy);
        const score = ink * 22 + overlap * 7 + dist * 0.0015;
        if (score < bestScore) {
          bestScore = score;
          best = { cx: tx, cy: ty };
        }
        // Stop early when we find a clean white zone with no overlap.
        if (ink < 0.015 && overlap < 0.01) break;
      }
      return best;
    }

    function placeInSideLane(preferred) {
      const side = preferred.cx > w * 0.55 ? "right" : "left";
      const cx = side === "right" ? (w - laneMargin) : laneMargin;
      let cy = Math.max(preferred.cy, laneY[side]);
      cy = clamp(cy, laneMargin, h - laneMargin);
      laneY[side] = cy + laneGap;
      return { cx: cx, cy: cy };
    }

    const sorted = anns.slice().sort(function (a, b) {
      const ay = Array.isArray(a.TextPos) && a.TextPos.length >= 2 ? Number(a.TextPos[1]) : ((a.BBox && a.BBox.length >= 4) ? (a.BBox[1] + a.BBox[3]) / 2 : 0);
      const by = Array.isArray(b.TextPos) && b.TextPos.length >= 2 ? Number(b.TextPos[1]) : ((b.BBox && b.BBox.length >= 4) ? (b.BBox[1] + b.BBox[3]) / 2 : 0);
      return ay - by;
    });

    sorted.forEach(function (ann) {
      const bb = ann.BBox;
      if (!bb || bb.length < 4) return;
      const x1 = bb[0] * scale;
      const y1 = bb[1] * scale;
      const x2 = bb[2] * scale;
      const y2 = bb[3] * scale;
      const preferred = chooseCenter(ann, x1, y1, x2, y2);
      const whiteSpot = chooseBestNearby(preferred.cx, preferred.cy);
      // If still on dense notes/text, move to side lane in top-to-down sequence.
      const inkAtWhiteSpot = getInkRatio(whiteSpot.cx, whiteSpot.cy);
      const laneSpot = inkAtWhiteSpot > 0.055 ? placeInSideLane(preferred) : whiteSpot;
      const pos = nudgeAway(laneSpot.cx, laneSpot.cy);
      const cx = pos.cx;
      const cy = pos.cy;

      ctx.save();
      ctx.strokeStyle = darkRed;
      ctx.fillStyle = darkRed;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.font = "bold 8px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(ann.id != null ? ann.id : ""), cx, cy);
      ctx.restore();
      placed.push({ cx: cx, cy: cy });
    });
  }

  function renderResults(data) {
    const det = data.detection;
    if (!det) return;

    loadImageForDraw(det)
      .then(function (img) {
        if (panelDetect) {
          clearPanel(panelDetect);
          panelDetect.appendChild(makeCanvasFromImage(img, det, drawDetections));
        }

        showInputRaster(img, det);

        clearPanel(panelBalloon);
        const balloonCanvas = makeCanvasFromImage(img, det, drawBalloons);
        panelBalloon.appendChild(balloonCanvas);
        lastBalloonCanvas = balloonCanvas;
        setBalloonDownloadEnabled(true);

        if (!det.preview_image_base64 && lastFile && img.src.indexOf("blob:") === 0) {
          URL.revokeObjectURL(img.src);
        }
      })
      .catch(function (e) {
        if (panelDetect) clearPanel(panelDetect, "Could not render: " + e);
        clearPanel(panelBalloon);
        lastBalloonCanvas = null;
        setBalloonDownloadEnabled(false);
      });
  }

  function downloadBlob(blob, filename) {
    const a = document.createElement("a");
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  function toCsvCell(v) {
    const s = v == null ? "" : String(v);
    if (/[",\n]/.test(s)) return "\"" + s.replace(/"/g, "\"\"") + "\"";
    return s;
  }

  function buildCsvFromJson(payload) {
    const det = (payload && payload.detection) || {};
    const rows = [];
    rows.push(["Summary"]);
    rows.push(["filename", payload.filename || ""]);
    rows.push(["count", det.count || 0]);
    rows.push(["width", det.width || ""]);
    rows.push(["height", det.height || ""]);
    rows.push([]);
    rows.push(["Detections"]);
    rows.push(["id", "class_name", "confidence", "x1", "y1", "x2", "y2"]);
    (det.detections || []).forEach(function (d, idx) {
      const bb = d.bbox || [];
      rows.push([
        idx + 1,
        d.class_name || "",
        d.confidence || "",
        bb[0] != null ? bb[0] : "",
        bb[1] != null ? bb[1] : "",
        bb[2] != null ? bb[2] : "",
        bb[3] != null ? bb[3] : "",
      ]);
    });
    rows.push([]);
    rows.push(["Balloons"]);
    rows.push(["id", "AnnotationType", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2", "text_x", "text_y"]);
    (det.drawing_annotations || []).forEach(function (a) {
      const bb = a.BBox || [];
      const tp = a.TextPos || [];
      rows.push([
        a.id != null ? a.id : "",
        a.AnnotationType || "",
        bb[0] != null ? bb[0] : "",
        bb[1] != null ? bb[1] : "",
        bb[2] != null ? bb[2] : "",
        bb[3] != null ? bb[3] : "",
        tp[0] != null ? tp[0] : "",
        tp[1] != null ? tp[1] : "",
      ]);
    });
    rows.push([]);
    rows.push(["Extracted text (per balloon)"]);
    rows.push(["balloon_number", "class_name", "confidence", "detected_text"]);
    (det.balloon_items || []).forEach(function (it) {
      rows.push([
        it.balloon_number != null ? it.balloon_number : "",
        it.class_name || "",
        it.confidence != null ? it.confidence : "",
        it.detected_text || "",
      ]);
    });
    return rows.map(function (r) { return r.map(toCsvCell).join(","); }).join("\n");
  }

  if (downloadInput) {
    downloadInput.addEventListener("click", function () {
      if (!lastFile) return;
      downloadBlob(lastFile, lastFile.name || "input");
    });
  }

  if (downloadBalloon) {
    downloadBalloon.addEventListener("click", function () {
      if (!lastBalloonCanvas) return;
      lastBalloonCanvas.toBlob(function (blob) {
        if (!blob) return;
        const base = lastFile && lastFile.name ? lastFile.name.replace(/\.[^.]+$/, "") : "drawing";
        downloadBlob(blob, "AutoBallooning_" + base + ".png");
      }, "image/png");
    });
  }

  if (inspectionReport) {
    inspectionReport.addEventListener("click", function () {
      if (!lastJson) return;
      try {
        sessionStorage.setItem(INSPECTION_STORAGE_KEY, JSON.stringify(lastJson));
      } catch (e) {
        setStatus("Could not open inspection report: " + e);
        return;
      }
      window.location.href = "/inspection-report";
    });
  }

  if (downloadExcel) {
    downloadExcel.addEventListener("click", async function () {
      if (!lastJson) return;
      try {
        const paths = ["/api/v1/export-excel", "/api/export-excel", "/export-excel"];
        let r = null;
        for (let i = 0; i < paths.length; i++) {
          const rr = await fetch(ORIGIN + paths[i], Object.assign({
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(lastJson),
          }, cred));
          if (authRedirect(rr.status)) return;
          if (rr.ok) {
            r = rr;
            break;
          }
          if (rr.status !== 404) {
            r = rr;
            break;
          }
        }
        if (!r || !r.ok) {
          const base404 = !r || r.status === 404;
          if (base404) {
            const base = lastFile && lastFile.name ? lastFile.name.replace(/\.[^.]+$/, "") : "drawing";
            const csv = buildCsvFromJson(lastJson);
            const blobCsv = new Blob([csv], { type: "text/csv;charset=utf-8" });
            downloadBlob(blobCsv, "AutoBallooning_" + base + ".csv");
            setStatus("Excel endpoint missing; downloaded CSV for Excel.");
            return;
          }
          setStatus("Excel export failed: HTTP " + r.status);
          return;
        }
        const blob = await r.blob();
        const base = lastFile && lastFile.name ? lastFile.name.replace(/\.[^.]+$/, "") : "drawing";
        downloadBlob(blob, "AutoBallooning_" + base + ".xlsx");
      } catch (e) {
        setStatus("Excel export failed: " + e);
      }
    });
  }

  fileInput.addEventListener("change", function () {
    lastFile = fileInput.files && fileInput.files[0];
    showInputPreview(lastFile);
    lastJson = null;
    if (jsonOut) jsonOut.textContent = "{}";
    lastBalloonCanvas = null;
    setBalloonDownloadEnabled(false);
    setExcelDownloadEnabled(false);
    setInspectionReportEnabled(false);
    if (resultBody) resultBody.innerHTML = "<tr><td colspan=\"4\">Run auto ballooning to see extracted values.</td></tr>";
    if (panelDetect) clearPanel(panelDetect, "Run detect to see green boxes.");
    clearPanel(panelBalloon, "Run auto ballooning to see balloons here.");
  });

  runBtn.addEventListener("click", async function () {
    if (!lastFile) {
      setStatus("Choose a file first.");
      return;
    }
    runBtn.disabled = true;
    setStatus("Processing…");
    if (jsonOut) jsonOut.textContent = "…";

    try {
      const fd = new FormData();
      fd.append("file", lastFile);
      const r = await fetch(ORIGIN + "/api/v1/detect", Object.assign({
        method: "POST",
        body: fd,
      }, cred));
      if (authRedirect(r.status)) return;
      const text = await r.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        setStatus("Non-JSON response HTTP " + r.status);
        if (jsonOut) jsonOut.textContent = text.slice(0, 4000);
        return;
      }
      if (jsonOut) jsonOut.textContent = JSON.stringify(data, null, 2);
      if (!r.ok || !data.ok) {
        setStatus("Error: " + (data.error || data.detail || "HTTP " + r.status));
        return;
      }
      lastJson = data;
      renderResults(data);
      renderResultTable(data);
      setExcelDownloadEnabled(true);
      setInspectionReportEnabled(true);
      setStatus("Done.");
    } catch (e) {
      setStatus("Request failed: " + e);
      if (jsonOut) jsonOut.textContent = String(e);
    }
    runBtn.disabled = false;
  });
})();

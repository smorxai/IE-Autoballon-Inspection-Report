(function () {
  const STORAGE_KEY = "smorx_inspection_payload";
  const META_KEY = "smorx_inspection_meta";
  const MIN_MEASURED_COLS = 1;
  const DEFAULT_MEASURED_COLS = 3;

  const irEmpty = document.getElementById("irEmpty");
  const irContent = document.getElementById("irContent");
  const irThead = document.getElementById("irThead");
  const irTbody = document.getElementById("irTbody");
  const irDashboardBtn = document.getElementById("irDashboardBtn");
  const irTableWrap = document.getElementById("irTableWrap");
  const irScrollLeft = document.getElementById("irScrollLeft");
  const irScrollRight = document.getElementById("irScrollRight");
  const irDownloadReport = document.getElementById("irDownloadReport");

  let measuredColCount = DEFAULT_MEASURED_COLS;
  let rows = [];

  function parseTolOffset(val) {
    if (val === "" || val === "—" || val == null) return null;
    const s = String(val).trim().replace(/^\+/, "");
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : null;
  }

  function parseBalloonDims(it) {
    if (window.BalloonParse && BalloonParse.parseBalloonItem) {
      return BalloonParse.parseBalloonItem(it);
    }
    return { nominal: "", tolLow: "", tolHigh: "" };
  }

  function referenceFromAnnotation(ann, imgW, imgH) {
    if (!ann || !ann.BBox || ann.BBox.length < 4 || !imgW || !imgH) return "";
    const bb = ann.BBox;
    const cx = (bb[0] + bb[2]) / 2;
    const cy = (bb[1] + bb[3]) / 2;
    const cols = 10;
    const rowSlots = 10;
    const col = Math.min(cols, Math.max(1, Math.ceil((cx / imgW) * cols)));
    const rowIdx = Math.min(rowSlots, Math.max(1, Math.ceil((cy / imgH) * rowSlots)));
    const rowLetter = String.fromCharCode(64 + rowIdx);
    return "Col " + col + " - Row " + rowLetter;
  }

  function formatTolDisplay(val) {
    if (val === "" || val == null) return "—";
    return String(val);
  }

  function evaluateMeasurement(nominal, tolLow, tolHigh, measured) {
    const mStr = String(measured == null ? "" : measured).trim();
    if (!mStr) return { status: "none", label: "—" };

    const m = parseFloat(mStr);
    if (!Number.isFinite(m)) return { status: "none", label: "—" };

    const n = parseFloat(String(nominal).trim());
    if (!Number.isFinite(n)) return { status: "none", label: "—" };

    const lo = parseTolOffset(tolLow);
    const hi = parseTolOffset(tolHigh);
    const hasLo = lo !== null;
    const hasHi = hi !== null;

    const eps = 1e-6;

    if (!hasLo && !hasHi) {
      if (Math.abs(m - n) < eps) return { status: "pass", label: "Nominal" };
      return { status: "fail", label: "Fail" };
    }

    const lowerBound = hasLo ? n + lo : n;
    const upperBound = hasHi ? n + hi : n;

    if (m < lowerBound - eps || m > upperBound + eps) {
      return { status: "fail", label: "Out of tolerance" };
    }
    if (Math.abs(m - n) < eps) {
      return { status: "pass", label: "Nominal" };
    }
    return { status: "warn", label: "In tolerance" };
  }

  function measuredCellHtml(row, rowIdx, col) {
    const ev = evaluateMeasurement(row.nominal, row.tolLow, row.tolHigh, row.measured[col]);
    const cls = ev.status === "pass" ? "ir-pass" : ev.status === "warn" ? "ir-warn" : ev.status === "fail" ? "ir-fail" : "";
    const dotCls = ev.status === "none" ? "" : ev.status;
    return (
      '<td><div class="ir-measured-cell">' +
      '<span class="ir-status-dot ' + dotCls + '" data-dot-row="' + rowIdx + '" data-dot-col="' + col + '"></span>' +
      '<input type="text" class="ir-measured ' + cls + '" data-field="measured" data-row="' + rowIdx + '" data-col="' + col + '" value="' + escAttr(row.measured[col]) + '" />' +
      "</div></td>"
    );
  }

  function buildRowsFromPayload(payload) {
    const det = (payload && payload.detection) || {};
    let items = [];
    if (window.BalloonParse && BalloonParse.hideIncompleteBalloons) {
      BalloonParse.hideIncompleteBalloons(det);
    }
    if (window.BalloonParse && BalloonParse.itemsForDisplay) {
      items = BalloonParse.itemsForDisplay(det);
    } else if (window.BalloonParse && BalloonParse.itemsForTable) {
      items = BalloonParse.itemsForTable(det);
      if (BalloonParse.balloonHasExtractedData) {
        items = items.filter(function (it) {
          return BalloonParse.balloonHasExtractedData(it);
        });
      }
    } else {
      items = det.balloon_items || [];
    }
    if (window.BalloonParse && BalloonParse.sortBalloonItemsTblr) {
      items = BalloonParse.sortBalloonItemsTblr(items);
    }
    const anns = det.drawing_annotations || [];
    const imgW = Number(det.width) || 1;
    const imgH = Number(det.height) || 1;
    const annById = {};
    anns.forEach(function (a) {
      if (a.id != null) annById[a.id] = a;
    });

    return items.map(function (it, idx) {
      if (window.BalloonParse && BalloonParse.enrichBalloonItem) {
        BalloonParse.enrichBalloonItem(it);
      }
      const bn = it.balloon_number != null ? it.balloon_number : idx + 1;
      const parsed = parseBalloonDims(it);
      const ann = annById[bn] || anns[idx];
      const measured = [];
      for (let i = 0; i < measuredColCount; i++) measured.push("");
      return {
        sno: idx + 1,
        balloonNumber: bn,
        referenceLocation: referenceFromAnnotation(ann, imgW, imgH),
        nominal: parsed.nominal,
        tolLow: parsed.tolLow,
        tolHigh: parsed.tolHigh,
        instrument: "",
        instrumentId: "",
        measured: measured,
        remarks: "",
      };
    });
  }

  function loadMeta() {
    try {
      const meta =
        window.InspectionStore && InspectionStore.getMeta
          ? InspectionStore.getMeta()
          : JSON.parse(localStorage.getItem(META_KEY) || sessionStorage.getItem(META_KEY) || "null");
      if (!meta) return;
      if (meta.partNumber != null) document.getElementById("irPartNumber").value = meta.partNumber;
      if (meta.partName != null) document.getElementById("irPartName").value = meta.partName;
      if (meta.revision != null) document.getElementById("irRevision").value = meta.revision;
      if (meta.material != null) document.getElementById("irMaterial").value = meta.material;
      if (meta.mass != null) document.getElementById("irMass").value = meta.mass;
      if (meta.finish != null) document.getElementById("irFinish").value = meta.finish;
      if (meta.measuredColCount != null) measuredColCount = meta.measuredColCount;
    } catch (e) { /* ignore */ }
  }

  function saveMeta() {
    const meta = {
      partNumber: document.getElementById("irPartNumber").value,
      partName: document.getElementById("irPartName").value,
      revision: document.getElementById("irRevision").value,
      material: document.getElementById("irMaterial").value,
      mass: document.getElementById("irMass").value,
      finish: document.getElementById("irFinish").value,
      measuredColCount: measuredColCount,
    };
    if (window.InspectionStore && InspectionStore.setMeta) {
      InspectionStore.setMeta(meta);
    } else {
      localStorage.setItem(META_KEY, JSON.stringify(meta));
    }
  }

  function renderHeader() {
    const accSpan = 8;
    const measSpan = measuredColCount + 1;
    let html =
      "<tr>" +
      '<th colspan="' + accSpan + '" class="ir-col-accountability">Characteristics Accountability</th>' +
      '<th colspan="' + measSpan + '" class="ir-inspection-results-head">' +
      '<div class="ir-inspection-head-inner">' +
      '<span class="ir-inspection-title">Inspection &amp; results</span>' +
      '<div class="ir-colctrl-btns ir-colctrl-btns--inline">' +
      '<button type="button" id="irAddCol">+ column</button>' +
      '<button type="button" id="irRemoveCol">− column</button>' +
      "</div></div></th>" +
      "</tr>" +
      "<tr>" +
      "<th>S.No</th>" +
      "<th>Balloon Number</th>" +
      "<th>Reference location</th>" +
      "<th>Nominal</th>" +
      "<th>Tol (low)</th>" +
      "<th>Tol (high)</th>" +
      "<th>Instrument</th>" +
      '<th class="ir-col-accountability">Instrument ID</th>';

    for (let c = 0; c < measuredColCount; c++) {
      html += '<th class="ir-th-measured">Measured ' + (c + 1) + "</th>";
    }
    html += "<th>Remarks</th></tr>";
    irThead.innerHTML = html;

    const addBtn = document.getElementById("irAddCol");
    const remBtn = document.getElementById("irRemoveCol");
    if (addBtn) {
      addBtn.disabled = false;
      addBtn.onclick = addMeasuredColumn;
    }
    if (remBtn) {
      remBtn.disabled = measuredColCount <= MIN_MEASURED_COLS;
      remBtn.onclick = removeMeasuredColumn;
    }
  }

  function renderBody() {
    irTbody.innerHTML = "";
    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        '<td colspan="20" style="padding:1.5rem;text-align:center;color:#64748b">No balloon rows loaded. Go back to Auto Ballooning, run detection, then open <strong>Inspection report</strong>.</td>';
      irTbody.appendChild(tr);
      return;
    }
    rows.forEach(function (row, rowIdx) {
      while (row.measured.length < measuredColCount) row.measured.push("");
      if (row.measured.length > measuredColCount) row.measured = row.measured.slice(0, measuredColCount);

      const tr = document.createElement("tr");
      let html =
        '<td><span class="ir-readonly">' + row.sno + "</span></td>" +
        '<td><span class="ir-readonly">' + row.balloonNumber + "</span></td>" +
        '<td class="ir-td-ref"><input type="text" data-field="reference" data-row="' + rowIdx + '" value="' + escAttr(row.referenceLocation) + '" /></td>' +
        '<td><span class="ir-readonly">' + escHtml(row.nominal || "—") + "</span></td>" +
        '<td><span class="ir-readonly">' + escHtml(formatTolDisplay(row.tolLow)) + "</span></td>" +
        '<td><span class="ir-readonly">' + escHtml(formatTolDisplay(row.tolHigh)) + "</span></td>" +
        '<td><input type="text" data-field="instrument" data-row="' + rowIdx + '" value="' + escAttr(row.instrument) + '" /></td>' +
        '<td><input type="text" data-field="instrumentId" data-row="' + rowIdx + '" value="' + escAttr(row.instrumentId) + '" /></td>';

      for (let c = 0; c < measuredColCount; c++) {
        html += measuredCellHtml(row, rowIdx, c);
      }
      html +=
        '<td class="ir-td-remarks"><input type="text" data-field="remarks" data-row="' + rowIdx + '" value="' + escAttr(row.remarks) + '" /></td>';

      tr.innerHTML = html;
      irTbody.appendChild(tr);
    });

    bindRowInputs();
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escAttr(s) {
    return escHtml(s).replace(/'/g, "&#39;");
  }

  function updateMeasuredVisual(rowIdx, col) {
    const tr = irTbody.children[rowIdx];
    if (!tr || !rows[rowIdx]) return;
    const row = rows[rowIdx];
    const ev = evaluateMeasurement(row.nominal, row.tolLow, row.tolHigh, row.measured[col]);
    const inp = tr.querySelector('input[data-field="measured"][data-row="' + rowIdx + '"][data-col="' + col + '"]');
    const dot = tr.querySelector('.ir-status-dot[data-dot-row="' + rowIdx + '"][data-dot-col="' + col + '"]');
    if (inp) {
      inp.classList.remove("ir-pass", "ir-warn", "ir-fail");
      if (ev.status === "pass") inp.classList.add("ir-pass");
      else if (ev.status === "warn") inp.classList.add("ir-warn");
      else if (ev.status === "fail") inp.classList.add("ir-fail");
    }
    if (dot) {
      dot.classList.remove("pass", "warn", "fail");
      if (ev.status !== "none") dot.classList.add(ev.status);
    }
  }

  function bindRowInputs() {
    irTbody.querySelectorAll("input").forEach(function (inp) {
      inp.addEventListener("input", onRowInput);
      inp.addEventListener("change", onRowInput);
    });
  }

  function onRowInput(ev) {
    const inp = ev.target;
    const rowIdx = parseInt(inp.getAttribute("data-row"), 10);
    const field = inp.getAttribute("data-field");
    if (!Number.isFinite(rowIdx) || !rows[rowIdx]) return;
    const row = rows[rowIdx];

    if (field === "reference") row.referenceLocation = inp.value;
    else if (field === "instrument") row.instrument = inp.value;
    else if (field === "instrumentId") row.instrumentId = inp.value;
    else if (field === "remarks") row.remarks = inp.value;
    else if (field === "measured") {
      const col = parseInt(inp.getAttribute("data-col"), 10);
      row.measured[col] = inp.value;
      updateMeasuredVisual(rowIdx, col);
    }
    saveMeta();
  }

  function renderTable() {
    renderHeader();
    renderBody();
  }

  function addMeasuredColumn() {
    measuredColCount += 1;
    rows.forEach(function (r) {
      r.measured.push("");
    });
    saveMeta();
    renderTable();
  }

  function removeMeasuredColumn() {
    if (measuredColCount <= MIN_MEASURED_COLS) return;
    measuredColCount -= 1;
    rows.forEach(function (r) {
      if (r.measured.length > measuredColCount) r.measured = r.measured.slice(0, measuredColCount);
    });
    saveMeta();
    renderTable();
  }

  function collectReportMeta() {
    function v(id) {
      const el = document.getElementById(id);
      return el ? el.value.trim() : "";
    }
    return {
      partNumber: v("irPartNumber"),
      partName: v("irPartName"),
      revision: v("irRevision"),
      material: v("irMaterial"),
      mass: v("irMass"),
      finish: v("irFinish"),
    };
  }

  function buildInspectionReportExportPayload() {
    saveMeta();
    const meta = collectReportMeta();
    return {
      part_number: meta.partNumber,
      part_name: meta.partName,
      revision: meta.revision,
      material: meta.material,
      mass: meta.mass,
      finish: meta.finish,
      measured_col_count: measuredColCount,
      rows: rows.map(function (row) {
        return {
          sno: row.sno,
          balloon_number: row.balloonNumber,
          reference_location: row.referenceLocation,
          nominal: row.nominal || "",
          tol_low: formatTolDisplay(row.tolLow),
          tol_high: formatTolDisplay(row.tolHigh),
          instrument: row.instrument || "",
          instrument_id: row.instrumentId || "",
          measured: row.measured.slice(),
          remarks: row.remarks || "",
        };
      }),
    };
  }

  function downloadBlob(blob, filename) {
    const a = document.createElement("a");
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  async function downloadInspectionReport() {
    if (!rows.length) {
      alert("No balloon rows in this report. Run auto ballooning and open Inspection report again.");
      return;
    }
    const payload = buildInspectionReportExportPayload();
    const base =
      (payload.part_number || "inspection_report").replace(/[^\w\-]+/g, "_") ||
      "inspection_report";
    const filename = "InspectionReport_" + base + ".pdf";

    if (irDownloadReport) {
      irDownloadReport.disabled = true;
      irDownloadReport.textContent = "Generating PDF…";
    }

    try {
      const headers = { "Content-Type": "application/json" };
      const token = localStorage.getItem("balloon_token");
      if (token) headers["Authorization"] = "Bearer " + token;

      const paths = [
        "/api/v1/export-inspection-report-pdf",
        "/api/export-inspection-report-pdf",
      ];
      let blob = null;
      let lastStatus = 0;
      for (let i = 0; i < paths.length; i++) {
        const r = await fetch(window.location.origin + paths[i], {
          method: "POST",
          headers: headers,
          body: JSON.stringify(payload),
          credentials: "same-origin",
        });
        lastStatus = r.status;
        if (r.ok) {
          blob = await r.blob();
          break;
        }
        if (r.status !== 404) {
          let detail = "HTTP " + r.status;
          try {
            const j = await r.json();
            if (j && j.error) detail = j.error;
            else if (j && j.detail) detail = String(j.detail);
          } catch (e) {
            /* ignore */
          }
          throw new Error(detail);
        }
      }
      if (!blob) {
        throw new Error(
          "HTTP " +
            lastStatus +
            " — PDF export not available. Restart the backend server (python serve_balloon.py) and try again."
        );
      }
      downloadBlob(blob, filename);
    } catch (e) {
      alert("Could not download PDF: " + (e && e.message ? e.message : e));
    } finally {
      if (irDownloadReport) {
        irDownloadReport.disabled = false;
        irDownloadReport.textContent = "Download report";
      }
    }
  }

  function init() {
    let payload = null;
    try {
      if (window.InspectionStore && InspectionStore.getPayload) {
        payload = InspectionStore.getPayload();
      } else {
        const raw =
          localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY);
        if (raw) payload = JSON.parse(raw);
      }
    } catch (e) {
      payload = null;
    }

    if (!payload || !payload.detection) {
      irEmpty.hidden = false;
      irContent.hidden = true;
      return;
    }

    irEmpty.hidden = true;
    irContent.hidden = false;
    if (payload.detection && window.BalloonParse) {
      if (!payload.detection.inspection_report_confirmed_only) {
        if (BalloonParse.expandMultiplierBalloons) {
          BalloonParse.expandMultiplierBalloons(payload.detection);
        } else if (BalloonParse.pruneParentBalloonsWithSubs) {
          BalloonParse.pruneParentBalloonsWithSubs(payload.detection);
        }
      }
      if (BalloonParse.saveInspectionMetaFromDetection) {
        BalloonParse.saveInspectionMetaFromDetection(payload.detection);
      }
    }
    loadMeta();
    if (!measuredColCount || measuredColCount < MIN_MEASURED_COLS) {
      measuredColCount = DEFAULT_MEASURED_COLS;
    }
    rows = buildRowsFromPayload(payload);
    renderTable();
    if (irDownloadReport) irDownloadReport.disabled = false;

    ["irPartNumber", "irPartName", "irRevision", "irMaterial", "irMass", "irFinish"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", saveMeta);
    });
  }

  if (irDownloadReport) {
    irDownloadReport.addEventListener("click", downloadInspectionReport);
  }

  if (irDashboardBtn) {
    irDashboardBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      saveMeta();
      if (window.InspectionStore && InspectionStore.goToDashboard) {
        InspectionStore.goToDashboard();
      } else {
        window.location.href = "http://localhost:3000/dashboard";
      }
    });
  }

  if (irScrollLeft && irTableWrap) {
    irScrollLeft.addEventListener("click", function () {
      irTableWrap.scrollBy({ left: -280, behavior: "smooth" });
    });
  }
  if (irScrollRight && irTableWrap) {
    irScrollRight.addEventListener("click", function () {
      irTableWrap.scrollBy({ left: 280, behavior: "smooth" });
    });
  }

  const irEmptyAppLink = document.getElementById("irEmptyAppLink");
  if (irEmptyAppLink) {
    irEmptyAppLink.addEventListener("click", function (ev) {
      ev.preventDefault();
      var url =
        window.InspectionStore && InspectionStore.getBalloonAppUrl
          ? InspectionStore.getBalloonAppUrl()
          : window.location.origin + "/app";
      window.location.href = url;
    });
  }

  init();
})();

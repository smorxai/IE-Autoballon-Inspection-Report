/**
 * Inspection report payload storage — localStorage so new tabs (window.open) can read it.
 * Payloads are slimmed (no base64 crops) to stay under ~5MB quota.
 */
(function (global) {
  const PAYLOAD_KEY = "smorx_inspection_payload";
  const META_KEY = "smorx_inspection_meta";

  var BALLOON_ITEM_STRIP_KEYS = [
    "crop_preview_base64",
    "crop_save_base64",
    "raw_ocr",
  ];

  function slimBalloonItem(it) {
    if (!it || typeof it !== "object") return it;
    var out = {};
    var keys = [
      "balloon_number",
      "detection_index",
      "class_name",
      "confidence",
      "feature_type",
      "view_location",
      "inspection_method",
      "remarks",
      "nominal_value",
      "tolerance",
      "others",
      "detected_text",
      "confirmed",
      "region_name",
      "bbox_pixels",
      "ocr_engine",
      "confirmed",
    ];
    keys.forEach(function (k) {
      if (it[k] !== undefined && it[k] !== null && it[k] !== "") {
        var v = it[k];
        if (k === "others" && typeof v === "string" && v.length > 500) {
          v = v.slice(0, 500);
        }
        out[k] = v;
      }
    });
    BALLOON_ITEM_STRIP_KEYS.forEach(function (k) {
      if (out[k] !== undefined) delete out[k];
    });
    return out;
  }

  function slimInspectionPayload(data) {
    if (!data) return null;
    var det = data.detection || {};
    var items = [];
    if (global.BalloonParse && BalloonParse.itemsForTable) {
      items = BalloonParse.itemsForTable(det);
    } else {
      items = det.balloon_items || [];
    }
    items = items
      .filter(function (it) {
        if (global.BalloonParse && BalloonParse.balloonHasExtractedData) {
          return BalloonParse.balloonHasExtractedData(it);
        }
        return true;
      })
      .map(slimBalloonItem);

    var anns = (det.drawing_annotations || []).map(function (a) {
      return {
        id: a.id,
        BBox: a.BBox,
        TextPos: a.TextPos,
        AnnotationType: a.AnnotationType,
        display_id: a.display_id,
        parent_balloon_number: a.parent_balloon_number,
      };
    });

    return {
      ok: data.ok,
      job: data.job,
      detection: {
        width: det.width,
        height: det.height,
        count: items.length,
        balloon_items: items,
        drawing_annotations: anns,
        title_block_meta: det.title_block_meta || {},
        inspection_report_confirmed_only: false,
      },
    };
  }

  function trySetStorage(storage, key, json) {
    try {
      storage.setItem(key, json);
      return true;
    } catch (e) {
      return false;
    }
  }

  function getPayload() {
    try {
      var raw = localStorage.getItem(PAYLOAD_KEY);
      if (!raw) raw = sessionStorage.getItem(PAYLOAD_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setPayload(data) {
    var slim = slimInspectionPayload(data) || data;
    var json = JSON.stringify(slim);
    try {
      localStorage.removeItem(PAYLOAD_KEY);
    } catch (e) { /* ignore */ }
    var ok = trySetStorage(localStorage, PAYLOAD_KEY, json);
    trySetStorage(sessionStorage, PAYLOAD_KEY, json);
    if (!ok) {
      var err = new Error(
        "Could not save inspection data. Clear site data for this site and try again."
      );
      err.name = "QuotaExceededError";
      throw err;
    }
  }

  function getMeta() {
    try {
      var raw = localStorage.getItem(META_KEY);
      if (!raw) raw = sessionStorage.getItem(META_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setMeta(meta) {
    var json = JSON.stringify(meta);
    trySetStorage(localStorage, META_KEY, json);
    trySetStorage(sessionStorage, META_KEY, json);
  }

  var DASHBOARD_URL_KEY = "smorx_dashboard_url";
  var BALLOON_APP_URL_KEY = "smorx_balloon_app_url";
  var DEFAULT_DASHBOARD_URL = "http://localhost:3000/dashboard";

  function getDashboardUrl() {
    return localStorage.getItem(DASHBOARD_URL_KEY) || DEFAULT_DASHBOARD_URL;
  }

  function setDashboardUrl(url) {
    if (url) localStorage.setItem(DASHBOARD_URL_KEY, url);
  }

  function getBalloonAppUrl() {
    return localStorage.getItem(BALLOON_APP_URL_KEY) || (window.location.origin + "/app");
  }

  function setBalloonAppUrl(url) {
    if (url) localStorage.setItem(BALLOON_APP_URL_KEY, url);
  }

  function goToDashboard() {
    window.location.href = getDashboardUrl();
  }

  global.InspectionStore = {
    PAYLOAD_KEY: PAYLOAD_KEY,
    META_KEY: META_KEY,
    getPayload: getPayload,
    setPayload: setPayload,
    slimInspectionPayload: slimInspectionPayload,
    getMeta: getMeta,
    setMeta: setMeta,
    getDashboardUrl: getDashboardUrl,
    setDashboardUrl: setDashboardUrl,
    getBalloonAppUrl: getBalloonAppUrl,
    setBalloonAppUrl: setBalloonAppUrl,
    goToDashboard: goToDashboard,
  };
})(typeof window !== "undefined" ? window : globalThis);

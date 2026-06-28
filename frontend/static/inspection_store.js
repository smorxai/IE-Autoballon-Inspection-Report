/**
 * Inspection report payload storage — localStorage so new tabs (window.open) can read it.
 */
(function (global) {
  const PAYLOAD_KEY = "smorx_inspection_payload";
  const META_KEY = "smorx_inspection_meta";

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
    var json = JSON.stringify(data);
    localStorage.setItem(PAYLOAD_KEY, json);
    try {
      sessionStorage.setItem(PAYLOAD_KEY, json);
    } catch (e) { /* ignore quota */ }
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
    localStorage.setItem(META_KEY, json);
    try {
      sessionStorage.setItem(META_KEY, json);
    } catch (e) { /* ignore */ }
  }

  var DASHBOARD_URL_KEY = "smorx_dashboard_url";
  var BALLOON_APP_URL_KEY = "smorx_balloon_app_url";
  function getDashboardUrl() {
    return localStorage.getItem(DASHBOARD_URL_KEY) || (window.location.origin + "/app");
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
    getMeta: getMeta,
    setMeta: setMeta,
    getDashboardUrl: getDashboardUrl,
    setDashboardUrl: setDashboardUrl,
    getBalloonAppUrl: getBalloonAppUrl,
    setBalloonAppUrl: setBalloonAppUrl,
    goToDashboard: goToDashboard,
  };
})(typeof window !== "undefined" ? window : globalThis);

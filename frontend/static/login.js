(function () {
  "use strict";

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const msg           = document.getElementById("msg");

  const panelLogin    = document.getElementById("panelLogin");
  const panelRegister = document.getElementById("panelRegister");
  const panelSuccess  = document.getElementById("panelSuccess");
  const noAccountHint = document.getElementById("noAccountHint");

  const emailInput    = document.getElementById("email");
  const passwordInput = document.getElementById("password");

  const regFirstname  = document.getElementById("regFirstname");
  const regLastname   = document.getElementById("regLastname");
  const regEmail      = document.getElementById("regEmail");

  // ── Redirect if already logged in ────────────────────────────────────────
  fetch("/api/auth/me", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(function (me) {
      if (me && me.logged_in && !me.trial_expired) {
        window.location.href = "/app";
      }
      if (me && me.logged_in && me.trial_expired) {
        window.location.href = "/payment";
      }
    })
    .catch(function () {});

  // ── Helpers ───────────────────────────────────────────────────────────────
  function show(m, isSuccess) {
    msg.textContent = m || "";
    msg.style.color = isSuccess ? "#4ade80" : "#f87171";
  }

  function showPanel(name) {
    panelLogin.style.display    = name === "login"    ? "" : "none";
    panelRegister.style.display = name === "register" ? "" : "none";
    panelSuccess.style.display  = name === "success"  ? "" : "none";
    show("");
  }

  /**
   * POST JSON to *path*.
   * Returns { ok, status, data } always — never throws.
   */
  async function apiPost(path, body) {
    try {
      const r    = await fetch(path, {
        method:      "POST",
        headers:     { "Content-Type": "application/json" },
        credentials: "same-origin",
        body:        JSON.stringify(body),
      });
      const text = await r.text();
      let data;
      try { data = JSON.parse(text); } catch (e) { data = { detail: text }; }
      return { ok: r.ok, status: r.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { detail: "Network error" } };
    }
  }

  function extractError(data) {
    if (!data) return "Request failed";
    const d = data.detail;
    if (d == null)             return data.error || data.message || "Error";
    if (typeof d === "string") return d;
    if (Array.isArray(d))      return d.map(x => (typeof x === "string" ? x : x.msg || JSON.stringify(x))).join(" ");
    if (d && typeof d === "object" && d.msg) return String(d.msg);
    try { return JSON.stringify(d); } catch (e) { return String(d); }
  }

  // ── LOGIN ─────────────────────────────────────────────────────────────────
  document.getElementById("btnLogin").addEventListener("click", async function () {
    show("");
    noAccountHint.style.display = "none";

    const email    = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email)    { show("Please enter your email address"); return; }
    if (!password) { show("Please enter your password");      return; }

    const btn = this;
    btn.disabled    = true;
    btn.textContent = "Logging in…";

    const { ok, status, data } = await apiPost("/api/auth/login", { email, password });

    btn.disabled    = false;
    btn.textContent = "Log in";

    if (ok) {
      if (data.requires_password_change) { window.location.href = "/change-password"; } else { window.location.href = "/app"; }
      return;
    }

    if (status === 404) { noAccountHint.style.display = ""; }

    show(extractError(data));
  });

  // Allow pressing Enter in the password field to trigger login
  passwordInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") document.getElementById("btnLogin").click();
  });

  // ── SHOW REGISTER PANEL ───────────────────────────────────────────────────
  document.getElementById("btnShowRegister").addEventListener("click", function () {
    regEmail.value = emailInput.value.trim();
    showPanel("register");
    regFirstname.focus();
  });

  // ── BACK TO LOGIN ─────────────────────────────────────────────────────────
  document.getElementById("btnBackToLogin").addEventListener("click", function () {
    showPanel("login");
  });

  // ── REGISTER ──────────────────────────────────────────────────────────────
  document.getElementById("btnRegister").addEventListener("click", async function () {
    show("");

    const firstname = regFirstname.value.trim();
    const lastname  = regLastname.value.trim();
    const email     = regEmail.value.trim();

    if (!firstname) { show("Please enter your first name"); return; }
    if (!lastname)  { show("Please enter your last name");  return; }
    if (!email)     { show("Please enter your email");      return; }

    const btn = this;
    btn.disabled    = true;
    btn.textContent = "Creating account…";

    const { ok, data } = await apiPost("/api/auth/register", { email, firstname, lastname });

    btn.disabled    = false;
    btn.textContent = "Create account";

    if (ok) { showPanel("success"); document.getElementById("successMsg").textContent = "Check your email for a temporary password."; return; }

    show(extractError(data));
  });

  // ── BACK FROM SUCCESS ─────────────────────────────────────────────────────
  document.getElementById("btnGoLogin").addEventListener("click", function () {
    showPanel("login");
    noAccountHint.style.display = "none";
  });

})();

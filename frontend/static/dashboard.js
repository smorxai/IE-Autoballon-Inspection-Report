(function () {
  "use strict";

  function getToken() {
    return window.BalloonAuth && BalloonAuth.getToken ? BalloonAuth.getToken() : null;
  }

  function authHeaders() {
    var h = { "Content-Type": "application/json" };
    var t = getToken();
    if (t) h.Authorization = "Bearer " + t;
    return h;
  }

  // Show user's name in the welcome heading; reveal Admin Panel for super_admin
  function loadWelcome() {
    var t = getToken();
    if (!t) return;
    fetch("/auth/me", { headers: { Authorization: "Bearer " + t } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (me) {
        if (!me) return;
        var name = me.full_name || me.username || me.email || "Engineer";
        var el = document.getElementById("dashWelcome");
        if (el) el.textContent = "Welcome, " + name;
        if (me.role === "super_admin") {
          var adminLink = document.getElementById("dashAdminLink");
          if (adminLink) adminLink.hidden = false;
        }
      })
      .catch(function () {});
  }

  // Load recent drawing sessions
  function loadSessions() {
    var grid = document.getElementById("dashSessionGrid");
    if (!grid) return;

    fetch("/activities", { headers: authHeaders() })
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/login"; return null; }
        return r.ok ? r.json() : null;
      })
      .then(function (sessions) {
        if (!sessions) return;
        grid.innerHTML = "";
        if (!sessions.length) {
          var p = document.createElement("p");
          p.className = "dash-empty";
          p.textContent = "No sessions yet. Open the app and run auto ballooning to get started.";
          grid.appendChild(p);
          return;
        }
        sessions.forEach(function (s) {
          var card = document.createElement("div");
          card.className = "dash-session-card";

          if (s.drawing_preview_b64) {
            var img = document.createElement("img");
            img.className = "dash-session-thumb";
            img.src = s.drawing_preview_b64;
            img.alt = s.filename || "Drawing";
            card.appendChild(img);
          } else {
            var ph = document.createElement("div");
            ph.className = "dash-thumb-placeholder";
            ph.textContent = "📄";
            card.appendChild(ph);
          }

          var name = document.createElement("div");
          name.className = "dash-session-name";
          name.textContent = s.filename || "Drawing";
          card.appendChild(name);

          var meta = document.createElement("div");
          meta.className = "dash-session-meta";
          var balloons = (s.balloon_count || 0) + " balloon" + (s.balloon_count === 1 ? "" : "s");
          var date = s.created_at ? new Date(s.created_at).toLocaleDateString() : "";
          meta.textContent = balloons + (date ? " · " + date : "");
          card.appendChild(meta);

          grid.appendChild(card);
        });
      })
      .catch(function () {
        if (grid) grid.innerHTML = '<p class="dash-empty">Could not load sessions.</p>';
      });
  }

  // Logout
  var logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      var t = getToken();
      if (t) {
        fetch("/auth/logout", {
          method: "POST",
          headers: { Authorization: "Bearer " + t },
        }).catch(function () {});
      }
      if (window.BalloonAuth && BalloonAuth.setToken) BalloonAuth.setToken(null);
      window.location.href = "/login";
    });
  }

  loadWelcome();
  loadSessions();
})();

(function () {
  "use strict";

  var msg = document.getElementById("msg");
  var orgBody = document.getElementById("orgBody");
  var engBody = document.getElementById("engBody");
  var orgSelect = document.getElementById("engTenant");
  var modal = document.getElementById("tempPwdModal");
  var modalEmail = document.getElementById("modalEmail");
  var modalPwd = document.getElementById("modalPwd");
  var modalTenant = document.getElementById("modalTenant");

  function show(m, isSuccess) {
    msg.textContent = m || "";
    msg.style.color = isSuccess ? "#4ade80" : "#f87171";
  }

  async function apiGet(path) {
    var r = await fetch(path, { headers: BalloonAuth.authHeaders({ "Content-Type": undefined }) });
    var data = await r.json().catch(function () { return {}; });
    if (BalloonAuth.redirectFromAuthError(r.status, data)) return null;
    if (!r.ok) throw new Error(BalloonAuth.extractError(data));
    return data;
  }

  async function apiPost(path, body) {
    var r = await fetch(path, {
      method: "POST",
      headers: BalloonAuth.authHeaders(),
      body: JSON.stringify(body),
    });
    var data = await r.json().catch(function () { return {}; });
    if (BalloonAuth.redirectFromAuthError(r.status, data)) return null;
    if (!r.ok) throw new Error(BalloonAuth.extractError(data));
    return data;
  }

  async function apiDelete(path) {
    var r = await fetch(path, {
      method: "DELETE",
      headers: BalloonAuth.authHeaders({ "Content-Type": undefined }),
    });
    var data = await r.json().catch(function () { return {}; });
    if (BalloonAuth.redirectFromAuthError(r.status, data)) return null;
    if (!r.ok) throw new Error(BalloonAuth.extractError(data));
    return data;
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleDateString(); } catch (e) { return iso; }
  }

  function accessLabel(u) {
    if (!u.is_active) return "No access (inactive)";
    var parts = [];
    if (u.can_read) parts.push("read");
    if (u.can_write) parts.push("write");
    if (u.can_delete) parts.push("delete");
    if (!parts.length) return "Active, no permissions";
    return parts.join(", ");
  }

  function fillOrgSelect(orgs) {
    orgSelect.innerHTML = '<option value="">Select organization…</option>';
    orgs.forEach(function (o) {
      var opt = document.createElement("option");
      opt.value = o.tenant_id;
      opt.textContent = o.name + " (" + o.tenant_id + ")";
      orgSelect.appendChild(opt);
    });
  }

  async function loadOrgs() {
    var orgs = await apiGet("/admin/organizations");
    if (!orgs) return;
    orgBody.innerHTML = "";
    orgs.forEach(function (o) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td><strong>" + o.name + "</strong></td>" +
        "<td class=\"mono\">" + o.tenant_id + "</td>" +
        "<td>" + (o.engineer_count || 0) + "</td>" +
        "<td>" + (o.subscription_status || "—") + "</td>" +
        "<td>" + fmtDate(o.trial_end_date) + "</td>";
      orgBody.appendChild(tr);
    });
    fillOrgSelect(orgs);
  }

  async function loadEngineers() {
    var engineers = await apiGet("/admin/engineers");
    if (!engineers) return;
    engBody.innerHTML = "";
    engineers.forEach(function (u) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + (u.name || "") + "</td>" +
        "<td>" + (u.email || "") + "</td>" +
        "<td class=\"mono\">" + (u.username || "—") + "</td>" +
        "<td>" + accessLabel(u) + (u.is_temp_password ? " · temp pwd" : "") + "</td>" +
        "<td>" +
        "<button type=\"button\" class=\"btn-link btn-grant\" data-id=\"" + u.id + "\">Grant access</button> " +
        "<button type=\"button\" class=\"btn-link btn-del\" data-id=\"" + u.id + "\" data-email=\"" + u.email + "\">Delete</button>" +
        "</td>";
      engBody.appendChild(tr);
    });
    engBody.querySelectorAll(".btn-grant").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.getAttribute("data-id");
        try {
          await apiPatch("/admin/users/" + id + "/permissions", {
            is_active: true,
            can_read: true,
            can_write: true,
            can_delete: true,
          });
          show("Full access granted. User can log in and use the app.", true);
          loadEngineers();
          loadPermissions();
        } catch (e) {
          show(String(e.message || e));
        }
      });
    });
    engBody.querySelectorAll(".btn-del").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.getAttribute("data-id");
        var email = btn.getAttribute("data-email");
        if (!confirm("Delete engineer " + email + "?")) return;
        try {
          await apiDelete("/admin/engineers/" + id);
          show("Engineer deleted.", true);
          loadEngineers();
          loadOrgs();
        } catch (e) {
          show(String(e.message || e));
        }
      });
    });
  }

  document.getElementById("btnCreateOrg").addEventListener("click", async function () {
    show("");
    var name = document.getElementById("orgName").value.trim();
    if (!name) { show("Enter organization name"); return; }
    this.disabled = true;
    try {
      var data = await apiPost("/admin/organizations", { name: name });
      if (!data) return;
      show('Organization "' + data.name + '" created (7-day trial). tenant_id: ' + data.tenant_id, true);
      document.getElementById("orgName").value = "";
      loadOrgs();
    } catch (e) {
      show(String(e.message || e));
    } finally {
      this.disabled = false;
    }
  });

  document.getElementById("btnCreateEng").addEventListener("click", async function () {
    show("");
    var name = document.getElementById("engName").value.trim();
    var email = document.getElementById("engEmail").value.trim();
    var tenant_id = orgSelect.value;
    if (!name) { show("Enter engineer name"); return; }
    if (!email) { show("Enter engineer email"); return; }
    if (!tenant_id) { show("Select an organization"); return; }
    this.disabled = true;
    try {
      var data = await apiPost("/admin/engineers", { name: name, email: email, tenant_id: tenant_id });
      if (!data) return;
      modalEmail.textContent = data.email;
      modalPwd.textContent = data.temp_password;
      modalTenant.textContent = data.tenant_id;
      modal.style.display = "";
      show("Engineer created. Enable access in User access control before they can log in.", true);
      document.getElementById("engName").value = "";
      document.getElementById("engEmail").value = "";
      orgSelect.value = "";
      loadEngineers();
      loadOrgs();
      loadPermissions();
    } catch (e) {
      show(String(e.message || e));
    } finally {
      this.disabled = false;
    }
  });

  document.getElementById("btnCloseModal").addEventListener("click", function () {
    modal.style.display = "none";
    show("Share the temporary password securely. Grant access before the engineer logs in.", true);
  });

  document.getElementById("btnLogout").addEventListener("click", function () {
    BalloonAuth.setToken(null);
    window.location.href = "/login";
  });

  async function apiPatch(path, body) {
    var r = await fetch(path, {
      method: "PATCH",
      headers: BalloonAuth.authHeaders(),
      body: JSON.stringify(body),
    });
    var data = await r.json().catch(function () { return {}; });
    if (BalloonAuth.redirectFromAuthError(r.status, data)) return null;
    if (!r.ok) throw new Error(BalloonAuth.extractError(data));
    return data;
  }

  async function loadPermissions() {
    var permBody = document.getElementById("permBody");
    if (!permBody) return;
    var users = await apiGet("/admin/users");
    if (!users) return;
    permBody.innerHTML = "";
    users.forEach(function (u) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + (u.name || "") + "</td>" +
        "<td class=\"mono\">" + (u.username || "—") + "</td>" +
        "<td>" + (u.email || "") + "</td>" +
        "<td><input type=\"checkbox\" class=\"perm-read\" " + (u.can_read ? "checked" : "") + " /></td>" +
        "<td><input type=\"checkbox\" class=\"perm-write\" " + (u.can_write ? "checked" : "") + " /></td>" +
        "<td><input type=\"checkbox\" class=\"perm-delete\" " + (u.can_delete ? "checked" : "") + " /></td>" +
        "<td><input type=\"checkbox\" class=\"perm-active\" " + (u.is_active ? "checked" : "") + " /></td>" +
        "<td>" +
        "<button type=\"button\" class=\"btn-link btn-grant-perm\" data-id=\"" + u.id + "\">Grant full</button> " +
        "<button type=\"button\" class=\"btn-link btn-save-perm\" data-id=\"" + u.id + "\">Save</button>" +
        "</td>";
      permBody.appendChild(tr);
    });
    permBody.querySelectorAll(".btn-grant-perm").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var tr = btn.closest("tr");
        tr.querySelector(".perm-read").checked = true;
        tr.querySelector(".perm-write").checked = true;
        tr.querySelector(".perm-delete").checked = true;
        tr.querySelector(".perm-active").checked = true;
        btn.nextElementSibling.click();
      });
    });
    permBody.querySelectorAll(".btn-save-perm").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var tr = btn.closest("tr");
        var id = btn.getAttribute("data-id");
        try {
          await apiPatch("/admin/users/" + id + "/permissions", {
            can_read: tr.querySelector(".perm-read").checked,
            can_write: tr.querySelector(".perm-write").checked,
            can_delete: tr.querySelector(".perm-delete").checked,
            is_active: tr.querySelector(".perm-active").checked,
          });
          show("Permissions updated for user.", true);
          loadEngineers();
        } catch (e) {
          show(String(e.message || e));
        }
      });
    });
  }

  BalloonAuth.requirePageAccess({ superAdminOnly: true }).then(function (ctx) {
    if (!ctx) return;
    loadOrgs();
    loadEngineers();
    loadPermissions();
  }).catch(function () {
    window.location.href = "/login";
  });
})();

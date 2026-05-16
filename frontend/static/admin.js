(function () {
  const msg = document.getElementById("msg");
  const body = document.getElementById("userBody");

  async function load() {
    const r = await fetch("/api/admin/users", { credentials: "same-origin" });
    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      msg.textContent = text.slice(0, 200);
      return;
    }
    if (!r.ok) {
      msg.textContent = data.detail || "Forbidden";
      return;
    }
    body.innerHTML = "";
    (data.users || []).forEach(function (u) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + (u.email || "") + "</td>" +
        "<td>" + (u.role || "") + "</td>" +
        "<td>" + (u.paid ? "yes" : "no") + "</td>" +
        "<td>" + (u.trial_started_at || "—") + "</td>";
      body.appendChild(tr);
    });
  }

  document.getElementById("btnPaid").addEventListener("click", async function () {
    msg.textContent = "";
    const email = document.getElementById("paidEmail").value.trim();
    const r = await fetch("/api/admin/set-paid", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email: email, paid: true }),
    });
    const data = await r.json().catch(function () { return {}; });
    if (!r.ok) {
      msg.textContent = data.detail || "Error";
      return;
    }
    load();
  });

  load();
})();

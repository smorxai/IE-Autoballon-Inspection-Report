(function () {
  "use strict";

  var msg = document.getElementById("msg");
  var btnPay = document.getElementById("btnPay");
  var panelSuccess = document.getElementById("panelSuccess");
  var panelMain = document.getElementById("panelMain");
  var planPrice = document.getElementById("planPrice");
  var userEmail = document.getElementById("userEmail");

  var currentUser = null;

  function show(m, isSuccess) {
    msg.textContent = m || "";
    msg.style.color = isSuccess ? "#4ade80" : "#f87171";
  }

  function loadRazorpayScript() {
    return new Promise(function (resolve) {
      if (window.Razorpay) return resolve(true);
      var script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = function () { resolve(true); };
      script.onerror = function () { resolve(false); };
      document.body.appendChild(script);
    });
  }

  BalloonAuth.requirePageAccess({ skipTrialCheck: true }).then(function (ctx) {
    if (!ctx || !ctx.me) return;
    currentUser = ctx.me;
    if (userEmail) userEmail.textContent = currentUser.email || "";
    if (currentUser.role === "super_admin") {
      window.location.href = "/admin";
    }
    return BalloonAuth.fetchTrialStatus();
  }).then(function (ts) {
    if (!ts) return;
    if (ts.subscription_status === "active") {
      window.location.href = "/app";
    }
  }).catch(function () {
    window.location.href = "/login";
  });

  fetch("/api/v1/auth-config").then(function (r) { return r.json(); }).then(function (cfg) {
    if (planPrice && cfg.plan_amount_inr) {
      planPrice.textContent = "₹" + cfg.plan_amount_inr;
    }
  }).catch(function () {});

  btnPay.addEventListener("click", async function () {
    show("");
    btnPay.disabled = true;
    btnPay.textContent = "Opening payment…";

    var loaded = await loadRazorpayScript();
    if (!loaded) {
      show("Could not load Razorpay. Check your internet connection.");
      btnPay.disabled = false;
      btnPay.textContent = "Pay with Razorpay";
      return;
    }

    try {
      var r = await fetch("/payment/create-order", {
        method: "POST",
        headers: BalloonAuth.authHeaders(),
      });
      var data = await r.json();
      if (!r.ok) {
        if (BalloonAuth.redirectFromAuthError(r.status, data)) return;
        show(BalloonAuth.extractError(data));
        btnPay.disabled = false;
        btnPay.textContent = "Pay with Razorpay";
        return;
      }

      var options = {
        key: data.key,
        amount: data.amount,
        currency: data.currency,
        name: "SmorX.ai",
        description: "Auto Ballooning — Professional Plan",
        order_id: data.order_id,
        prefill: { email: (currentUser && currentUser.email) || "" },
        theme: { color: "#2563eb" },
        handler: async function (response) {
          var vr = await fetch("/payment/verify", {
            method: "POST",
            headers: BalloonAuth.authHeaders(),
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });
          var vData = await vr.json();
          if (!vr.ok) {
            show(BalloonAuth.extractError(vData));
            btnPay.disabled = false;
            btnPay.textContent = "Pay with Razorpay";
            return;
          }
          panelMain.style.display = "none";
          panelSuccess.style.display = "";
          setTimeout(function () { window.location.href = "/app"; }, 2500);
        },
        modal: {
          ondismiss: function () {
            btnPay.disabled = false;
            btnPay.textContent = "Pay with Razorpay";
          },
        },
      };

      var rzp = new window.Razorpay(options);
      rzp.on("payment.failed", function (response) {
        show("Payment failed: " + ((response.error && response.error.description) || "Please try again."));
        btnPay.disabled = false;
        btnPay.textContent = "Pay with Razorpay";
      });
      rzp.open();
    } catch (e) {
      show("Network error. Please try again.");
      btnPay.disabled = false;
      btnPay.textContent = "Pay with Razorpay";
    }
  });
})();

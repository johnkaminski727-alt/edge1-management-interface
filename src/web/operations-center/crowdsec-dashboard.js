"use strict";

(() => {
  const grid = document.getElementById("crowdsec-cards");
  const freshness = document.getElementById("crowdsec-freshness");
  const refresh = document.getElementById("crowdsec-refresh");

  if (!grid || !freshness || !refresh) return;
  let lastObservedAt = null;

  const escapeText = value => String(value ?? "Unknown")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function card(label, value, state, detail) {
    const className = state === "good" ? "good" :
      state === "warning" ? "warning" : "neutral";

    return '<article class="card ' + className + '">' +
      '<div class="label">' + escapeText(label) + '</div>' +
      '<div class="value">' + escapeText(value) + '</div>' +
      '<small>' + escapeText(detail || "") + '</small>' +
      '</article>';
  }

  function unavailable(message) {
    freshness.textContent = message;
    grid.innerHTML = card(
      "CrowdSec observation", "Unavailable", "warning",
      "No current protection claim can be made from this dashboard."
    );
  }

  function updateObservationAge() {
    if (lastObservedAt === null) return;
    const observed = Date.parse(lastObservedAt);
    const seconds = Math.floor((Date.now() - observed) / 1000);
    const current = Number.isFinite(observed) && seconds >= -60 && seconds <= 300;
    freshness.textContent = current
      ? "Fresh observation: " + Math.max(0, seconds) + " seconds old"
      : "STALE OR INVALID — current protection is unverified";
    if (!current) {
      grid.innerHTML = card("CrowdSec observation", "Not current", "warning",
        "Cached observations have expired; refresh to verify current state.");
    }
  }

  async function loadCrowdSec() {
    refresh.disabled = true;
    try {
      const response = await fetch(
        "./crowdsec-status.json",
        { cache: "no-store" }
      );
      if (!response.ok) throw Error("Snapshot unavailable");

      const data = await response.json();
      if (data.schema_version !== "wwcx.crowdsec-observation.v1") {
        throw Error("Unsupported snapshot format");
      }

      lastObservedAt = data.generated_at;
      const observedAt = Date.parse(data.generated_at);
      const ageSeconds = Math.max(
        0, Math.floor((Date.now() - observedAt) / 1000)
      );
      const fresh = Number.isFinite(observedAt) &&
        observedAt <= Date.now() + 60000 &&
        ageSeconds <= 300;

      freshness.textContent = fresh
        ? "Fresh observation: " + ageSeconds + " seconds old"
        : "STALE OR INVALID — current protection is unverified";

      const hook = (label, value, detail) => {
        const verified = value?.verified === true;
        return card(
          label,
          !fresh ? "Not current" :
            verified ? "Active" : "Unverified",
          fresh && verified ? "good" : "warning",
          detail
        );
      };

      const count = (label, value) => card(
        label,
        fresh && value?.available === true &&
          Number.isInteger(value.count)
          ? value.count.toLocaleString()
          : "Unavailable",
        fresh && value?.available === true
          ? "neutral" : "warning",
        "Observed blacklist entries; not a feed-freshness guarantee."
      );

      const counters = data.forward?.ipv4?.drop_packets;
      const counterLabel = Array.isArray(counters) &&
        counters.length === 2 && fresh
        ? counters.map(Number).join(" outbound / ") + " inbound"
        : "Unavailable";

      const bouncer = data.services?.[
        "crowdsec-firewall-bouncer"
      ];
      const bouncerOK = fresh &&
        bouncer?.active === true &&
        bouncer?.enabled === true;

      grid.innerHTML = [
        hook("IPv4 INPUT", data.input?.ipv4,
          "Traffic destined for Edge1"),
        hook("IPv6 INPUT", data.input?.ipv6,
          "Traffic destined for Edge1"),
        hook("IPv4 VPN FORWARD", data.forward?.ipv4,
          "WireGuard and internet traffic"),
        card("IPv6 VPN forwarding", "Not deployed",
          "neutral", "IPv6 forwarding remains disabled"),
        count("IPv4 blacklist", data.blacklists?.ipv4),
        count("IPv6 blacklist", data.blacklists?.ipv6),
        card("Forward drop counters", counterLabel,
          fresh ? "neutral" : "warning",
          "Cumulative since firewall rule activation"),
        card("CrowdSec bouncer",
          !fresh ? "Not current" :
          bouncerOK ? "Running" : "Needs attention",
          bouncerOK ? "good" : "warning",
          "Service and startup registration")
      ].join("");
      updateObservationAge();
    } catch (error) {
      lastObservedAt = null;
      unavailable("Snapshot unavailable or invalid");
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", loadCrowdSec);
  loadCrowdSec();
  setInterval(loadCrowdSec, 60000);
  setInterval(updateObservationAge, 10000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") updateObservationAge();
  });
})();

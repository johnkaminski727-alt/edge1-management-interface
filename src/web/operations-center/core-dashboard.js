"use strict";

(() => {
  const grid = document.getElementById("core-cards");
  const freshness = document.getElementById("core-freshness");
  const refresh = document.getElementById("core-refresh");

  if (!grid || !freshness || !refresh) return;

  const escapeText = value => String(value ?? "Unknown")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function card(label, value, state, detail) {
    const css = state === "good" ? "good" :
      state === "warning" ? "warning" : "neutral";

    return '<article class="card ' + css + '">' +
      '<div class="label">' + escapeText(label) + '</div>' +
      '<div class="value">' + escapeText(value) + '</div>' +
      '<small>' + escapeText(detail || "") + '</small>' +
      '</article>';
  }

  function unavailable() {
    freshness.textContent =
      "No current health observation is available";
    grid.innerHTML = card(
      "System health", "Unavailable", "warning",
      "The monitoring snapshot could not be verified."
    );
  }

  async function loadCore() {
    refresh.disabled = true;

    try {
      const response = await fetch(
        "./core-status.json", { cache: "no-store" }
      );
      if (!response.ok) throw Error("Snapshot unavailable");

      const data = await response.json();
      if (data.schema_version !== "wwcx.core-observation.v1" ||
          data.read_only !== true ||
          data.traffic_controls_changed !== false) {
        throw Error("Unsupported observation");
      }

      const generated = Date.parse(data.generated_at);
      const seconds = Math.floor(
        (Date.now() - generated) / 1000
      );
      const fresh = Number.isFinite(generated) &&
        seconds >= -60 && seconds <= 300;

      freshness.textContent = fresh
        ? "Last observed " + Math.max(0, seconds) +
          " seconds ago"
        : "STALE — current health cannot be confirmed";

      const services = data.services || {};
      const names = Object.keys(services);
      const active = names.filter(
        name => services[name]?.state === "active"
      ).length;

      function service(label, name) {
        const entry = services[name];
        const running = fresh &&
          entry?.state === "active";
        return card(
          label,
          !fresh ? "Not current" :
            running ? "Running" :
            entry?.state || "Unknown",
          running ? "good" : "warning",
          "Observed systemd service state"
        );
      }

      function iface(label, name) {
        const entry = data.interfaces?.[name];
        const up = fresh && entry?.up === true;
        return card(
          label,
          !fresh ? "Not current" :
            entry?.available !== true ? "Unavailable" :
            up ? "Up" : "Down",
          up ? "good" : "warning",
          "Interface state; not an end-to-end test"
        );
      }

      grid.innerHTML = [
        card(
          "Core services",
          fresh ? active + " / " + names.length :
            "Not current",
          fresh && active === names.length &&
            names.length === 11 ? "good" : "warning",
          "Observed active services"
        ),
        iface("Internet interface", "ens3"),
        iface("WireGuard interface", "wg0"),
        service("WireGuard VPN", "wg-quick@wg0"),
        service("AdGuard Home", "AdGuardHome"),
        service("Unbound DNS", "unbound"),
        service("Operations API", "edge1-operations-api"),
        card(
          "IPv4 forwarding",
          !fresh ? "Not current" :
            data.routing?.ipv4_forwarding === 1
              ? "Enabled" : "Not enabled",
          fresh && data.routing?.ipv4_forwarding === 1
            ? "good" : "warning",
          "Kernel routing setting"
        ),
        card(
          "IPv6 forwarding",
          !fresh ? "Not current" :
            data.routing?.ipv6_forwarding === 0
              ? "Disabled" : "Enabled / unknown",
          fresh && data.routing?.ipv6_forwarding === 0
            ? "neutral" : "warning",
          "Routed IPv6 is not deployed"
        )
      ].join("");

    } catch (error) {
      console.warn("Core observation:", error);
      unavailable();
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", loadCore);
  loadCore();
  setInterval(loadCore, 60000);
})();

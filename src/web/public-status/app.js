"use strict";

const STATUS_URL = "./status.json";
const allowedStates = new Set(["healthy", "limited", "attention", "unavailable"]);
const allowedFreshness = new Set(["fresh", "aging", "stale", "unknown"]);
const allowedCategories = new Set(["security", "network_defense", "operations"]);

const escapeHtml = value => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const categoryLabel = value => ({
  security: "Security",
  network_defense: "Network defense",
  operations: "Operations",
}[value] || "Status");

function componentCard(item) {
  const category = allowedCategories.has(item?.component_category)
    ? item.component_category
    : "operations";
  const state = allowedStates.has(item?.component_state)
    ? item.component_state
    : "unavailable";
  const freshness = allowedFreshness.has(item?.freshness_bucket)
    ? item.freshness_bucket
    : "unknown";
  const count = Number.isInteger(item?.bounded_count)
    && item.bounded_count >= 0
    && item.bounded_count <= 999
    ? item.bounded_count
    : 0;
  return `<article class="card ${escapeHtml(state)}"><div class="label">${escapeHtml(categoryLabel(category))}</div><div class="value">${escapeHtml(state)}</div><small>Count ${count}; freshness ${escapeHtml(freshness)}.</small></article>`;
}

function renderStatus(documentValue) {
  const state = allowedStates.has(documentValue?.overall_state)
    ? documentValue.overall_state
    : "unavailable";
  const overall = document.getElementById("overall");
  overall.textContent = `Overall: ${state}`;
  overall.className = `status ${state}`;

  const components = Array.isArray(documentValue?.component_category)
    ? documentValue.component_category
    : [];
  document.getElementById("components").innerHTML = components.map(componentCard).join("")
    || componentCard({});

  const notice = typeof documentValue?.maintenance_notice === "string"
    ? documentValue.maintenance_notice.trim()
    : "";
  document.getElementById("maintenance-panel").hidden = !notice;
  document.getElementById("maintenance").textContent = notice;
  document.getElementById("checked").textContent = `Last checked: ${new Date().toLocaleString()}`;
}

async function loadStatus() {
  try {
    const response = await fetch(STATUS_URL, {
      cache: "no-store",
      credentials: "omit",
      referrerPolicy: "no-referrer",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const value = await response.json();
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("Invalid status document");
    }
    renderStatus(value);
  } catch (error) {
    console.warn("Minimized status unavailable", error);
    renderStatus({overall_state: "unavailable", component_category: []});
  }
}

loadStatus();
setInterval(loadStatus, 60000);

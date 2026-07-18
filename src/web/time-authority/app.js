(function () {
  "use strict";

  const API_PATH = "/api/time-authority/summary?limit=2000";
  const FIXTURE_PATH = "./fixtures/baseline-summary.json";
  const state = { payload: null, observer: "all" };

  const elements = {
    cards: document.querySelector("#summary-cards"),
    chart: document.querySelector("#rtt-chart"),
    rows: document.querySelector("#measurement-rows"),
    filter: document.querySelector("#observer-filter"),
    mode: document.querySelector("#mode-pill"),
    generated: document.querySelector("#generated-at"),
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function number(value, digits) {
    return value == null || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(digits);
  }

  function selected(records) {
    return state.observer === "all" ? records : records.filter((item) => item.observer_id === state.observer);
  }

  function renderCards() {
    const observers = state.payload.observers || [];
    elements.cards.innerHTML = observers.map((item) => `
      <article class="summary-card">
        <p class="eyebrow">${escapeHtml(item.observer_id)}</p>
        <h2>${escapeHtml(item.observer_host)}</h2>
        <dl>
          <div><dt>Reachable</dt><dd>${escapeHtml(item.reachable_sources)}/${escapeHtml(item.total_sources)}</dd></div>
          <div><dt>Average RTT</dt><dd>${number(item.average_rtt_ms, 2)} ms</dd></div>
          <div><dt>Fastest</dt><dd>${number(item.minimum_rtt_ms, 2)} ms</dd></div>
        </dl>
      </article>
    `).join("");
  }

  function renderFilter() {
    const options = (state.payload.observers || []).map((item) =>
      `<option value="${escapeHtml(item.observer_id)}">${escapeHtml(item.observer_host)}</option>`
    ).join("");
    elements.filter.innerHTML = `<option value="all">Both observers</option>${options}`;
    elements.filter.value = state.observer;
  }

  function renderChart() {
    const records = selected((state.payload.latest || []).filter((item) => item.reachable && item.rtt_ms != null));
    if (!records.length) {
      elements.chart.innerHTML = '<p class="empty-state">No reachable sources for this observer.</p>';
      return;
    }
    const width = 920;
    const rowHeight = 34;
    const left = 210;
    const right = 80;
    const height = 45 + records.length * rowHeight;
    const maximum = Math.max(...records.map((item) => Number(item.rtt_ms)), 1);
    const palette = { edge1: "#1f5f99", "shared-host": "#a05a20" };
    const bars = records.map((item, index) => {
      const y = 28 + index * rowHeight;
      const barWidth = (Number(item.rtt_ms) / maximum) * (width - left - right);
      const label = `${item.observer_id} · ${item.server_name}`;
      return `
        <text x="${left - 10}" y="${y + 15}" text-anchor="end">${escapeHtml(label)}</text>
        <rect x="${left}" y="${y}" width="${Math.max(barWidth, 2)}" height="20" rx="3" fill="${palette[item.observer_id] || "#5d6b7a"}"></rect>
        <text x="${left + barWidth + 8}" y="${y + 15}" class="value">${number(item.rtt_ms, 2)} ms</text>
      `;
    }).join("");
    elements.chart.innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">${bars}</svg>`;
  }

  function renderTable() {
    const records = selected(state.payload.latest || []);
    elements.rows.innerHTML = records.map((item) => {
      const ok = item.reachable && item.expectation_ok !== false;
      const status = item.reachable ? (ok ? "Healthy" : "Unexpected") : "Unreachable";
      return `<tr>
        <td>${escapeHtml(item.observer_id)}</td>
        <td><strong>${escapeHtml(item.server_name)}</strong></td>
        <td><code>${escapeHtml(item.resolved_address || "—")}</code></td>
        <td>${escapeHtml(item.stratum == null ? "—" : item.stratum)}</td>
        <td>${escapeHtml(item.refid || "—")}</td>
        <td class="number">${number(item.rtt_ms, 2)} ms</td>
        <td class="number">${number(item.clock_offset_ms, 3)} ms</td>
        <td><span class="health ${ok ? "health--good" : "health--warn"}">${status}</span></td>
      </tr>`;
    }).join("");
  }

  function render() {
    renderCards();
    renderFilter();
    renderChart();
    renderTable();
    const mode = state.payload.mode === "live" ? "Live measurements" : "Baseline fixture";
    elements.mode.innerHTML = `<span class="status-dot"></span>${escapeHtml(mode)}`;
    elements.generated.textContent = `Generated ${state.payload.generated_at_utc || "from baseline observations"}`;
  }

  async function load() {
    try {
      const response = await fetch(API_PATH, { cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`API ${response.status}`);
      state.payload = await response.json();
    } catch (error) {
      const response = await fetch(FIXTURE_PATH, { cache: "no-store" });
      state.payload = await response.json();
    }
    render();
  }

  elements.filter.addEventListener("change", () => {
    state.observer = elements.filter.value;
    renderChart();
    renderTable();
  });

  load().catch(() => {
    elements.mode.textContent = "Data unavailable";
    elements.rows.innerHTML = '<tr><td colspan="8">Time Authority data could not be loaded.</td></tr>';
  });
})();

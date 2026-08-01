(() => {
  'use strict';

  const TARGET = '#analytics-anomalies';
  const HEALTH_ROUTE = '/api/telephony/analytics/health';
  const EXPECTED_IDS = new Set([
    'platform_health_score',
    'answer_rate',
    'failure_ratio',
    'dominant_failure_concentration',
    'interconnect_attention_ratio',
    'interconnect_latency',
  ]);
  const STATES = new Set(['ok', 'watch', 'critical', 'insufficient_data']);
  const TARGETS = new Set(['#analytics-health', '#analytics-failures', '#analytics-carriers']);
  const SAFETY_KEYS = [
    'automatic_action',
    'notification_dispatch',
    'traffic_enforcement',
    'route_change',
    'service_control',
  ];

  const escapeHtml = (value) => String(value ?? '—').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[character]));

  const stateLabel = (value) => String(value || 'insufficient_data').replaceAll('_', ' ');

  function unavailable(message) {
    const target = document.querySelector(TARGET);
    if (!target) return;
    target.innerHTML = `
      <h3>Informational anomaly indicators</h3>
      <p class="analytics-unavailable">${escapeHtml(message)}</p>
    `;
  }

  function validate(payload) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false;
    if (payload.schema_version !== '1.0') return false;
    if (payload.mode !== 'informational_no_enforcement') return false;
    if (!STATES.has(payload.overall_state)) return false;
    if (!payload.safety || typeof payload.safety !== 'object') return false;
    if (!SAFETY_KEYS.every((key) => payload.safety[key] === false)) return false;
    if (!Array.isArray(payload.indicators) || payload.indicators.length !== EXPECTED_IDS.size) return false;

    const seen = new Set();
    for (const indicator of payload.indicators) {
      if (!indicator || typeof indicator !== 'object' || Array.isArray(indicator)) return false;
      if (!EXPECTED_IDS.has(indicator.id) || seen.has(indicator.id)) return false;
      if (!STATES.has(indicator.state)) return false;
      if (!TARGETS.has(indicator.investigation_target)) return false;
      if (indicator.automatic_action !== false) return false;
      if (typeof indicator.reason_code !== 'string' || indicator.reason_code.length > 96) return false;
      if (typeof indicator.unit !== 'string' || indicator.unit.length > 48) return false;
      if (!Number.isInteger(indicator.minimum_sample) || indicator.minimum_sample < 0) return false;
      if (!Number.isInteger(indicator.sample_size) || indicator.sample_size < 0) return false;
      if (indicator.observed_value !== null && typeof indicator.observed_value !== 'number') return false;
      seen.add(indicator.id);
    }
    return seen.size === EXPECTED_IDS.size;
  }

  function render(payload) {
    const target = document.querySelector(TARGET);
    if (!target) return;

    const rows = payload.indicators.map((indicator) => `
      <li class="anomaly-indicator anomaly-${escapeHtml(indicator.state)}">
        <div>
          <strong>${escapeHtml(indicator.id.replaceAll('_', ' '))}</strong>
          <small>${escapeHtml(stateLabel(indicator.state))} · sample ${escapeHtml(indicator.sample_size)}/${escapeHtml(indicator.minimum_sample)}</small>
        </div>
        <div class="anomaly-observation">
          <span>${escapeHtml(indicator.observed_value)}</span>
          <small>${escapeHtml(indicator.unit)}</small>
          <a href="${escapeHtml(indicator.investigation_target)}">Inspect aggregate panel</a>
        </div>
      </li>
    `).join('');

    target.innerHTML = `
      <div class="anomaly-heading">
        <h3>Informational anomaly indicators</h3>
        <span class="anomaly-overall anomaly-${escapeHtml(payload.overall_state)}">${escapeHtml(stateLabel(payload.overall_state))}</span>
      </div>
      <p class="anomaly-boundary">No notification, enforcement, routing, service control, or automatic remediation.</p>
      <ul class="anomaly-indicators">${rows}</ul>
    `;
  }

  async function loadAnomalyPanel() {
    try {
      const response = await fetch(HEALTH_ROUTE, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json();
      if (!validate(health.anomalies)) throw new Error('invalid anomaly contract');
      render(health.anomalies);
    } catch (error) {
      unavailable('Informational anomaly indicators are unavailable.');
    }
  }

  const refresh = document.querySelector('#refresh');
  if (refresh) refresh.addEventListener('click', loadAnomalyPanel);
  loadAnomalyPanel();
})();

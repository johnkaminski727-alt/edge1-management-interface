const stateClass = {
  healthy: 'ok',
  degraded: 'warn',
  critical: 'critical',
  registered: 'ok',
  unreachable: 'critical',
  ready: 'ok',
  pass: 'ok',
  warn: 'warn',
  unknown: 'warn',
};

const displayText = (value) => String(value ?? '—');
const text = (value) => displayText(value).replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}[character]));

function badge(value) {
  const key = displayText(value).toLowerCase();
  return `<span class="badge ${stateClass[key] || ''}">${text(value)}</span>`;
}

function countList(values, emptyMessage) {
  const entries = Object.entries(values || {});
  if (!entries.length) {
    return `<p class="analytics-empty">${text(emptyMessage)}</p>`;
  }
  return `<ul class="analytics-list">${entries
    .map(([label, value]) => `<li><span>${text(label)}</span><strong>${text(value)}</strong></li>`)
    .join('')}</ul>`;
}

function analyticsStat(label, value, suffix = '') {
  return `<div class="analytics-stat"><span>${text(label)}</span><strong>${text(value)}${text(suffix)}</strong></div>`;
}

function analyticsUnavailable(target, message) {
  target.innerHTML = `<h3>${text(target.dataset.title || 'Aggregate analytics')}</h3><p class="analytics-unavailable">${text(message)}</p>`;
}

function render(data) {
  document.querySelector('#overall-title').textContent = `${displayText(data.overall_status)} — ${displayText(data.site)}`;
  document.querySelector('#overall-title').className = stateClass[data.overall_status] || '';
  document.querySelector('#generated-at').textContent = `Snapshot ${new Date(data.generated_at).toLocaleString()} · ${displayText(data.mode)}`;

  const metrics = [
    ['Active calls', data.metrics.active_calls],
    ['Registrations', data.metrics.registrations],
    ['Messages queued', data.metrics.messages_queued],
    ['Trunks healthy', `${displayText(data.metrics.trunks_healthy)}/${displayText(data.metrics.trunks_total)}`],
    ['Critical alerts', data.metrics.critical_alerts],
  ];
  document.querySelector('#metrics').innerHTML = metrics
    .map(([label, value]) => `<article class="metric"><strong>${text(value)}</strong><span>${text(label)}</span></article>`)
    .join('');

  document.querySelector('#service-grid').innerHTML = (data.services || [])
    .map((service) => `<article class="service-card"><div class="section-heading"><h3>${text(service.name)}</h3>${badge(service.status)}</div><p>${text(service.role)}</p><small>Latency ${text(service.latency_ms)} ms · checked ${text(service.last_checked)}</small></article>`)
    .join('');

  document.querySelector('#peer-rows').innerHTML = (data.interconnects || [])
    .map((peer) => `<tr><td>${text(peer.name)}</td><td>${badge(peer.status)}</td><td>${text(peer.latency_ms)} ms</td><td>${text(peer.success_rate)}%</td><td>${text(peer.active_calls)}</td></tr>`)
    .join('');

  document.querySelector('#registration-rows').innerHTML = (data.registrations || [])
    .map((registration) => `<tr><td>${text(registration.endpoint)}</td><td>${badge(registration.state)}</td><td>${text(registration.transport)}</td><td>${text(registration.user_agent)}</td><td>${text(registration.expires_in_seconds)}s</td></tr>`)
    .join('');

  document.querySelector('#alerts').innerHTML = (data.alerts || []).length
    ? data.alerts.map((alert) => `<article class="alert"><h3 class="${stateClass[alert.severity] || ''}">${text(alert.title)}</h3><p>${text(alert.summary)}</p><small>${text(alert.source)} · ${text(alert.opened_at)}</small></article>`).join('')
    : '<p class="alert ok">No active alerts.</p>';

  document.querySelector('#sip-peer-cards').innerHTML = (data.interconnects || [])
    .map((peer) => `
      <article class="service-card">
        <div class="section-heading">
          <h3>${text(peer.name)}</h3>
          ${badge(peer.status)}
        </div>
        <p>Endpoint: ${text(peer.endpoint)}</p>
        <p>Latency: ${text(peer.latency_ms)} ms</p>
        <p>Success: ${text(peer.success_rate)}%</p>
        <p>Active calls: ${text(peer.active_calls)}</p>
      </article>
    `).join('');
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function renderAnalyticsHealth(health) {
  const target = document.querySelector('#analytics-health');
  const components = Object.entries(health.components || {});
  target.innerHTML = `
    <h3>Platform health score</h3>
    <div class="analytics-score">
      <strong class="${stateClass[health.overall_status] || ''}">${text(health.score)}</strong>
      <span>/100</span>
      ${badge(health.overall_status)}
    </div>
    ${components.length
      ? `<ul class="analytics-list">${components.map(([name, status]) => `<li><span>${text(name)}</span>${badge(status)}</li>`).join('')}</ul>`
      : '<p class="analytics-empty">No component states available.</p>'}
  `;
}

function renderAnalyticsFailures(calls) {
  const target = document.querySelector('#analytics-failures');
  target.innerHTML = `
    <h3>Call and SIP outcomes</h3>
    <div class="analytics-stats">
      ${analyticsStat('Calls', calls.calls_total)}
      ${analyticsStat('Answered', calls.calls_answered)}
      ${analyticsStat('Answer rate', calls.answer_rate_percent, '%')}
      ${analyticsStat('Average duration', calls.duration_seconds_average, 's')}
    </div>
    <h4>Failure classes</h4>
    ${countList(calls.failure_classes, 'No failure classes observed in the sanitized dataset.')}
  `;
}

function renderAnalyticsCarriers(calls, interconnects) {
  const target = document.querySelector('#analytics-carriers');
  const hasCalls = calls !== null;
  const hasInterconnects = interconnects !== null;
  if (!hasCalls && !hasInterconnects) {
    analyticsUnavailable(target, 'Aggregate carrier and interconnect analytics are unavailable.');
    return;
  }

  const interconnectStats = hasInterconnects
    ? `<div class="analytics-stats">
        ${analyticsStat('Interconnects', interconnects.interconnects_total)}
        ${analyticsStat('Needs attention', interconnects.attention_required)}
        ${analyticsStat('Average latency', interconnects.latency_ms_average, 'ms')}
        ${analyticsStat('Maximum latency', interconnects.latency_ms_max, 'ms')}
      </div>
      <h4>Interconnect states</h4>
      ${countList(interconnects.states, 'No interconnect state records available.')}`
    : '<p class="analytics-unavailable">Interconnect posture is unavailable.</p>';

  const carrierUsage = hasCalls
    ? `<h4>Sanitized carrier utilization</h4>${countList(calls.carriers, 'No carrier utilization records available.')}`
    : '<p class="analytics-unavailable">Carrier utilization is unavailable.</p>';

  target.innerHTML = `<h3>Carrier and interconnect posture</h3>${interconnectStats}${carrierUsage}`;
}

async function loadAnalyticsPanels() {
  const healthTarget = document.querySelector('#analytics-health');
  const failureTarget = document.querySelector('#analytics-failures');
  const carrierTarget = document.querySelector('#analytics-carriers');
  healthTarget.dataset.title = 'Platform health score';
  failureTarget.dataset.title = 'Call and SIP outcomes';
  carrierTarget.dataset.title = 'Carrier and interconnect posture';

  const [healthResult, callsResult, interconnectResult] = await Promise.allSettled([
    fetchJson('/api/telephony/analytics/health'),
    fetchJson('/api/telephony/analytics/calls'),
    fetchJson('/api/telephony/analytics/interconnects'),
  ]);

  if (healthResult.status === 'fulfilled') {
    renderAnalyticsHealth(healthResult.value);
  } else {
    analyticsUnavailable(healthTarget, 'Aggregate platform health is unavailable.');
  }

  if (callsResult.status === 'fulfilled') {
    renderAnalyticsFailures(callsResult.value);
  } else {
    analyticsUnavailable(failureTarget, 'Aggregate call and SIP outcomes are unavailable.');
  }

  renderAnalyticsCarriers(
    callsResult.status === 'fulfilled' ? callsResult.value : null,
    interconnectResult.status === 'fulfilled' ? interconnectResult.value : null,
  );
}

async function loadSipHistory() {
  const target = document.querySelector('#sip-history');
  if (!target) {
    return;
  }

  try {
    const history = await fetchJson('/api/telephony/health/history');
    const checks = (history.checks || []).slice(-10).reverse();
    target.innerHTML = checks.length
      ? checks.map((check) => `
          <article class="alert">
            <h3 class="${stateClass[check.status] || ''}">${text(check.peer)} — ${text(check.status)}</h3>
            <p>SIP ${text(check.response_code)} · ${text(check.latency_ms)} ms</p>
            <small>${text(check.timestamp)}</small>
          </article>
        `).join('')
      : '<p class="alert ok">No SIP history available.</p>';
  } catch (error) {
    target.innerHTML = '<p class="alert">SIP history unavailable.</p>';
  }
}

async function loadSipReadiness() {
  const target = document.querySelector('#sip-readiness');
  if (!target) {
    return;
  }

  try {
    const readiness = await fetchJson('/api/telephony/readiness');
    const requirements = Object.entries(readiness.production_requirements || {})
      .map(([key, value]) => `<li>${value ? '✓' : '□'} ${text(key)}</li>`)
      .join('');

    target.innerHTML = `
      <article class="alert">
        <h3>${text(readiness.platform)}</h3>
        <p>Carriers: ${text(readiness.summary?.carriers)} · SIP Peers: ${text(readiness.summary?.sip_peers)} · Routes: ${text(readiness.summary?.routing_rules)}</p>
        <ul>${requirements}</ul>
      </article>
    `;
  } catch (error) {
    target.innerHTML = '<p class="alert">Readiness unavailable.</p>';
  }
}

async function loadSipAcceptance() {
  const target = document.querySelector('#sip-acceptance');
  if (!target) {
    return;
  }

  try {
    const acceptance = await fetchJson('/api/telephony/acceptance');
    const tests = (acceptance.sip_peer_tests || [])
      .map((test) => `<li>${text(test.peer)} — ${text(test.status)} (${text(test.options)} / ${text(test.latency_ms)} ms)</li>`)
      .join('');
    const requirements = Object.entries(acceptance.production_requirements || {})
      .map(([key, value]) => `<li>${value ? '✓' : '□'} ${text(key)}</li>`)
      .join('');

    target.innerHTML = `
      <article class="alert">
        <h3>${text(acceptance.platform)}</h3>
        <p>Carriers: ${text(acceptance.carrier_count)} · Routes: ${text(acceptance.routing_rules)}</p>
        <strong>SIP Tests</strong>
        <ul>${tests || '<li>No tests</li>'}</ul>
        <strong>Production Requirements</strong>
        <ul>${requirements}</ul>
      </article>
    `;
  } catch (error) {
    target.innerHTML = '<p class="alert">Acceptance unavailable.</p>';
  }
}

async function loadCarrierLifecycle() {
  const target = document.querySelector('#carrier-lifecycle');
  if (!target) {
    return;
  }

  try {
    const data = await fetchJson('/api/telephony/carriers');
    target.innerHTML = (data.carriers || []).map((carrier) => `
      <article class="alert">
        <h3 class="${stateClass[carrier.status] || ''}">${text(carrier.name)}</h3>
        <p>Status: ${text(carrier.status)}</p>
        ${(carrier.sip_peers || []).map((peer) => `<small>Peer: ${text(peer.peer)} · ${text(peer.status)}</small>`).join('<br>')}
      </article>
    `).join('');
  } catch (error) {
    target.innerHTML = '<p class="alert">Carrier lifecycle unavailable.</p>';
  }
}

async function load() {
  const button = document.querySelector('#refresh');
  button.disabled = true;
  try {
    let data;
    try {
      data = await fetchJson('/api/telephony/status');
    } catch (liveError) {
      data = await fetchJson('./telephony.fixture.json');
      data.mode = `fixture fallback (${liveError.message})`;
    }
    render(data);
    await Promise.all([
      loadAnalyticsPanels(),
      loadSipHistory(),
      loadSipReadiness(),
      loadSipAcceptance(),
      loadCarrierLifecycle(),
    ]);
  } catch (error) {
    document.querySelector('#overall-title').textContent = 'Snapshot unavailable';
    document.querySelector('#generated-at').textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

document.querySelector('#refresh').addEventListener('click', load);
load();

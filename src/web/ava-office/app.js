(() => {
  'use strict';

  const status = document.getElementById('connection-status');
  const workList = document.getElementById('work-list');
  const decisionList = document.getElementById('decision-list');
  const instructionList = document.getElementById('instruction-list');
  const metrics = {
    active: document.getElementById('metric-active'),
    needsYou: document.getElementById('metric-needs-you'),
    waiting: document.getElementById('metric-waiting'),
    scheduled: document.getElementById('metric-scheduled'),
  };

  let workState = '';

  function text(value, fallback = '—') {
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
  }

  function escapeHtml(value) {
    return text(value, '').replace(/[&<>'"]/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[char]));
  }

  async function getJson(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function count(summary, ...states) {
    return states.reduce((total, state) => total + Number(summary.work_items?.[state] || 0), 0);
  }

  async function loadSummary() {
    try {
      const summary = await getJson('/api/ava-office/summary');
      metrics.active.textContent = String(count(summary, 'new', 'working'));
      metrics.needsYou.textContent = String(Number(summary.work_items?.needs_owner || 0) + Number(summary.actions?.awaiting_confirmation || 0));
      metrics.waiting.textContent = String(count(summary, 'waiting_external'));
      metrics.scheduled.textContent = String(count(summary, 'scheduled'));
      status.textContent = 'Ava Office read model connected. External execution remains separately gated.';
    } catch (error) {
      status.textContent = `Ava Office data is not available: ${error.message}`;
      Object.values(metrics).forEach((node) => { node.textContent = '—'; });
    }
  }

  function workCard(item) {
    return `<article class="item-card">
      <div><h3>${escapeHtml(item.title)}</h3></div>
      <span class="badge ${escapeHtml(item.state)}">${escapeHtml(item.state).replaceAll('_', ' ')}</span>
      <p>${escapeHtml(item.desired_outcome)}</p>
      <div class="meta">
        <span>${escapeHtml(item.priority)} priority</span>
        <span>from ${escapeHtml(item.source_channel)}</span>
        ${item.due_at_utc ? `<span>due ${escapeHtml(item.due_at_utc)}</span>` : ''}
        <span>updated ${escapeHtml(item.updated_at_utc)}</span>
      </div>
    </article>`;
  }

  async function loadWork() {
    workList.innerHTML = '<div class="empty">Loading work queue…</div>';
    const query = workState ? `?state=${encodeURIComponent(workState)}` : '';
    try {
      const payload = await getJson(`/api/ava-office/work-items${query}`);
      workList.innerHTML = payload.items?.length ? payload.items.map(workCard).join('') : '<div class="empty">No work items in this view.</div>';
    } catch (error) {
      workList.innerHTML = `<div class="error">Unable to read work queue: ${escapeHtml(error.message)}</div>`;
    }
  }

  function decisionCard(item) {
    return `<article class="item-card">
      <div><h3>${escapeHtml(item.summary)}</h3></div>
      <span class="badge ${escapeHtml(item.status)}">${escapeHtml(item.status).replaceAll('_', ' ')}</span>
      <p>${escapeHtml(item.reason)}</p>
      <div class="meta"><span>${escapeHtml(item.capability)}</span><span>${escapeHtml(item.authority_class)} authority</span></div>
    </article>`;
  }

  async function loadDecisions() {
    decisionList.innerHTML = '<div class="empty">Loading decisions…</div>';
    try {
      const payload = await getJson('/api/ava-office/decisions');
      decisionList.innerHTML = payload.items?.length ? payload.items.map(decisionCard).join('') : '<div class="empty">Nothing currently needs your decision.</div>';
    } catch (error) {
      decisionList.innerHTML = `<div class="error">Unable to read decisions: ${escapeHtml(error.message)}</div>`;
    }
  }

  function instructionCard(item) {
    return `<article class="item-card">
      <div><h3>${escapeHtml(item.domain)}</h3></div>
      <span class="badge">${escapeHtml(item.effect).replaceAll('_', ' ')}</span>
      <p>${escapeHtml(item.statement)}</p>
      <div class="meta"><span>priority ${escapeHtml(item.priority)}</span><span>updated ${escapeHtml(item.updated_at_utc)}</span></div>
    </article>`;
  }

  async function loadInstructions() {
    instructionList.innerHTML = '<div class="empty">Loading standing instructions…</div>';
    try {
      const payload = await getJson('/api/ava-office/instructions');
      instructionList.innerHTML = payload.items?.length ? payload.items.map(instructionCard).join('') : '<div class="empty">No standing instructions have been recorded yet.</div>';
    } catch (error) {
      instructionList.innerHTML = `<div class="error">Unable to read instructions: ${escapeHtml(error.message)}</div>`;
    }
  }

  document.querySelectorAll('.tabs button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tabs button').forEach((node) => node.classList.toggle('active', node === button));
      document.querySelectorAll('.view').forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === button.dataset.view));
      if (button.dataset.view === 'decisions') loadDecisions();
      if (button.dataset.view === 'instructions') loadInstructions();
    });
  });

  document.querySelectorAll('.filters button').forEach((button) => {
    button.addEventListener('click', () => {
      workState = button.dataset.state || '';
      document.querySelectorAll('.filters button').forEach((node) => node.classList.toggle('active', node === button));
      loadWork();
    });
  });

  document.getElementById('refresh-work').addEventListener('click', () => {
    loadSummary();
    loadWork();
  });

  loadSummary();
  loadWork();
})();

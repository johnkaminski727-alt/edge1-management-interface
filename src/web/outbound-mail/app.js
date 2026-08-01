(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const state = { status: null, preview: null, activity: [], remoteActivity: [] };

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function showStep(name) {
    $$('.panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === name));
    $$('.step-nav button').forEach((button) => button.classList.toggle('active', button.dataset.step === name));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function splitAddresses(value) {
    return String(value || '').split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  }

  function formPayload() {
    return {
      original_recipient: $('#original-recipient').value.trim(),
      identity_hint: $('#sender-profile').value,
      system_generated: $('#system-generated').checked,
      to: $('#to').value,
      cc: $('#cc').value,
      bcc: $('#bcc').value,
      subject: $('#subject').value.trim(),
      body: $('#body').value,
      message_class: $('#message-class').value,
      signer_name: $('#signer-name').value.trim(),
      signer_title: $('#signer-title').value.trim(),
      case_id: $('#case-id').value.trim(),
      action_id: $('#action-id').value.trim(),
      mailing_address: $('#mailing-address').value.trim(),
      unsubscribe_url: $('#unsubscribe-url').value.trim(),
    };
  }

  function selectedIdentityAddress() {
    if (state.preview && state.preview.sender_selection) return state.preview.sender_selection.address;
    const selection = state.status && state.status.sender_selection;
    if (!selection) return 'Automatic';
    const hint = $('#sender-profile').value;
    if (hint) {
      const identity = selection.identities.find((item) => item.key === hint || item.address === hint);
      if (identity) return identity.address;
    }
    const original = $('#original-recipient').value.trim().toLowerCase();
    if (original && selection.identities.some((item) => item.address === original)) return original;
    return selection.default_sender;
  }

  function updateSetup() {
    const selected = state.status && state.status.providers.find((item) => item.selected);
    const senderSelection = state.status && state.status.sender_selection;
    const checks = [
      ['Mailing address configured', Boolean($('#mailing-address').value.trim())],
      ['Automatic sender selection active', Boolean(senderSelection && senderSelection.automatic_selection_enabled)],
      ['Submitted From override disabled', Boolean(senderSelection && !senderSelection.allow_submitted_from_override)],
      ['At least one live sender authorized', Boolean(senderSelection && senderSelection.live_sender_count > 0)],
      ['Delivery adapter enabled', Boolean(selected && selected.enabled)],
      ['Runtime provider settings available', Boolean(selected && selected.configured)],
      ['Live delivery authorized', Boolean(state.status && state.status.external_delivery_enabled)],
    ];
    $('#setup-checklist').innerHTML = checks.map(([label, ok]) => `<p class="${ok ? 'pass' : 'pending'}"><span>${ok ? '✓' : '○'}</span>${escapeHtml(label)}</p>`).join('');
    $('#summary-provider').textContent = selected ? selected.name : 'Not configured';
    $('#summary-sender').textContent = selectedIdentityAddress();
  }

  function renderProviderOptions(status) {
    const select = $('#provider');
    select.innerHTML = status.providers.map((provider) => {
      const label = `${provider.name} — ${provider.ready ? 'ready' : provider.detail}`;
      return `<option value="${escapeHtml(provider.name)}" ${provider.selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    select.disabled = true;
    select.title = 'Provider selection is controlled by the server configuration and activation process.';
  }

  function renderSenderOptions(status) {
    const selection = status.sender_selection;
    const select = $('#sender-profile');
    const options = selection.identities.map((identity) => {
      const value = identity.key || identity.address;
      const label = `${identity.display_name} — ${identity.address}${identity.live_enabled ? ' — live' : ' — preview only'}`;
      return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
    });
    select.innerHTML = `<option value="">Automatic — original recipient, then ${escapeHtml(selection.default_sender)}</option>${options.join('')}`;
    $('#private-mailbox').value = selection.private_delivery_mailbox;
    $('#shared-mailbox').value = selection.shared_delivery_mailbox;
    $('#system-sender').value = selection.system_sender;
    $('#summary-private-mailbox').textContent = selection.private_delivery_mailbox;
    $('#summary-shared-mailbox').textContent = selection.shared_delivery_mailbox;
  }

  function renderStatus(status) {
    state.status = status;
    renderProviderOptions(status);
    renderSenderOptions(status);
    const pill = $('.mode-pill');
    pill.innerHTML = `<span aria-hidden="true"></span>${status.external_delivery_enabled ? 'Gateway ready' : 'Preview only'}`;
    pill.classList.toggle('ready', status.external_delivery_enabled);
    $('#submit-message').disabled = !status.external_delivery_enabled;
    updateSetup();
  }

  async function loadStatus() {
    const response = await fetch('/outbound-mail/status', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Gateway status failed: ${response.status}`);
    renderStatus(await response.json());
  }

  function clientValidation() {
    const errors = [];
    const warnings = [];
    const recipients = [...splitAddresses($('#to').value), ...splitAddresses($('#cc').value), ...splitAddresses($('#bcc').value)];
    if (!recipients.length) errors.push('Add at least one recipient.');
    if (!$('#subject').value.trim()) errors.push('Add a subject.');
    if (!$('#body').value.trim()) errors.push('Add a message body.');
    if (!$('#mailing-address').value.trim()) warnings.push('Mailing address is not configured; live submission remains blocked.');
    if ($('#message-class').value === 'commercial' && !$('#unsubscribe-url').value.trim()) errors.push('Commercial messages require an unsubscribe or preference URL.');
    const original = $('#original-recipient').value.trim().toLowerCase();
    if (original && state.status && !state.status.sender_selection.identities.some((item) => item.address === original)) {
      errors.push('Original inbound recipient is not a registered sender identity.');
    }
    if ($('#system-generated').checked) warnings.push('System-generated mode selects noreply@ww.cx and intentionally omits Reply-To.');
    if (!state.status || !state.status.external_delivery_enabled) warnings.push('External delivery remains disabled; this preview does not send mail.');
    return { errors, warnings, recipients };
  }

  function renderValidation(result) {
    const items = [
      ...result.errors.map((text) => `<p class="error">✕ ${escapeHtml(text)}</p>`),
      ...result.warnings.map((text) => `<p class="warning">! ${escapeHtml(text)}</p>`),
      ...(result.errors.length || result.warnings.length ? [] : ['<p class="pass">✓ Preview satisfies configured policy checks.</p>']),
    ];
    $('#validation-results').innerHTML = items.join('');
  }

  function addComposedActivity(preview) {
    const request = preview.request;
    state.activity.unshift({
      controlId: preview.control_id,
      caseId: request.case_id || '—',
      recipient: request.recipients[0] || '—',
      subject: `${request.subject || 'Untitled'} [${request.from_address}]`,
      status: 'Composed',
      event: new Date().toISOString(),
      confidence: 'Confirmed',
    });
    renderActivity();
  }

  async function generatePreview() {
    const validation = clientValidation();
    renderValidation(validation);
    if (validation.errors.length) {
      $('#preview-status').textContent = 'Blocked';
      $('#preview-status').className = 'badge danger';
      showStep('preview');
      return;
    }

    $('#preview-status').textContent = 'Generating';
    $('#preview-status').className = 'badge';
    const response = await fetch('/outbound-mail/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formPayload()),
    });
    const result = await response.json();
    if (!response.ok) {
      validation.errors.push(`${result.error || 'preview_failed'}: ${result.message || 'Unknown error'}`);
      renderValidation(validation);
      $('#preview-status').textContent = 'Blocked';
      $('#preview-status').className = 'badge danger';
      showStep('preview');
      return;
    }

    state.preview = result;
    $('#message-preview').textContent = result.body;
    $('#headers-preview').textContent = Object.entries(result.headers).map(([key, value]) => `${key}: ${value}`).join('\n');
    $('#metadata-preview').innerHTML = [
      ['Control ID', result.control_id],
      ['Selected sender', result.request.from_address],
      ['Reply-To', result.request.reply_to || 'None'],
      ['Selection reason', result.sender_selection.reason],
      ['Submitted From replaced', result.sender_selection.from_address_replaced ? 'Yes' : 'No'],
      ['Class', result.request.message_class],
      ['Recipients', String(result.request.recipients.length)],
      ['Action URL', result.action_url],
      ['Provider', state.status.providers.find((item) => item.selected)?.name || 'none'],
      ['Tracking', 'disclosed-action-link; no-hidden-pixel'],
    ].map(([term, value]) => `<div><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('');
    $('#summary-sender').textContent = result.request.from_address;
    $('#preview-status').textContent = 'Preview ready';
    $('#preview-status').className = 'badge safe';
    $('#submit-message').disabled = !(state.status && state.status.external_delivery_enabled && result.sender_selection.live_enabled);
    addComposedActivity(result);
    showStep('preview');
  }

  async function submitMessage() {
    if (!state.status || !state.status.external_delivery_enabled || !state.preview || !state.preview.sender_selection.live_enabled) return;
    if (!window.confirm('Submit this correspondence through the configured external provider?')) return;
    const payload = formPayload();
    payload.confirm_send = true;
    const response = await fetch('/outbound-mail/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      window.alert(`${result.error || 'send_failed'}: ${result.message || 'Unknown error'}`);
      return;
    }
    window.alert(`Message submitted from ${result.sender_selection.address}. Control ID: ${result.control_id}`);
    await loadActivity();
  }

  function normalizedRemoteActivity(event) {
    return {
      controlId: event.control_id || '—',
      caseId: event.case_id || '—',
      recipient: event.recipient_count ? `${event.recipient_count} recipient(s)` : '—',
      subject: event.sender_address ? `Restricted [${event.sender_address}]` : 'Restricted in audit view',
      status: event.event === 'outbound_message_submitted' ? 'Submitted' : (event.event || 'Event'),
      event: event.occurred_at || '—',
      confidence: 'Confirmed',
    };
  }

  async function loadActivity() {
    const response = await fetch('/outbound-mail/audit?limit=100', { cache: 'no-store' });
    if (!response.ok) return;
    const result = await response.json();
    state.remoteActivity = (result.events || []).map(normalizedRemoteActivity);
    renderActivity();
  }

  function renderActivity() {
    const query = $('#activity-search').value.toLowerCase();
    const status = $('#activity-status').value;
    const combined = [...state.activity, ...state.remoteActivity];
    const rows = combined.filter((row) => (!status || row.status === status) && Object.values(row).join(' ').toLowerCase().includes(query));
    $('#activity-body').innerHTML = rows.length ? rows.map((row) => `<tr><td>${escapeHtml(row.controlId)}</td><td>${escapeHtml(row.caseId)}</td><td>${escapeHtml(row.recipient)}</td><td>${escapeHtml(row.subject)}</td><td><span class="status">${escapeHtml(row.status)}</span></td><td>${escapeHtml(row.event)}</td><td>${escapeHtml(row.confidence)}</td></tr>`).join('') : '<tr><td colspan="7" class="empty">No matching events.</td></tr>';
  }

  function exportCsv() {
    const header = ['Control ID', 'Case', 'Recipient', 'Subject', 'Status', 'Last event', 'Confidence'];
    const rows = [...state.activity, ...state.remoteActivity].map((row) => [row.controlId, row.caseId, row.recipient, row.subject, row.status, row.event, row.confidence]);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    const link = document.createElement('a');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    link.href = url;
    link.download = 'wwcx-correspondence-matrix.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  $$('.step-nav button').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.step)));
  $$('[data-next]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.next)));
  $$('[data-back]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.back)));
  ['mailing-address', 'privacy-url', 'contact-email', 'original-recipient', 'sender-profile'].forEach((id) => $(`#${id}`).addEventListener('input', updateSetup));
  $('#system-generated').addEventListener('change', updateSetup);
  $('#message-class').addEventListener('change', () => $('#unsubscribe-wrap').classList.toggle('hidden', $('#message-class').value !== 'commercial'));
  $('#generate-preview').addEventListener('click', generatePreview);
  $('#submit-message').addEventListener('click', submitMessage);
  $('#copy-preview').addEventListener('click', async () => state.preview && navigator.clipboard.writeText(state.preview.body));
  $('#activity-search').addEventListener('input', renderActivity);
  $('#activity-status').addEventListener('change', renderActivity);
  $('#export-activity').addEventListener('click', exportCsv);
  $('#load-example').addEventListener('click', () => {
    $('#original-recipient').value = 'john@spiritcreekgardens.com';
    $('#to').value = 'records@example.com';
    $('#case-id').value = 'ENT-184366738';
    $('#action-id').value = 'ENT-ACT-014';
    $('#subject').value = 'Request for transfer, custody, and billing records';
    $('#body').value = 'Hello,\n\nPlease provide the complete chronology and supporting records identified in our correspondence.\n\nThank you.';
    updateSetup();
  });

  Promise.all([loadStatus(), loadActivity()]).catch((error) => {
    $('.mode-pill').textContent = 'Gateway unavailable';
    $('#setup-checklist').innerHTML = `<p class="error"><span>✕</span>${escapeHtml(error.message)}</p>`;
  });
})();

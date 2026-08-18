(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const state = {
    status: null,
    preview: null,
    activity: [],
    remoteActivity: [],
    currentStep: 'setup',
    draftCommitted: false,
  };

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function toast(message, tone = 'neutral') {
    const region = $('#toast-region');
    if (!region) return;
    const item = document.createElement('div');
    item.className = `toast ${tone}`;
    item.textContent = message;
    region.appendChild(item);
    window.setTimeout(() => item.remove(), 3200);
  }

  function focusPanel(name) {
    const panel = $(`.panel[data-panel="${name}"]`);
    const heading = panel && panel.querySelector('h2');
    if (!heading) return;
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
    window.setTimeout(() => heading.removeAttribute('tabindex'), 0);
  }

  function showStep(name, options = {}) {
    state.currentStep = name;
    $$('.panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === name));
    $$('.step-nav button').forEach((button) => {
      const active = button.dataset.step === name;
      button.classList.toggle('active', active);
      button.setAttribute('aria-current', active ? 'page' : 'false');
    });
    if (!options.keepScroll) window.scrollTo({ top: 0, behavior: options.instant ? 'auto' : 'smooth' });
    if (options.focus !== false) focusPanel(name);
  }

  function splitAddresses(value) {
    return String(value || '').split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  }

  function managedDomains() {
    const selection = state.status && state.status.sender_selection;
    return selection && Array.isArray(selection.managed_domains) ? selection.managed_domains : [];
  }

  function registeredAddresses() {
    const selection = state.status && state.status.sender_selection;
    return selection ? new Set(selection.identities.map((item) => item.address)) : new Set();
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

  function hasDraftContent() {
    return [
      'original-recipient',
      'to',
      'cc',
      'bcc',
      'subject',
      'body',
      'case-id',
      'action-id',
    ].some((id) => $(`#${id}`).value.trim());
  }

  function originalRecipientPreview() {
    const original = $('#original-recipient').value.trim().toLowerCase();
    if (!original || !original.includes('@')) return null;
    const domain = original.split('@').pop();
    if (managedDomains().includes(domain) && !registeredAddresses().has(original)) return original;
    return null;
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
    const proposed = originalRecipientPreview();
    if (proposed) return `${proposed} (preview)`;
    return selection.default_sender;
  }

  function invalidatePreview() {
    if (!state.preview) {
      updateSetup();
      return;
    }
    state.preview = null;
    $('#preview-status').textContent = 'Review needed';
    $('#preview-status').className = 'badge';
    $('#message-preview').textContent = 'The message changed. Generate a fresh review before sending.';
    $('#headers-preview').textContent = 'Preview invalidated because the message changed.';
    $('#metadata-preview').innerHTML = '';
    $('#validation-results').innerHTML = '';
    $('#submit-message').disabled = true;
    updateSetup();
  }

  function markDraftChanged() {
    state.draftCommitted = false;
    invalidatePreview();
  }

  function updateGreeting() {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning.' : hour < 18 ? 'Good afternoon.' : 'Good evening.';
    $('#today-greeting').textContent = greeting;
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
    $('#summary-mode').textContent = state.status && state.status.external_delivery_enabled ? 'Live enabled' : 'Preview only';
  }

  function renderProviderOptions(status) {
    const select = $('#provider');
    select.innerHTML = status.providers.map((provider) => {
      const label = `${provider.name} — ${provider.ready ? 'ready' : provider.detail}`;
      return `<option value="${escapeHtml(provider.name)}" ${provider.selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    select.disabled = true;
    select.title = 'Provider selection is controlled by server configuration and the activation process.';
  }

  function renderSenderOptions(status) {
    const selection = status.sender_selection;
    const select = $('#sender-profile');
    const options = selection.identities.map((identity) => {
      const value = identity.key || identity.address;
      const availability = identity.live_enabled ? 'live' : 'preview only';
      return `<option value="${escapeHtml(value)}">${escapeHtml(identity.display_name)} — ${escapeHtml(identity.address)} — ${availability}</option>`;
    });
    select.innerHTML = `<option value="">Automatic — use message context, then ${escapeHtml(selection.default_sender)}</option>${options.join('')}`;
    $('#private-mailbox').value = selection.private_delivery_mailbox;
    $('#shared-mailbox').value = selection.shared_delivery_mailbox;
    $('#system-sender').value = selection.system_sender;
    const domains = Array.isArray(selection.managed_domains) ? selection.managed_domains : [];
    $('#managed-domains').value = domains.length ? domains.join(', ') : 'Managed by server registry';
  }

  function renderStatus(status) {
    state.status = status;
    renderProviderOptions(status);
    renderSenderOptions(status);
    const pill = $('.mode-pill');
    pill.innerHTML = `<span aria-hidden="true"></span>${status.external_delivery_enabled ? 'Live delivery enabled' : 'Preview only'}`;
    pill.classList.toggle('ready', status.external_delivery_enabled);
    $('#submit-message').disabled = true;
    updateSetup();
  }

  async function loadStatus() {
    const response = await fetch('/outbound-mail/status', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Mail Room status failed: ${response.status}`);
    renderStatus(await response.json());
  }

  function validateOriginalRecipient(errors, warnings) {
    const original = $('#original-recipient').value.trim().toLowerCase();
    if (!original) return;
    if (!original.includes('@')) {
      errors.push('Original inbound recipient must be a complete email address.');
      return;
    }
    if (!state.status) return;
    if (registeredAddresses().has(original)) return;
    const domain = original.split('@').pop();
    const domains = managedDomains();
    if (domains.length && !domains.includes(domain)) {
      errors.push('Original inbound recipient is outside the managed Mail Room domains.');
      return;
    }
    if (domains.includes(domain)) {
      warnings.push('This catch-all address can be preserved for review, but it is not automatically authorized for live sending.');
    }
  }

  function clientValidation() {
    const errors = [];
    const warnings = [];
    const recipients = [...splitAddresses($('#to').value), ...splitAddresses($('#cc').value), ...splitAddresses($('#bcc').value)];
    if (!recipients.length) errors.push('Add at least one recipient.');
    if (!$('#subject').value.trim()) errors.push('Add a subject.');
    if (!$('#body').value.trim()) errors.push('Write the message before reviewing it.');
    if ($('#message-class').value === 'commercial' && !$('#unsubscribe-url').value.trim()) errors.push('Commercial messages require an unsubscribe or preference URL.');
    validateOriginalRecipient(errors, warnings);
    if ($('#system-generated').checked) warnings.push('System-generated mode uses noreply@ww.cx and intentionally omits Reply-To.');
    if (state.status && state.status.external_delivery_enabled && !$('#mailing-address').value.trim()) warnings.push('Mailing address is not configured; live submission will remain blocked.');
    if (!state.status || !state.status.external_delivery_enabled) warnings.push('Safe mode is active: this review cannot send external mail.');
    return { errors, warnings, recipients };
  }

  function renderValidation(result) {
    const items = [
      ...result.errors.map((text) => `<p class="error"><span aria-hidden="true">×</span>${escapeHtml(text)}</p>`),
      ...result.warnings.map((text) => `<p class="warning"><span aria-hidden="true">!</span>${escapeHtml(text)}</p>`),
      ...(result.errors.length || result.warnings.length ? [] : ['<p class="pass"><span aria-hidden="true">✓</span>Ready for review.</p>']),
    ];
    $('#validation-results').innerHTML = items.join('');
  }

  function updateActivityCount() {
    const total = state.activity.length + state.remoteActivity.length;
    $('#activity-count').textContent = `${total} ${total === 1 ? 'item' : 'items'}`;
  }

  function addComposedActivity(preview) {
    const request = preview.request;
    state.activity.unshift({
      controlId: preview.control_id,
      caseId: request.case_id || '—',
      recipient: request.recipients[0] || '—',
      subject: request.subject || 'Untitled',
      status: 'Composed',
      event: new Date().toISOString(),
      confidence: 'Confirmed',
    });
    renderActivity();
  }

  function selectionReasonLabel(reason) {
    const labels = {
      original_recipient: 'Matched original recipient',
      original_recipient_catch_all_proposal: 'Preserved catch-all recipient for preview',
      identity_hint: 'Selected message identity',
      default_sender: 'Default Mail Room identity',
      system_generated: 'System no-reply identity',
      default_unknown_original_recipient: 'Default identity fallback',
    };
    return labels[reason] || reason || 'Automatic';
  }

  async function generatePreview() {
    const validation = clientValidation();
    renderValidation(validation);
    if (validation.errors.length) {
      $('#preview-status').textContent = 'Needs attention';
      $('#preview-status').className = 'badge danger';
      showStep('preview');
      return;
    }

    $('#preview-status').textContent = 'Building review';
    $('#preview-status').className = 'badge';
    let response;
    try {
      response = await fetch('/outbound-mail/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formPayload()),
      });
    } catch (error) {
      validation.errors.push(`Mail Room could not reach the preview service: ${error.message}`);
      renderValidation(validation);
      $('#preview-status').textContent = 'Unavailable';
      $('#preview-status').className = 'badge danger';
      showStep('preview');
      return;
    }

    const result = await response.json();
    if (!response.ok) {
      validation.errors.push(result.message || result.error || 'Mail Room could not build the preview.');
      renderValidation(validation);
      $('#preview-status').textContent = 'Needs attention';
      $('#preview-status').className = 'badge danger';
      showStep('preview');
      return;
    }

    state.preview = result;
    $('#message-preview').textContent = result.body;
    $('#headers-preview').textContent = Object.entries(result.headers).map(([key, value]) => `${key}: ${value}`).join('\n');
    $('#metadata-preview').innerHTML = [
      ['From', result.request.from_address],
      ['To', result.request.recipients.join(', ')],
      ['Reply-To', result.request.reply_to || 'None'],
      ['Why this sender', selectionReasonLabel(result.sender_selection.reason)],
      ['Control ID', result.control_id],
      ['Message class', result.request.message_class],
      ['Provider', state.status.providers.find((item) => item.selected)?.name || 'Not configured'],
      ['Privacy', 'Disclosed link; no-hidden-pixel'],
    ].map(([term, value]) => `<div><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('');
    $('#summary-sender').textContent = result.request.from_address;
    $('#preview-status').textContent = result.sender_selection.live_enabled ? 'Ready to send' : 'Review ready';
    $('#preview-status').className = 'badge safe';
    $('#submit-message').disabled = !(state.status && state.status.external_delivery_enabled && result.sender_selection.live_enabled);
    addComposedActivity(result);
    renderValidation(validation);
    showStep('preview');
  }

  async function submitMessage() {
    if (!state.status || !state.status.external_delivery_enabled || !state.preview || !state.preview.sender_selection.live_enabled) return;
    if (!window.confirm(`Send this message from ${state.preview.sender_selection.address}?`)) return;
    const payload = formPayload();
    payload.confirm_send = true;
    let response;
    try {
      response = await fetch('/outbound-mail/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      toast(`Send failed: ${error.message}`, 'error');
      return;
    }
    const result = await response.json();
    if (!response.ok) {
      toast(result.message || result.error || 'Send failed.', 'error');
      return;
    }
    toast(`Message submitted. Control ID: ${result.control_id}`, 'success');
    state.preview = null;
    state.draftCommitted = true;
    $('#submit-message').disabled = true;
    await loadActivity();
  }

  function normalizedRemoteActivity(event) {
    return {
      controlId: event.control_id || '—',
      caseId: event.case_id || '—',
      recipient: event.recipient_count ? `${event.recipient_count} recipient(s)` : '—',
      subject: event.sender_address ? `Restricted — ${event.sender_address}` : 'Restricted in audit view',
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
    $('#activity-body').innerHTML = rows.length ? rows.map((row) => `<tr><td><strong>${escapeHtml(row.controlId)}</strong></td><td>${escapeHtml(row.caseId)}</td><td>${escapeHtml(row.recipient)}</td><td>${escapeHtml(row.subject)}</td><td><span class="status">${escapeHtml(row.status)}</span></td><td>${escapeHtml(row.event)}</td><td>${escapeHtml(row.confidence)}</td></tr>`).join('') : '<tr><td colspan="7" class="empty">No matching Mail Room activity.</td></tr>';
    updateActivityCount();
  }

  function exportCsv() {
    const records = [...state.activity, ...state.remoteActivity];
    if (!records.length) {
      toast('There is no activity to export yet.');
      return;
    }
    const header = ['Control ID', 'Case', 'Recipient', 'Subject', 'Status', 'Last event', 'Confidence'];
    const rows = records.map((row) => [row.controlId, row.caseId, row.recipient, row.subject, row.status, row.event, row.confidence]);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    const link = document.createElement('a');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    link.href = url;
    link.download = 'wwcx-mail-room-activity.csv';
    link.click();
    URL.revokeObjectURL(url);
    toast('Mail activity exported.', 'success');
  }

  function isTypingTarget(target) {
    return target instanceof HTMLElement && (target.matches('input, textarea, select') || target.isContentEditable);
  }

  function handleKeyboard(event) {
    const typing = isTypingTarget(event.target);
    if (event.key === 'Escape' && !typing && !$('#shortcut-dialog').open) {
      showStep('setup');
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      if (state.currentStep === 'compose' || state.currentStep === 'controls') {
        event.preventDefault();
        generatePreview();
      }
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey || typing) return;
    if (event.key.toLowerCase() === 'c') {
      event.preventDefault();
      showStep('compose');
      window.setTimeout(() => $('#to').focus(), 80);
    } else if (event.key === '/') {
      event.preventDefault();
      showStep('activity');
      window.setTimeout(() => $('#activity-search').focus(), 80);
    }
  }

  $$('.step-nav button').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.step)));
  $$('[data-next]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.next)));
  $$('[data-back]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.back)));
  $('#quick-compose').addEventListener('click', () => window.setTimeout(() => $('#to').focus(), 80));
  ['mailing-address', 'original-recipient', 'sender-profile', 'to', 'cc', 'bcc', 'subject', 'body', 'signer-name', 'signer-title', 'case-id', 'action-id', 'unsubscribe-url'].forEach((id) => {
    $(`#${id}`).addEventListener('input', markDraftChanged);
  });
  ['sender-profile', 'message-class', 'system-generated'].forEach((id) => {
    $(`#${id}`).addEventListener('change', markDraftChanged);
  });
  ['privacy-url', 'contact-email'].forEach((id) => $(`#${id}`).addEventListener('input', updateSetup));
  $('#message-class').addEventListener('change', () => $('#unsubscribe-wrap').classList.toggle('hidden', $('#message-class').value !== 'commercial'));
  ['generate-preview', 'generate-preview-options'].forEach((id) => $(`#${id}`).addEventListener('click', generatePreview));
  $('#submit-message').addEventListener('click', submitMessage);
  $('#copy-preview').addEventListener('click', async () => {
    if (!state.preview) {
      toast('Generate a review first.');
      return;
    }
    try {
      await navigator.clipboard.writeText(state.preview.body);
      toast('Final message copied.', 'success');
    } catch (error) {
      toast(`Could not copy message: ${error.message}`, 'error');
    }
  });
  $('#activity-search').addEventListener('input', renderActivity);
  $('#activity-status').addEventListener('change', renderActivity);
  $('#export-activity').addEventListener('click', exportCsv);
  $('#shortcut-help').addEventListener('click', () => $('#shortcut-dialog').showModal());
  document.addEventListener('keydown', handleKeyboard);
  window.addEventListener('beforeunload', (event) => {
    if (state.draftCommitted || !hasDraftContent()) return;
    event.preventDefault();
    event.returnValue = '';
  });
  $('#load-example').addEventListener('click', () => {
    $('#original-recipient').value = 'john@spiritcreekgardens.com';
    $('#to').value = 'records@example.com';
    $('#case-id').value = 'ENT-184366738';
    $('#action-id').value = 'ENT-ACT-014';
    $('#subject').value = 'Request for transfer, custody, and billing records';
    $('#body').value = 'Hello,\n\nPlease provide the complete chronology and supporting records identified in our correspondence.\n\nThank you.';
    markDraftChanged();
    toast('Example loaded. Nothing has been sent.');
  });

  updateGreeting();
  renderActivity();
  Promise.all([loadStatus(), loadActivity()]).catch((error) => {
    $('.mode-pill').innerHTML = '<span aria-hidden="true"></span>Mail Room unavailable';
    $('#setup-checklist').innerHTML = `<p class="error"><span>×</span>${escapeHtml(error.message)}</p>`;
    toast('Mail Room could not load its gateway status.', 'error');
  });
})();

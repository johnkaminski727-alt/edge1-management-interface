(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const state = { preview: null, activity: [] };

  function showStep(name) {
    $$('.panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === name));
    $$('.step-nav button').forEach((button) => button.classList.toggle('active', button.dataset.step === name));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function splitAddresses(value) {
    return value.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  }

  function escapeHeader(value) {
    return value.replace(/[\r\n]/g, ' ').trim();
  }

  function makeControlId() {
    const now = new Date();
    const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
    const random = crypto.getRandomValues(new Uint32Array(2));
    return `WWCX-${stamp}-${random[0].toString(16).padStart(8, '0')}${random[1].toString(16).padStart(8, '0')}`.toUpperCase();
  }

  function tokenFragment() {
    const bytes = crypto.getRandomValues(new Uint8Array(24));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }

  function updateSetup() {
    const checks = [
      ['Mailing address configured', Boolean($('#mailing-address').value.trim())],
      ['Delivery adapter selected', Boolean($('#provider').value)],
      ['Privacy page configured', Boolean($('#privacy-url').value.trim())],
      ['Live delivery authorized', false],
    ];
    $('#setup-checklist').innerHTML = checks.map(([label, ok]) => `<p class="${ok ? 'pass' : 'pending'}"><span>${ok ? '✓' : '○'}</span>${label}</p>`).join('');
    $('#summary-provider').textContent = $('#provider').value || 'Not configured';
  }

  function validate() {
    const errors = [];
    const warnings = [];
    const recipients = [...splitAddresses($('#to').value), ...splitAddresses($('#cc').value), ...splitAddresses($('#bcc').value)];
    if (!recipients.length) errors.push('Add at least one recipient.');
    if (!$('#subject').value.trim()) errors.push('Add a subject.');
    if (!$('#body').value.trim()) errors.push('Add a message body.');
    if (!$('#mailing-address').value.trim()) warnings.push('Mailing address is not configured; live submission remains blocked.');
    if (!$('#provider').value) warnings.push('No delivery adapter is selected.');
    if ($('#message-class').value === 'commercial' && !$('#unsubscribe-url').value.trim()) errors.push('Commercial messages require an unsubscribe or preference URL.');
    if ($('#include-action-link').checked && !$('#include-disclosure').checked) errors.push('Action links require a visible logging disclosure.');
    return { errors, warnings, recipients };
  }

  function renderFooter(controlId, actionUrl) {
    const lines = [
      '--',
      $('#signer-name').value.trim() || 'John Kaminski',
      $('#signer-title').value.trim() || 'Authorized Representative',
      `${$('#operating-name').value.trim()} | ${$('#legal-name').value.trim()}`,
      $('#mailing-address').value.trim() || '[Mailing address required before live delivery]',
      `Email: ${$('#contact-email').value.trim()} | Web: ${$('#website').value.trim()}`,
      '',
      '[WWCX-CORRESPONDENCE-CONTROL]',
      `Correspondence control: ${controlId}`,
    ];
    if ($('#include-action-link').checked) lines.push(`View the correspondence record or acknowledge receipt: ${actionUrl}`);
    lines.push('Access to the linked correspondence record may be logged for security, delivery verification, records management, and dispute resolution.');
    lines.push(`Privacy information: ${$('#privacy-url').value.trim()}`);
    if ($('#include-confidentiality').checked) {
      lines.push('', 'CONFIDENTIALITY AND RECORDS NOTICE: This message and any attachments may contain confidential information intended for the addressed recipient. If received in error, notify the sender and delete the material.');
    }
    lines.push('This notice does not create confidentiality, privilege, a contractual duty, or other legal rights where they do not otherwise exist.');
    if ($('#message-class').value === 'commercial') lines.push('', `Commercial-message preferences or unsubscribe: ${$('#unsubscribe-url').value.trim()}`);
    return lines.join('\n');
  }

  function generatePreview() {
    const result = validate();
    const controlId = makeControlId();
    const actionUrl = `https://ww.cx/correspondence/r/${tokenFragment()}`;
    const body = `${$('#body').value.trim()}\n\n${renderFooter(controlId, actionUrl)}`;
    const headers = {
      'X-WWCX-Control-ID': controlId,
      'X-WWCX-Policy': 'wwcx.outbound-mail-policy.v1',
      'X-WWCX-Tracking': 'disclosed-action-link; no-hidden-pixel',
    };
    if ($('#case-id').value.trim()) headers['X-WWCX-Case-ID'] = escapeHeader($('#case-id').value);
    if ($('#action-id').value.trim()) headers['X-WWCX-Action-ID'] = escapeHeader($('#action-id').value);

    state.preview = { controlId, actionUrl, body, headers, result };
    $('#message-preview').textContent = body;
    $('#headers-preview').textContent = Object.entries(headers).map(([key, value]) => `${key}: ${value}`).join('\n');
    $('#metadata-preview').innerHTML = [
      ['Class', $('#message-class option:checked').textContent],
      ['Recipients', String(result.recipients.length)],
      ['Retention', `${$('#retention').value} days`],
      ['IP treatment', $('#ip-mode option:checked').textContent],
      ['Provider', $('#provider').value || 'Not configured'],
    ].map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`).join('');
    const items = [
      ...result.errors.map((text) => `<p class="error">✕ ${text}</p>`),
      ...result.warnings.map((text) => `<p class="warning">! ${text}</p>`),
      ...(result.errors.length || result.warnings.length ? [] : ['<p class="pass">✓ Preview satisfies configured policy checks.</p>']),
    ];
    $('#validation-results').innerHTML = items.join('');
    $('#preview-status').textContent = result.errors.length ? 'Blocked' : 'Preview ready';
    $('#preview-status').className = `badge ${result.errors.length ? 'danger' : 'safe'}`;
    $('#submit-message').disabled = true;

    state.activity.unshift({
      controlId,
      caseId: $('#case-id').value.trim() || '—',
      recipient: result.recipients[0] || '—',
      subject: $('#subject').value.trim() || 'Untitled',
      status: 'Composed',
      event: new Date().toISOString(),
      confidence: 'Confirmed',
    });
    renderActivity();
    showStep('preview');
  }

  function renderActivity() {
    const query = $('#activity-search').value.toLowerCase();
    const status = $('#activity-status').value;
    const rows = state.activity.filter((row) => (!status || row.status === status) && Object.values(row).join(' ').toLowerCase().includes(query));
    $('#activity-body').innerHTML = rows.length ? rows.map((row) => `<tr><td>${row.controlId}</td><td>${row.caseId}</td><td>${row.recipient}</td><td>${row.subject}</td><td><span class="status">${row.status}</span></td><td>${row.event}</td><td>${row.confidence}</td></tr>`).join('') : '<tr><td colspan="7" class="empty">No matching events.</td></tr>';
  }

  function exportCsv() {
    const header = ['Control ID', 'Case', 'Recipient', 'Subject', 'Status', 'Last event', 'Confidence'];
    const rows = state.activity.map((row) => [row.controlId, row.caseId, row.recipient, row.subject, row.status, row.event, row.confidence]);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    link.download = 'wwcx-correspondence-matrix.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  $$('.step-nav button').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.step)));
  $$('[data-next]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.next)));
  $$('[data-back]').forEach((button) => button.addEventListener('click', () => showStep(button.dataset.back)));
  ['mailing-address', 'provider', 'privacy-url'].forEach((id) => $(`#${id}`).addEventListener('input', updateSetup));
  $('#message-class').addEventListener('change', () => $('#unsubscribe-wrap').classList.toggle('hidden', $('#message-class').value !== 'commercial'));
  $('#generate-preview').addEventListener('click', generatePreview);
  $('#copy-preview').addEventListener('click', async () => state.preview && navigator.clipboard.writeText(state.preview.body));
  $('#activity-search').addEventListener('input', renderActivity);
  $('#activity-status').addEventListener('change', renderActivity);
  $('#export-activity').addEventListener('click', exportCsv);
  $('#load-example').addEventListener('click', () => {
    $('#to').value = 'records@example.com';
    $('#case-id').value = 'ENT-184366738';
    $('#action-id').value = 'ENT-ACT-014';
    $('#subject').value = 'Request for transfer, custody, and billing records';
    $('#body').value = 'Hello,\n\nPlease provide the complete chronology and supporting records identified in our correspondence.\n\nThank you.';
  });

  updateSetup();
})();

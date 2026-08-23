const api = '/api/portability';
const $ = (id) => document.getElementById(id);
let activeFilter = '';

async function getJson(url) {
  const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin'});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

async function loadSummary() {
  const data = await getJson(`${api}/summary`);
  $('case-count').textContent = Object.values(data.cases || {}).reduce((a,b) => a + b, 0);
  $('number-count').textContent = data.numbers ?? 0;
  $('document-count').textContent = data.documents ?? 0;
}

async function loadCases() {
  $('status').textContent = 'Loading port cases…';
  const query = activeFilter ? `?state=${encodeURIComponent(activeFilter)}` : '';
  const data = await getJson(`${api}/cases${query}`);
  const list = $('cases'); list.innerHTML = '';
  for (const item of data.items || []) {
    const li = document.createElement('li');
    li.innerHTML = `<button data-id="${esc(item.id)}"><span><strong>${esc(item.customer_ref)}</strong><small>${esc(item.direction)} · ${esc(item.id)}</small></span><span class="badge">${esc(item.state.replaceAll('_',' '))}</span></button>`;
    li.querySelector('button').addEventListener('click', () => loadCase(item.id));
    list.appendChild(li);
  }
  $('status').textContent = `${(data.items || []).length} case${(data.items || []).length === 1 ? '' : 's'}`;
}

async function loadCase(id) {
  const item = await getJson(`${api}/case/${encodeURIComponent(id)}`);
  $('detail-title').textContent = item.customer_ref;
  const nums = (item.numbers || []).map(x => `<li>${esc(x.number)} <span>${esc(x.status)}</span></li>`).join('');
  const docs = (item.documents || []).map(x => `<li>${esc(x.document_type)} <span>${esc(x.received_at_utc)}</span></li>`).join('');
  $('detail').innerHTML = `<dl><dt>Case</dt><dd>${esc(item.id)}</dd><dt>Direction</dt><dd>${esc(item.direction)}</dd><dt>State</dt><dd>${esc(item.state)}</dd><dt>Losing carrier</dt><dd>${esc(item.losing_carrier || '—')}</dd><dt>Gaining carrier</dt><dd>${esc(item.gaining_carrier || '—')}</dd><dt>Requested date</dt><dd>${esc(item.desired_due_date || '—')}</dd><dt>FOC</dt><dd>${esc(item.foc_at_utc || '—')}</dd><dt>Cutover</dt><dd>${esc(item.scheduled_cutover_at_utc || '—')}</dd></dl><h3>Numbers</h3><ul>${nums || '<li>None</li>'}</ul><h3>Evidence</h3><ul>${docs || '<li>No documents linked</li>'}</ul>`;
}

async function refresh() {
  try { await Promise.all([loadSummary(), loadCases()]); }
  catch (error) { $('status').textContent = `Unavailable: ${error.message}`; }
}

document.querySelectorAll('.tabs button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.tabs button').forEach(x => x.classList.remove('active'));
  button.classList.add('active'); activeFilter = button.dataset.filter || ''; loadCases();
}));
$('refresh').addEventListener('click', refresh);
refresh();

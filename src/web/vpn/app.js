(() => {
  'use strict';
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const badge = (value, cls='') => `<span class="badge ${cls}">${esc(value)}</span>`;
  const telemetryByAddress = (payload) => Object.fromEntries((payload?.devices || []).map(item => [item.address, item]));
  async function fetchJson(url) { const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); }
  async function load() {
    const [data, telemetry] = await Promise.all([
      fetchJson('/edge1-ops/status/wireguard-identity.json'),
      fetchJson('/edge1-ops/status/wireguard-dns-security.json').catch(() => ({devices:[],summary:{}}))
    ]);
    const s = data.summary || {}, ts = telemetry.summary || {}, byAddress=telemetryByAddress(telemetry);
    document.getElementById('metrics').innerHTML = [
      ['Configured peers', s.peer_count ?? 0], ['Account-owned', s.owned_count ?? 0],
      ['Registration records', s.registered_count ?? 0], ['DNS blocks / 24h', ts.blocked_24h ?? 0]
    ].map(([k,v]) => `<article><span>${esc(k)}</span><strong>${esc(v)}</strong></article>`).join('');
    document.getElementById('devices').innerHTML = (data.devices || []).map(device => {
      const dns = device.dns || {}, sec = device.security || {}, address=((device.assigned_addresses||[])[0]||'').split('/')[0], obs=byAddress[address]||{}, q=obs.dns||{}, osec=obs.security||{};
      const security = [sec.spamhaus_enabled ? 'Spamhaus' : null, osec.crowdsec_observed ? 'CrowdSec' : null, sec.quarantined ? 'Quarantined' : null].filter(Boolean).join(' · ') || 'Standard';
      const owner=device.owner_display_name || device.owner_subject || 'Unassigned';
      return `<tr><td><strong>${esc(device.name)}</strong><small>${esc(device.owner_subject||'')}</small></td><td><code>${esc((device.assigned_addresses || []).join(', '))}</code></td><td>${esc(owner)}</td><td>${badge(device.registration_status, device.registration_status === 'registered' ? 'ok' : '')}</td><td>${badge(dns.filtering_enabled ? 'Filtered' : 'Unfiltered', dns.filtering_enabled ? 'ok' : 'warn')}<small>${esc(dns.server || '')} · split DNS preserved</small></td><td>${esc(security)}<small>${esc(q.queries_24h ?? 0)} queries · ${esc(q.blocked_24h ?? 0)} blocked / 24h</small></td></tr>`;
    }).join('') || '<tr><td colspan="6">No WireGuard peers found.</td></tr>';
    const generated=telemetry.generated_at ? new Date(telemetry.generated_at).toLocaleString() : 'current projection';
    document.getElementById('freshness').textContent = `Telemetry ${generated}`;
  }
  load().catch(err => {
    document.getElementById('devices').innerHTML = `<tr><td colspan="6">Unable to load VPN identity data: ${esc(err.message)}</td></tr>`;
    document.getElementById('freshness').textContent = 'Unavailable';
  });
})();

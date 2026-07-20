const stateClass={healthy:'ok',degraded:'warn',critical:'critical',registered:'ok',unreachable:'critical'};
const text=(value)=>String(value??'—');
function badge(value){const key=String(value).toLowerCase();return `<span class="badge ${stateClass[key]||''}">${text(value)}</span>`;}
function render(data){
 document.querySelector('#overall-title').textContent=`${data.overall_status} — ${data.site}`;
 document.querySelector('#overall-title').className=stateClass[data.overall_status]||'';
 document.querySelector('#generated-at').textContent=`Snapshot ${new Date(data.generated_at).toLocaleString()} · ${data.mode}`;
 const metrics=[['Active calls',data.metrics.active_calls],['Registrations',data.metrics.registrations],['Messages queued',data.metrics.messages_queued],['Trunks healthy',`${data.metrics.trunks_healthy}/${data.metrics.trunks_total}`],['Critical alerts',data.metrics.critical_alerts]];
 document.querySelector('#metrics').innerHTML=metrics.map(([label,value])=>`<article class="metric"><strong>${text(value)}</strong><span>${label}</span></article>`).join('');
 document.querySelector('#service-grid').innerHTML=data.services.map(s=>`<article class="service-card"><div class="section-heading"><h3>${text(s.name)}</h3>${badge(s.status)}</div><p>${text(s.role)}</p><small>Latency ${text(s.latency_ms)} ms · checked ${text(s.last_checked)}</small></article>`).join('');
 document.querySelector('#peer-rows').innerHTML=data.interconnects.map(p=>`<tr><td>${text(p.name)}</td><td>${badge(p.status)}</td><td>${text(p.latency_ms)} ms</td><td>${text(p.success_rate)}%</td><td>${text(p.active_calls)}</td></tr>`).join('');
 document.querySelector('#registration-rows').innerHTML=data.registrations.map(r=>`<tr><td>${text(r.endpoint)}</td><td>${badge(r.state)}</td><td>${text(r.transport)}</td><td>${text(r.user_agent)}</td><td>${text(r.expires_in_seconds)}s</td></tr>`).join('');
 document.querySelector('#alerts').innerHTML=data.alerts.length?data.alerts.map(a=>`<article class="alert"><h3 class="${stateClass[a.severity]||''}">${text(a.title)}</h3><p>${text(a.summary)}</p><small>${text(a.source)} · ${text(a.opened_at)}</small></article>`).join(''):'<p class="alert ok">No active alerts.</p>';

 document.querySelector('#sip-peer-cards').innerHTML=(data.interconnects||[]).map(p=>`
 <article class="service-card">
   <div class="section-heading">
     <h3>${text(p.name)}</h3>
     ${badge(p.status)}
   </div>
   <p>Endpoint: ${text(p.endpoint)}</p>
   <p>Latency: ${text(p.latency_ms)} ms</p>
   <p>Success: ${text(p.success_rate)}%</p>
   <p>Active calls: ${text(p.active_calls)}</p>
 </article>
 `).join('');
}
async function fetchJson(url){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}
async function loadSipHistory(){
 const target=document.querySelector('#sip-history');
 if(!target){return;}

 try{
  const history=await fetchJson('/api/telephony/health/history');

  const checks=(history.checks||[]).slice(-10).reverse();

  target.innerHTML=checks.length
   ? checks.map(c=>`
      <article class="alert">
        <h3 class="${stateClass[c.status]||''}">
          ${text(c.peer)} — ${text(c.status)}
        </h3>
        <p>
          SIP ${text(c.response_code)}
          · ${text(c.latency_ms)} ms
        </p>
        <small>${text(c.timestamp)}</small>
      </article>
    `).join('')
   : '<p class="alert ok">No SIP history available.</p>';

 }catch(error){
  target.innerHTML =
    '<p class="alert">SIP history unavailable.</p>';
 }
}


async function load(){
 const button=document.querySelector('#refresh');button.disabled=true;
 try{
  let data;
  try{data=await fetchJson('/api/telephony/status');}
  catch(liveError){data=await fetchJson('./telephony.fixture.json');data.mode=`fixture fallback (${liveError.message})`;}
  render(data);
  await loadSipHistory();
 }catch(error){document.querySelector('#overall-title').textContent='Snapshot unavailable';document.querySelector('#generated-at').textContent=error.message;}
 finally{button.disabled=false;}
}
document.querySelector('#refresh').addEventListener('click',load);load();

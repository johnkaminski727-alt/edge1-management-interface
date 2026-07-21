<?php
declare(strict_types=1);
require dirname(__DIR__) . '/includes/store-lib.php';
wwcx_session_start();
$user = wwcx_require_user('admin');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Electrum Console | WW.CX Admin</title>
<style>
:root{font-family:system-ui,sans-serif;color-scheme:dark}body{margin:0;background:#10151c;color:#eef3f8}main{max-width:1100px;margin:auto;padding:24px}.head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:22px}.card{background:#19222d;border:1px solid #314052;border-radius:12px;padding:18px}.label{color:#a9b8c8;font-size:.85rem}.value{font-size:1.55rem;font-weight:700;margin-top:6px;overflow-wrap:anywhere}button{border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer}.status{margin-top:18px;padding:12px;border-radius:8px;background:#19222d}.ok{color:#71d99a}.bad{color:#ff8c8c}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.83rem}.muted{color:#a9b8c8}
</style>
</head>
<body><main>
<div class="head"><div><h1>Electrum Console</h1><p class="muted">Read-only watch-wallet monitoring. Spending and signing are not available.</p></div><button id="refresh" type="button">Refresh</button></div>
<div id="status" class="status">Loading Electrum status…</div>
<section class="grid" aria-live="polite">
<div class="card"><div class="label">Confirmed balance</div><div id="confirmed" class="value">—</div></div>
<div class="card"><div class="label">Unconfirmed balance</div><div id="unconfirmed" class="value">—</div></div>
<div class="card"><div class="label">Unmatured balance</div><div id="unmatured" class="value">—</div></div>
<div class="card"><div class="label">Network</div><div id="network" class="value">—</div></div>
<div class="card"><div class="label">Synchronized</div><div id="synchronized" class="value">—</div></div>
<div class="card"><div class="label">Server</div><div id="server" class="value">—</div></div>
</section>
<div class="card" style="margin-top:16px"><div class="label">Wallet information</div><pre id="details">—</pre></div>
<script>
'use strict';
const $=id=>document.getElementById(id);
const display=v=>v===null||v===undefined||v===''?'—':String(v);
function balancePart(balance,key){return balance&&typeof balance==='object'?display(balance[key]):'—';}
async function refresh(){
 const button=$('refresh'); button.disabled=true; $('status').textContent='Refreshing…'; $('status').className='status';
 try{
  const response=await fetch('api/electrum-status.php',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
  const data=await response.json(); if(!response.ok||!data.ok) throw new Error(data.error||'Electrum unavailable');
  const info=data.info||{}, balance=data.balance||{};
  $('confirmed').textContent=balancePart(balance,'confirmed'); $('unconfirmed').textContent=balancePart(balance,'unconfirmed'); $('unmatured').textContent=balancePart(balance,'unmatured');
  $('network').textContent=display(info.network); $('synchronized').textContent=display(info.synchronized); $('server').textContent=display(info.server);
  $('details').textContent=JSON.stringify(info,null,2); $('status').textContent='Electrum watch wallet is available. Updated '+display(data.generated_at)+'.'; $('status').className='status ok';
 }catch(error){$('status').textContent=error instanceof Error?error.message:'Electrum unavailable';$('status').className='status bad';}
 finally{button.disabled=false;}
}
$('refresh').addEventListener('click',refresh); refresh();
</script>
</main></body></html>

"use strict";
(() => {
  const $ = id => document.getElementById(id), api = "./api/";
  let mode = "inbox", offset = 0, more = false, draftId = null, metadata = {}, dirty = false, generation = 0, editorSession = 0, saving = false;
  function say(text) { $("feedback").textContent = text; }
  async function request(path, data) {
    const response = await fetch(api + path, {credentials:"same-origin", cache:"no-store", ...(data === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json", "X-Mail-Room-Request":"1"}, body:JSON.stringify(data)})});
    if (response.status === 401 || response.redirected) throw new Error("Your session has expired. Sign in to Edge1 again; unsaved text stays on this page.");
    if (!(response.headers.get("content-type") || "").includes("application/json")) throw new Error("Mail Room is unavailable or requires an Edge1 login.");
    const result = await response.json(); if (!response.ok) throw new Error(result.error || "Request failed"); return result;
  }
  function element(tag, text, className) { const n = document.createElement(tag); n.textContent = text; if(className)n.className=className; return n; }
  function canLeave() { return !dirty || window.confirm("Leave this unsaved draft? Save it first to keep your changes."); }
  function showEditor(payload = {}, id = null) {
    if (!canLeave()) return;
    editorSession++; $("editor").reset(); draftId = id; metadata = {};
    for(const key of ["thread_id","source_message_id","in_reply_to","references"]) if(payload[key]) metadata[key]=payload[key];
    for(const field of $("editor").elements) if(field.name) field.value = Array.isArray(payload[field.name]) ? payload[field.name].join(", ") : payload[field.name] || (field.name === "message_class" ? "business_correspondence" : "");
    $("editor").hidden=false; $("prepared").hidden=true; $("saved").textContent=id ? "Saved draft opened." : "New draft — not saved yet."; dirty=false;
    $("editor").scrollIntoView({behavior:"smooth",block:"start"});
  }
  function payload() {
    const data = {...metadata}; for(const field of $("editor").elements) if(field.name && field.value.trim()) data[field.name] = ["to","cc","bcc"].includes(field.name) ? field.value.split(",").map(s=>s.trim()).filter(Boolean) : field.value;
    return data;
  }
  async function save() {
    if(saving) throw new Error("A draft save is already in progress.");
    saving=true; const session=editorSession, snapshot=payload();
    try { const d = await request("drafts", {id:draftId, payload:snapshot});
      if(session===editorSession) { draftId=d.id; dirty=JSON.stringify(payload())!==JSON.stringify(snapshot); $("saved").textContent=dirty ? "Saved earlier version · New changes not saved" : "Saved on Edge1 · " + new Date(d.updated).toLocaleString(); }
      say("Draft saved. Nothing sent."); return d;
    } finally { saving=false; }
  }
  function renderMail(m, container) {
    const article=element("article", "", "thread-message"); article.append(element("h2",m.subject || "(No subject)"));
    const meta=element("div","","mail-meta"); meta.append(element("p","From: " + m.sender), element("p","Original recipients: " + (m.recipients || []).join(", ")),element("p",new Date(m.occurred_at).toLocaleString())); article.append(meta,element("div",m.body_text || "(No plain-text body)","mail-text")); container.append(article);
  }
  async function openMessage(m) {
    if (!canLeave()) return;
    const current=++generation; say("Opening thread…");
    const data = await request("thread/" + encodeURIComponent(m.thread_id)); if(current !== generation)return;
    $("editor").hidden=true; dirty=false; $("reading").replaceChildren();
    for(const item of data.thread.messages) renderMail(item,$("reading"));
    const reply=element("button","Draft a reply"); reply.onclick=()=>{
      const addresses=m.recipients || [], from=(m.sender.match(/<([^<>]+)>/) || [null,m.sender])[1];
      showEditor({to:[from],subject:/^re:/i.test(m.subject) ? m.subject : "Re: " + m.subject, original_recipient:addresses.length===1 ? addresses[0] : "",thread_id:m.thread_id,source_message_id:m.message_id,in_reply_to:m.message_id});
    }; $("reading").append(reply); say("Thread opened. Email content is displayed as plain text.");
  }
  async function load() {
    const current=++generation; $("list").replaceChildren(element("p","Loading…"));
    const q=new FormData($("search")), filters=new URLSearchParams({q:q.get("q"),offset:String(offset)}); if(q.get("recipient")) filters.set("recipient",q.get("recipient"));
    const result = await request(mode==="inbox" ? "messages?"+filters : "drafts"); if(current !== generation)return;
    const items=mode==="inbox" ? result.messages : result.drafts; more=!!result.has_more; $("list").replaceChildren();
    for(const m of items) { const button=element("button","","message"); button.append(element("strong",m.subject || "(No subject)"),element("span",mode==="inbox" ? m.sender : "Saved draft"),element("span",new Date(m.occurred_at || m.updated).toLocaleString())); button.onclick=()=> (mode==="inbox" ? openMessage(m) : request("draft/"+m.id).then(d=>showEditor(d.payload,d.id))).catch(e=>say(e.message)); $("list").append(button); }
    if(!items.length) $("list").append(element("p",mode==="inbox" ? "No messages match. Connected provider mail will appear here after setup." : "No saved drafts yet."));
    $("previous").disabled=offset===0 || mode!=="inbox"; $("next").disabled=!more || mode!=="inbox"; $("page").textContent=mode==="inbox" ? "Page "+(offset/25+1) : "Latest 100";
  }
  function safely(fn) { return (...args)=>{ if(args[0] && args[0].type === "submit") args[0].preventDefault(); return Promise.resolve().then(()=>fn(...args)).catch(e=>say(e.message)); }; }
  $("search").onsubmit=safely(e=>{e.preventDefault();offset=0;return load();});
  for(const name of ["inbox","drafts"]) $(name).onclick=safely(()=>{mode=name;offset=0;$("search").hidden=name!=="inbox";for(const n of ["inbox","drafts"])$(n).classList.toggle("active",n===name);return load();});
  $("previous").onclick=safely(()=>{offset=Math.max(0,offset-25);return load();}); $("next").onclick=safely(()=>{offset+=25;return load();});
  $("compose").onclick=()=>showEditor(); $("close").onclick=()=>{if(canLeave()){$("editor").hidden=true;dirty=false;}};
  $("editor").addEventListener("invalid",()=>{$("editor").querySelector("details").open=true;},true);
  $("editor").oninput=()=>{dirty=true;$("prepared").hidden=true;$("saved").textContent="Unsaved changes";};
  $("save").onclick=safely(save);
  $("editor").onsubmit=safely(async e=>{e.preventDefault();const d=await save();const result=await request("prepare",{id:d.id});if(draftId!==d.id || JSON.stringify(payload())!==JSON.stringify(d.payload)){say("Earlier draft version prepared. Save and prepare your new changes for an updated preview.");return;}$("prepared").textContent="Prepared for review — not sent\n\nFrom: " + (result.request?.from_address || "Selected by identity policy") + "\nTo: " + (result.request?.recipients || d.payload.to || []).join(", ") + "\nSubject: " + (result.request?.subject || d.payload.subject) + "\n\n" + (result.body || d.payload.body);$("prepared").hidden=false;say("Prepared for review. Nothing sent.");});
  window.addEventListener("beforeunload",e=>{if(dirty){e.preventDefault();e.returnValue="";}});
  request("status").then(s=>{$("connection").textContent=s.provider_connected ? "Provider connected · Sending disabled · Manual drafts available" : "Local Mail Room ready · Provider credentials still needed · Only commissioning mail is available · Sending disabled";}).catch(e=>{$("connection").textContent=e.message;});
  safely(load)();
})();

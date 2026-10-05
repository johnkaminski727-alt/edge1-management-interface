"use strict";
(() => {
  const $ = id => document.getElementById(id), api = "./api/", views=["inbox","drafts","activity","daily"];
  let mode="inbox",offset=0,more=false,draftId=null,metadata={},dirty=false,generation=0,editorSession=0,saving=false,autosave=null,senders=null;
  function say(text){$("feedback").textContent=text;}
  async function request(path,data){
    const r=await fetch(api+path,{credentials:"same-origin",cache:"no-store",...(data===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Mail-Room-Request":"1"},body:JSON.stringify(data)})});
    if(r.status===401||r.redirected)throw new Error("Your session has expired. Sign in to Edge1 again; unsaved text stays on this page.");
    if(!(r.headers.get("content-type")||"").includes("application/json"))throw new Error("Mail Room is unavailable or requires an Edge1 login.");
    const result=await r.json();if(!r.ok)throw new Error(result.error||"Request failed");return result;
  }
  function element(tag,text,className){const n=document.createElement(tag);n.textContent=text;if(className)n.className=className;return n;}
  function safely(fn){return(...args)=>{if(args[0]?.type==="submit")args[0].preventDefault();return Promise.resolve().then(()=>fn(...args)).catch(e=>say(e.message));};}
  function canLeave(){return !dirty||window.confirm("Leave this unsaved draft? Save it first to keep your changes.");}
  function selected(){return senders?.senders.find(s=>s.address===$("from").value);}
  function signature(overwrite=false){
    const item=selected();if(!item)return;
    const original=$("editor").elements.original_recipient.value.trim().toLowerCase(),mapped=senders.recipient_to_sender[original];
    $("from").disabled=!!original; // Replies retain canonical original-recipient policy.
    if(mapped)$("from").value=mapped;
    const effective=selected()||item;
    $("sender-note").textContent=original ? "Reply sender follows the original receiving address. Sending is disabled." : effective.organization+" · "+(effective.live_enabled?"Outbound identity enabled; sending is currently disabled":"Available for drafting; outbound commissioning pending");
    for(const name of ["signer_name","signer_title","mailing_address"]){const f=$("editor").elements[name];if(overwrite||!f.value)f.value=effective.signature[name]||"";}
  }
  function showEditor(data={},id=null){
    if(!canLeave())return;clearTimeout(autosave);editorSession++;$("editor").reset();draftId=id;metadata={};
    for(const key of ["thread_id","source_message_id","in_reply_to","references"])if(data[key])metadata[key]=data[key];
    for(const field of $("editor").elements)if(field.name)field.value=Array.isArray(data[field.name])?data[field.name].join(", "):data[field.name]||(field.name==="message_class"?"business_correspondence":"");
    if(senders){$("from").value=data.identity_hint||senders.recipient_to_sender[data.original_recipient]||senders.default_sender;signature();}
    $("editor").hidden=false;$("prepared").hidden=true;$("saved").textContent=id?"Saved draft opened.":"New draft — not saved yet.";$("autosave-state").textContent="Drafts autosave on Edge1 after a short pause.";dirty=false;
    $("editor").scrollIntoView({behavior:"smooth",block:"start"});
  }
  function payload(){const d={...metadata};for(const f of $("editor").elements)if(f.name&&f.value.trim())d[f.name]=["to","cc","bcc"].includes(f.name)?f.value.split(",").map(s=>s.trim()).filter(Boolean):f.value;return d;}
  async function save(quiet=false){
    if(saving){if(quiet){autosave=setTimeout(()=>save(true).catch(e=>say(e.message)),1000);return;}throw new Error("A draft save is already in progress.");}
    saving=true;const session=editorSession,snapshot=payload();
    try{const d=await request("drafts",{id:draftId,payload:snapshot});if(session===editorSession){draftId=d.id;dirty=JSON.stringify(payload())!==JSON.stringify(snapshot);$("saved").textContent=dirty?"Saved earlier version · New changes not saved":"Saved on Edge1 · "+new Date(d.updated).toLocaleString();}if(!quiet)say("Draft saved. Nothing sent.");return d;}finally{saving=false;}
  }
  function changed(){dirty=true;$("prepared").hidden=true;$("saved").textContent="Unsaved changes · Autosave pending";clearTimeout(autosave);autosave=setTimeout(()=>save(true).catch(e=>{say(e.message);$("saved").textContent="Autosave failed · Unsaved text is still here";}),1500);}
  function renderMail(m,container){
    const a=element("article","","thread-message");a.append(element("h2",m.subject||"(No subject)"));const meta=element("div","","mail-meta");meta.append(element("p","From: "+m.sender),element("p","Original recipients: "+(m.recipients||[]).join(", ")),element("p",new Date(m.occurred_at).toLocaleString()));
    const email=(m.sender.match(/<([^<>]+)>/)||[null,m.sender])[1];const link=element("a","Find sender in Contacts");link.href="/edge1-ops/contacts/?q="+encodeURIComponent(email);link.target="_blank";link.rel="noopener";meta.append(link);a.append(meta,element("div",m.body_text||"(No plain-text body)","mail-text"));container.append(a);
  }
  async function openMessage(m){
    if(!canLeave())return;const current=++generation;say("Opening thread…");const data=await request("thread/"+encodeURIComponent(m.thread_id));if(current!==generation||!canLeave())return;
    clearTimeout(autosave);$("editor").hidden=true;dirty=false;$("reading").replaceChildren();for(const item of data.thread.messages)renderMail(item,$("reading"));
    const actions=element("div","","actions"),reply=element("button","Draft a reply"),archive=element("button",m.archived?"Move to inbox":"Archive"),read=element("button","Mark unread"),tag=element("button","Edit tags");
    const replyData=()=>({to:[(m.sender.match(/<([^<>]+)>/)||[null,m.sender])[1]],subject:/^re:/i.test(m.subject)?m.subject:"Re: "+m.subject,original_recipient:m.recipients.length===1?m.recipients[0]:"",thread_id:m.thread_id,source_message_id:m.message_id,in_reply_to:m.message_id});
    reply.onclick=()=>showEditor(replyData());archive.onclick=safely(async()=>{await request("flags",{message_id:m.message_id,archived:!m.archived});await load();say(m.archived?"Moved to inbox.":"Archived in Mail Room. Source mail is retained.");});read.onclick=safely(async()=>{await request("flags",{message_id:m.message_id,is_read:false});await load();say("Marked unread.");});tag.onclick=safely(async()=>{const text=window.prompt("Tags, separated by commas",(m.tags||[]).join(", "));if(text===null)return;await request("flags",{message_id:m.message_id,tags:text.split(",").map(t=>t.trim()).filter(Boolean)});await load();say("Tags saved.");});actions.append(reply,archive,read,tag);$("reading").append(actions);
    const box=element("section","","assistant-box");box.append(element("h2","AVA assistance"),element("p","Ask AVA’s configured model to review this thread. Suggestions stay editable; nothing is sent or applied automatically."));const summary=element("button","Summarize thread"),suggest=element("button","Suggest reply"),output=element("pre",""),use=element("button","Use suggestion in a draft");use.hidden=true;
    for(const [b,operation] of [[summary,"summary"],[suggest,"reply"]])b.onclick=safely(async()=>{summary.disabled=suggest.disabled=true;use.hidden=true;output.textContent="AVA is reviewing the thread…";try{const d=await request("assist",{operation,thread_id:m.thread_id});output.textContent=d.text+(d.truncated_context?"\n\nOnly the latest bounded excerpts were reviewed.":"");use.hidden=operation!=="reply";use.onclick=()=>showEditor({...replyData(),body:d.text});}finally{summary.disabled=suggest.disabled=false;}});
    box.append(summary,suggest,output,use);$("reading").append(box);
    await request("flags",{message_id:m.message_id,is_read:true});
    const attachments=await request("attachments/"+encodeURIComponent(m.message_id));const check=element("section","","assistant-box");check.append(element("h2","Attachment checks"));check.append(element("p",attachments.indexed===false?"Attachment inventory not yet indexed. Downloads blocked.":attachments.attachments.length?"Downloads remain disabled pending attachment acceptance.":"No attachments found in the native archive."));for(const a of attachments.attachments)check.append(element("p",a.filename+" · "+Math.ceil(a.size_bytes/1024)+" KB · "+a.state.replaceAll("_"," ")));$("reading").append(check);say("Thread opened. Email content is displayed as plain text.");
  }
  async function load(){
    const current=++generation;$("list").replaceChildren(element("p","Loading…"));const filters=new URLSearchParams(new FormData($("search")));filters.set("offset",offset);
    if(mode==="daily"){
      const reports=await request("reports");if(current!==generation)return;$("list").replaceChildren();
      for(const day of reports.dates){const b=element("button",day,"message");b.onclick=safely(async()=>{if(!canLeave())return;const r=await request("report/"+day);$("editor").hidden=true;clearTimeout(autosave);dirty=false;$("reading").replaceChildren(element("h2","Daily activity · "+r.date),element("p",r.timezone+" · "+(r.complete_day?"Completed day":"Today so far")+" · Updated "+new Date(r.generated_at).toLocaleString()));
        const labels={successful_logins:"Successful logins",unique_login_users:"Users who logged in",failed_logins:"Failed login attempts",logouts:"Logouts",messages_sent:"Messages submitted to provider",messages_received:"Messages received",commissioning_messages_received:"Commissioning messages",drafts_prepared:"Draft preparations",new_contacts:"New contacts",new_contact_points:"New contact points",new_contact_relationships:"New relationships"};
        for(const [key,value] of Object.entries(r.counts))$("reading").append(element("p",(labels[key]||key)+": "+(value===null?"Unavailable":value)));
        for(const note of r.notes)$("reading").append(element("p",note,"small"));for(const [source,state] of Object.entries(r.sources))if(state!=="available")$("reading").append(element("p",source+": "+state,"notice"));});$("list").append(b);}
      if(!reports.dates.length)$("list").append(element("p","First report is being generated."));$("previous").disabled=$("next").disabled=true;$("page").textContent="Saskatchewan time";return;
    }
    const result=await request(mode==="inbox"?"messages?"+filters:mode==="drafts"?"drafts":"activity");if(current!==generation)return;const items=mode==="inbox"?result.messages:mode==="drafts"?result.drafts:result.events;more=!!result.has_more;$("list").replaceChildren();
    for(const m of items){const b=element("button","","message"+(!m.is_read&&mode==="inbox"?" unread":""));b.append(element("strong",m.subject||"(No subject)"),element("span",mode==="inbox"?m.sender:mode==="drafts"?"Saved draft":"Prepared · not sent"),element("span",new Date(m.occurred_at||m.updated).toLocaleString()));if(m.tags?.length)b.append(element("span",m.tags.join(" · ")));b.onclick=safely(()=>mode==="inbox"?openMessage(m):request("draft/"+(m.id||m.draft_id)).then(d=>showEditor(d.payload,d.id)));$("list").append(b);}
    if(!items.length)$("list").append(element("p",mode==="inbox"?"No matching messages. Provider intake is pending.":mode==="drafts"?"No saved drafts yet.":"No prepared messages yet. Sending and provider delivery receipts remain unavailable."));
    $("previous").disabled=offset===0||mode!=="inbox";$("next").disabled=!more||mode!=="inbox";$("page").textContent=mode==="inbox"?"Page "+(offset/25+1):"Latest 100";
  }
  $("search").onsubmit=safely(()=>{offset=0;return load();});
  for(const name of views)$(name).onclick=safely(()=>{mode=name;offset=0;$("search").hidden=name!=="inbox";for(const n of views)$(n).classList.toggle("active",n===name);return load();});
  $("previous").onclick=safely(()=>{offset=Math.max(0,offset-25);return load();});$("next").onclick=safely(()=>{offset+=25;return load();});
  $("compose").onclick=()=>showEditor();$("close").onclick=()=>{if(canLeave()){clearTimeout(autosave);$("editor").hidden=true;dirty=false;editorSession++;}};
  $("editor").addEventListener("invalid",()=>{$("editor").querySelector("details").open=true;},true);$("editor").oninput=changed;
  $("from").onchange=()=>{signature(true);changed();};$("editor").elements.original_recipient.onchange=()=>{signature();changed();};
  $("save").onclick=safely(()=>{clearTimeout(autosave);return save();});
  $("remember-signature").onclick=safely(async()=>{const item=selected();if(!item)throw new Error("Select a sender first.");const signature={};for(const k of ["signer_name","signer_title","mailing_address"])signature[k]=$("editor").elements[k].value.trim();await request("signature",{address:item.address,signature});item.signature=signature;say("Signature remembered for "+item.address);});
  $("editor").onsubmit=safely(async()=>{clearTimeout(autosave);const d=await save();const result=await request("prepare",{id:d.id});if(draftId!==d.id||JSON.stringify(payload())!==JSON.stringify(d.payload)){say("Earlier version prepared. Prepare your new changes for an updated preview.");return;}$("prepared").textContent="Prepared for review — not sent\n\nFrom: "+result.request.from_address+"\nTo: "+result.request.recipients.join(", ")+"\nSubject: "+result.request.subject+"\n\n"+result.body;$("prepared").hidden=false;say("Prepared with organization signature and footer. Nothing sent.");});
  window.addEventListener("beforeunload",e=>{if(dirty){e.preventDefault();e.returnValue="";}});
  request("senders").then(d=>{senders=d;$("from").replaceChildren();for(const s of d.senders){const o=element("option",s.address+" — "+s.organization+(s.live_enabled?"":" · draft only"));o.value=s.address;$("from").append(o);}$("from").value=d.default_sender;for(const domain of d.domains){const o=element("option",domain);o.value=domain;$("domain").append(o);}if(!$("editor").hidden)signature();}).catch(e=>say(e.message));
  request("status").then(s=>{$("connection").textContent=s.provider_connected?"Provider connected · Sending disabled":"Local Mail Room ready · Provider credentials pending · Sending disabled";}).catch(e=>{$("connection").textContent=e.message;});safely(load)();
})();

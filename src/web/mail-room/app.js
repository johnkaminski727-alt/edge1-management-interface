"use strict";
(() => {
  const $ = id => document.getElementById(id), api = "./api/", views=["inbox","drafts","activity","daily","filtering","readiness"];
  let mode="inbox",offset=0,more=false,draftId=null,metadata={},dirty=false,generation=0,editorSession=0,saving=false,autosave=null,senders=null;
  function say(text){$("feedback").textContent=text;}
  async function request(path,data){
    const r=await fetch(api+path,{credentials:"same-origin",cache:"no-store",...(data===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Mail-Room-Request":"1"},body:JSON.stringify(data)})});
    if(r.status===401||r.redirected)throw new Error("Your session has expired. Sign in to Edge1 again; unsaved text stays on this page.");
    if(!(r.headers.get("content-type")||"").includes("application/json"))throw new Error("Mail Room is unavailable or requires an Edge1 login.");
    if(r.status===403)throw new Error("Mail Room requires an authenticated admin session. Unsaved text stays on this page.");
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
  function securityDetails(decision, container){
    if(decision.operator_report)container.append(element("p",decision.operator_report==="phishing"?"Reported phishing · Awaiting confirmation":decision.operator_report==="confirmed_phishing"?"Confirmed phishing":decision.operator_report.startsWith("reviewed_release:")?"Released after manual review":"Operator classification: "+decision.operator_report.replaceAll("_"," ")));
    container.append(element("h2", "Security · "+decision.state),element("p", "Sender: "+(decision.authentication?.status||"not_verified").replaceAll("_"," ")),element("p", "SPF: "+(decision.authentication?.spf||"not verified")+" · DKIM: "+(decision.authentication?.dkim||"not verified")+" · DMARC: "+(decision.authentication?.dmarc||"not verified")),element("p", (decision.reasons||[]).join(" · ").replaceAll("_"," ")),element("p", "Domain authentication does not verify the person or guarantee safe content.", "small"));
  }
  function securityActions(m, container, decision){
    const actions=element("div","","actions");
    for(const [label,action] of [["Spam","spam"],["Not spam","not_spam"],["Report phishing","phishing"],...(decision?.state==="quarantine"?[["Confirm phishing","confirmed_phishing"],["Release after review","release"]]:[])]){
      const b=element("button",label);b.type="button";
      b.onclick=safely(async()=>{
        if(action==="release"&&!window.confirm("Release this message to the inbox and AVA after your review? Malware and incomplete checks cannot be overridden."))return;
        let interacted=false;
        if(action==="phishing"){
          if(!window.confirm("Report this message as suspected phishing and move it to quarantine? Related messages may also be held for review."))return;
          interacted=window.confirm("Did you click a link, enter credentials, or open an attachment from this message? OK records an interaction; Cancel records no interaction.");
        }
        if(action==="confirmed_phishing"&&!window.confirm("Record this as confirmed phishing? Ordinary release will remain blocked."))return;
        const result=await request("security-action",{message_id:m.message_id,action,interacted,reviewed:action==="release"});
        $("reading").replaceChildren(element("h2","Message moved to "+result.state));await load();
        say(interacted?"Phishing reported. Stop interacting with the message. If you entered a password, change it through the service’s known website and revoke active sessions; if you opened a file, arrange a device security check.":"Security classification saved. Related messages flagged: "+result.related_flagged);
      });actions.append(b);
    }container.append(actions);
  }
  async function openMessage(m){
    if(!canLeave())return;const current=++generation;
    const decision=await request("security/"+encodeURIComponent(m.message_id));
    if(current!==generation)return;
    if(decision.state!=="released"){
      clearTimeout(autosave);$("editor").hidden=true;dirty=false;$("reading").replaceChildren(element("h2",m.subject||"(No subject)"),element("p","From: "+m.sender));securityDetails(decision,$("reading"));
      const review=element("button","Review plain text without AVA");review.onclick=safely(async()=>{
        if(!window.confirm("Display potentially malicious correspondence as plain text for manual review? Attachments and AVA remain unavailable."))return;
        const result=await request("review",{message_id:m.message_id,acknowledged:true});
        const body=element("section","","thread-message");renderMail(result.message,body);$("reading").append(body);review.disabled=true;
      });$("reading").append(review);securityActions(m,$("reading"),decision);say("Held mail stays outside AVA and the normal inbox.");return;
    }
    say("Opening thread…");const data=await request("thread/"+encodeURIComponent(m.thread_id));if(current!==generation||!canLeave())return;
    clearTimeout(autosave);$("editor").hidden=true;dirty=false;$("reading").replaceChildren();for(const item of data.thread.messages)renderMail(item,$("reading"));
    securityDetails(decision,$("reading"));securityActions(m,$("reading"),decision);
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
    if(mode==="readiness"){
      const report=await request("readiness");if(current!==generation)return;
      $("list").replaceChildren(element("p","Readiness evidence for each domain. No routing changes or sending are enabled."));
      const render=()=>{
        if(!canLeave())return;clearTimeout(autosave);$("editor").hidden=true;dirty=false;
        $("reading").replaceChildren(element("h2","Mail readiness & health"),element("p","Updated "+new Date(report.generated_at).toLocaleString()));
        if(Date.now()-Date.parse(report.generated_at)>15*60000)$("reading").append(element("p","Monitoring report is stale; live health is not confirmed.","notice"));
        for(const warning of report.warnings)$("reading").append(element("p",warning.replaceAll("_"," "),"notice"));
        const q=report.backlog;
        $("reading").append(element("h2","Intake monitoring"),element("p","Pending or unchecked: "+q.pending_or_unchecked+" · Oldest pending: "+(q.oldest_pending_age_seconds===null?"none":Math.ceil(q.oldest_pending_age_seconds/60)+" minutes")),element("p","Archives: "+q.archives+" · Storage free: "+(report.storage.free_bytes/1024**3).toFixed(1)+" GB · Used: "+report.storage.used_percent+"%"));
        for(const [unit,state] of Object.entries(report.services))$("reading").append(element("p",unit+": "+state,"small"));
        showUpdates(report.updates,$("reading"));
        $("reading").append(element("h2","Recovery rehearsal"),element("p",report.recovery.state==="passed"?"Passed "+new Date(report.recovery.completed_at).toLocaleString()+" · SQLite, archive/config hashes and isolated spam-learning store verified. Production was not restored.":"Not yet rehearsed."));
        $("reading").append(element("h2","Access and retention"));for(const [name,value] of Object.entries(report.access_policy))$("reading").append(element("p",name.replaceAll("_"," ")+": "+value,"small"));
      };
      for(const d of report.domains){const b=element("button",d.domain+" · Not commissioned","message");b.onclick=()=>{
        if(!canLeave())return;clearTimeout(autosave);$("editor").hidden=true;dirty=false;
        $("reading").replaceChildren(element("h2","Domain readiness · "+d.domain),element("p",d.registered_senders+" registered sender identities · Sending disabled"));
        if(d.dns_baseline?.captured_at)$("reading").append(element("p","DNS baseline captured "+new Date(d.dns_baseline.captured_at).toLocaleString()+" · Observed MX answers: "+d.dns_baseline.mx_answer_count+" · External authoritative verification remains pending.","small"));
        for(const [name,state] of Object.entries(d.checks))$("reading").append(element("p",name.replaceAll("_"," ")+": "+state.replaceAll("_"," "),state==="verified"?"small":"notice"));
        $("reading").append(element("p","Commissioning evidence must include external DNS checks and real delivery tests. Existing records or local tests alone do not prove migration readiness."));
      };$("list").append(b);}
      const health=element("button","Overall health, access & recovery","message");health.onclick=render;$("list").prepend(health);render();
      $("previous").disabled=$("next").disabled=true;$("page").textContent="Five domains";return;
    }
    if(mode==="filtering"){
      const config=await request("filter-settings");if(current!==generation)return;$("list").replaceChildren(element("p","Choose a receiving domain to tune spam thresholds."));
      for(const [domain,settings] of Object.entries(config.domains)){
        const b=element("button",domain,"message");b.onclick=()=>{
          if(!canLeave())return;clearTimeout(autosave);$("editor").hidden=true;dirty=false;
          const form=element("form","");form.append(element("h2","Filtering · "+domain));
          const fields={};for(const [name,label] of [["junk_score","Junk score"],["quarantine_score","Quarantine score"],["trusted_senders","Trusted sender addresses, one per line"]]){
            const l=element("label",label),input=document.createElement(name==="trusted_senders"?"textarea":"input");
            if(name!=="trusted_senders"){input.type="number";input.min=3;input.max=30;input.step=0.5;input.required=true;}else input.rows=5;
            input.value=Array.isArray(settings[name])?settings[name].join("\n"):settings[name];fields[name]=input;l.append(input);form.append(l);
          }
          form.append(element("p","Trusted senders receive only a small spam-score adjustment when aligned authentication passes. Malware and phishing checks remain in force."),element("button","Save domain settings"));
          form.onsubmit=safely(async()=>{await request("filter-settings",{domain,junk_score:Number(fields.junk_score.value),quarantine_score:Number(fields.quarantine_score.value),trusted_senders:fields.trusted_senders.value.split(/\n/).map(s=>s.trim()).filter(Boolean)});say("Domain filtering settings saved. Future scans use these settings.");});$("reading").replaceChildren(form);
        };$("list").append(b);
      }$("previous").disabled=$("next").disabled=true;$("page").textContent="Per-domain rules";return;
    }
    if(mode==="daily"){
      const reports=await request("reports");if(current!==generation)return;$("list").replaceChildren();
      for(const day of reports.dates){const b=element("button",day,"message");b.onclick=safely(async()=>{if(!canLeave())return;const r=await request("report/"+day);$("editor").hidden=true;clearTimeout(autosave);dirty=false;$("reading").replaceChildren(element("h2","Daily activity · "+r.date),element("p",r.timezone+" · "+(r.complete_day?"Completed day":"Today so far")+" · Updated "+new Date(r.generated_at).toLocaleString()));
        const labels={successful_logins:"Successful logins",unique_login_users:"Users who logged in",failed_logins:"Failed login attempts",logouts:"Logouts",messages_sent:"Messages submitted to provider",messages_received:"Messages received",commissioning_messages_received:"Commissioning messages",drafts_prepared:"Draft preparations",messages_classified_junk:"Junk classifications",messages_quarantined:"Quarantine classifications",messages_held_pending:"Pending-check classifications",phishing_reports:"Reported phishing",confirmed_phishing:"Confirmed phishing",spam_reports:"Spam reports",not_spam_corrections:"Not spam corrections",manual_releases:"Reviewed releases",related_phishing_holds:"Related messages held",new_contacts:"New contacts",new_contact_points:"New contact points",new_contact_relationships:"New relationships"};
        for(const [key,value] of Object.entries(r.counts))$("reading").append(element("p",(labels[key]||key)+": "+(value===null?"Unavailable":value)));
        showUpdates(r.security_updates,$("reading"));
        if(r.mail_health?.warnings)for(const warning of r.mail_health.warnings)$("reading").append(element("p","Mail health: "+warning.replaceAll("_"," "),"notice"));
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
  function showUpdates(updates, target){
    if(!updates)return;
    target.append(element("h2","Definition and rule updates"));
    for(const [name,job] of Object.entries(updates.jobs)){
      const success=job.last_success?new Date(job.last_success*1000).toLocaleString():"No successful check recorded";
      target.append(element("p",(name==="definitions"?"Malware definitions":"Packaged spam rules and scanner engines")+": "+job.schedule+" · Last success: "+success+" · "+job.last_result+(job.stale?" · OVERDUE":""),job.stale||job.last_result!=="success"?"notice":"small"));
    }
    target.append(element("p","Warnings after 3 hours without a definition check or 36 hours without package maintenance. New mail is held if definitions have not been verified for 24 hours. Custom domain policy stays versioned; Spam/Not spam corrections are learned during the minute-by-minute scan job.","small"));
  }
  request("status").then(s=>{$("connection").textContent=s.provider_connected?"Provider connected · Sending disabled":"Local Mail Room ready · Security gate active · Provider credentials pending · Sending disabled";if(s.updates?.warnings?.length)$("connection").textContent+=" · Security updates need attention";}).catch(e=>{$("connection").textContent=e.message;});safely(load)();
})();

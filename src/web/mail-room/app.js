"use strict";
(() => {
  const $ = id => document.getElementById(id), api = "./api/", views=["inbox","drafts","activity","daily","filtering","readiness"];
  const DEFAULT_MAILING_ADDRESS="PO Box 333\nInvermay, Saskatchewan S0A 1M0"; // shared by every sending organization
  let sendEnabled=false,prepared=null,selectedKey="",current_actions=null,listItems=[],mode="inbox",offset=0,more=false,draftId=null,metadata={},dirty=false,generation=0,editorSession=0,saving=false,autosave=null,senders=null;
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
  function senderName(sender){const m=(sender||"").match(/^\s*"?([^"<]*?)"?\s*<([^<>]+)>/);return m?(m[1].trim()||m[2]):(sender||"(Unknown sender)");}
  function shortDate(value){const d=new Date(value);if(isNaN(d))return "";const now=new Date();if(d.toDateString()===now.toDateString())return d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});return d.toLocaleDateString([],d.getFullYear()===now.getFullYear()?{month:"short",day:"numeric"}:{year:"numeric",month:"short",day:"numeric"});}
  function showReader(on){document.querySelector(".workspace").classList.toggle("reading",on);if(on)document.querySelector(".reader").scrollTop=0;}
  function section(title,open=false){const d=element("details","","side-section");d.open=open;d.append(element("summary",title));return d;}
  function canLeave(){return !dirty||window.confirm("Leave this unsaved draft? Save it first to keep your changes.");}
  function selected(){
    const address=$("from").value, known=senders?.senders.find(s=>s.address===address);
    if(known)return known;
    const policy=senders?.catch_all_domains?.[address.split("@")[1]], contact=policy&&senders.senders.find(s=>s.address===policy.default_sender);
    return contact?{...contact,address}:undefined;
  }
  function senderChoices(original="",hint=""){
    original=original.trim().toLowerCase();
    const policy=senders.catch_all_domains?.[original.split("@")[1]];
    const choices=policy?[...new Set([original,policy.default_sender])]:senders.senders.map(s=>s.address);
    $("from").replaceChildren();
    for(const address of choices){const o=element("option",address);o.value=address;$("from").append(o);}
    const domainPolicy=senders.catch_all_domains?.[$("domain").value];
    const fallback=policy?original:senders.recipient_to_sender[original]||(domainPolicy?.default_sender)||senders.default_sender;
    $("from").value=choices.includes(hint)?hint:fallback;
  }
  function signature(overwrite=false){
    const item=selected();if(!item)return;
    const original=$("editor").elements.original_recipient.value.trim().toLowerCase(),mapped=senders.recipient_to_sender[original];
    const policy=senders.catch_all_domains?.[original.split("@")[1]];
    $("from").disabled=!!original&&!policy;
    if(mapped&&!policy)$("from").value=mapped;
    const effective=selected()||item;
    $("sender-note").textContent=effective.organization+" · "+(sendEnabled&&effective.live_enabled?(original?"Reply from the selected receiving address or domain contact":"Sending enabled · Prepare for review, then Send"):"Available for drafting; sending is disabled for this identity");
    for(const name of ["signer_name","signer_title","mailing_address"]){const f=$("editor").elements[name];if(overwrite||!f.value)f.value=effective.signature[name]||(name==="mailing_address"?DEFAULT_MAILING_ADDRESS:"");}
  }
  function showEditor(data={},id=null){
    if(!canLeave())return;clearTimeout(autosave);editorSession++;$("editor").reset();draftId=id;metadata={};
    for(const key of ["thread_id","source_message_id","in_reply_to","references"])if(data[key])metadata[key]=data[key];
    for(const field of $("editor").elements)if(field.name)field.value=Array.isArray(data[field.name])?data[field.name].join(", "):data[field.name]||(field.name==="message_class"?"business_correspondence":"");
    if(senders){senderChoices(data.original_recipient||"",data.identity_hint||"");signature();}
    $("editor-title").textContent=id?"Saved draft":data.in_reply_to?"Reply":"New message";
    if(!data.in_reply_to){$("reading").replaceChildren();current_actions=null;} // replies keep the thread above the form
    $("editor").hidden=false;$("prepared").hidden=true;$("send").hidden=true;prepared=null;$("saved").textContent=id?"Saved draft opened.":"New draft — not saved yet.";$("autosave-state").textContent="Drafts autosave on Edge1 after a short pause.";dirty=false;
    $("editor").scrollIntoView({behavior:"smooth",block:"start"});
  }
  function payload(){const d={...metadata};for(const f of $("editor").elements)if(f.name&&f.value.trim())d[f.name]=["to","cc","bcc"].includes(f.name)?f.value.split(",").map(s=>s.trim()).filter(Boolean):f.value;return d;}
  async function save(quiet=false){
    if(saving){if(quiet){autosave=setTimeout(()=>save(true).catch(e=>say(e.message)),1000);return;}throw new Error("A draft save is already in progress.");}
    saving=true;const session=editorSession,snapshot=payload();
    try{const d=await request("drafts",{id:draftId,payload:snapshot});if(session===editorSession){draftId=d.id;dirty=JSON.stringify(payload())!==JSON.stringify(snapshot);$("saved").textContent=dirty?"Saved earlier version · New changes not saved":"Saved on Edge1 · "+new Date(d.updated).toLocaleString();}if(!quiet)say("Draft saved. Nothing sent.");return d;}finally{saving=false;}
  }
  function changed(){dirty=true;$("prepared").hidden=true;$("send").hidden=true;prepared=null;$("saved").textContent="Unsaved changes · Autosave pending";clearTimeout(autosave);autosave=setTimeout(()=>save(true).catch(e=>{say(e.message);$("saved").textContent="Autosave failed · Unsaved text is still here";}),1500);}
  function renderMail(m,container,open=true){
    const a=element("details","","thread-message");a.open=open;const head=element("summary","");head.append(element("strong",senderName(m.sender)),element("span",new Date(m.occurred_at).toLocaleString()));a.append(head);
    const meta=element("div","","mail-meta");meta.append(element("p","From: "+m.sender),element("p","To: "+(m.recipients||[]).join(", ")));
    const email=(m.sender.match(/<([^<>]+)>/)||[null,m.sender])[1];const link=element("a","Find sender in Contacts");link.href="/edge1-ops/contacts/?q="+encodeURIComponent(email);link.target="_blank";link.rel="noopener";meta.append(link);a.append(meta,element("div",m.body_text||"(No plain-text body)","mail-text"));container.append(a);
  }
  function securityBadges(decision){
    const auth=decision.authentication||{},row=element("div","","security-badges"),state=v=>/^pass/i.test(v||"")?" pass":/fail|reject/i.test(v||"")?" fail":"";
    row.append(element("span","Security: "+decision.state,"badge"+(decision.state==="released"?" pass":" fail")));
    for(const k of ["spf","dkim","dmarc"])row.append(element("span",k.toUpperCase()+" "+(auth[k]||"not verified"),"badge"+state(auth[k])));
    return row;
  }
  function securityDetails(decision, container){
    if(decision.operator_report)container.append(element("p",decision.operator_report==="phishing"?"Reported phishing · Awaiting confirmation":decision.operator_report==="confirmed_phishing"?"Confirmed phishing":decision.operator_report.startsWith("reviewed_release:")?"Released after manual review":"Operator classification: "+decision.operator_report.replaceAll("_"," ")));
    container.append(element("p", "State: "+decision.state),element("p", "Sender: "+(decision.authentication?.status||"not_verified").replaceAll("_"," ")),element("p", "SPF: "+(decision.authentication?.spf||"not verified")+" · DKIM: "+(decision.authentication?.dkim||"not verified")+" · DMARC: "+(decision.authentication?.dmarc||"not verified")),element("p", (decision.reasons||[]).join(" · ").replaceAll("_"," ")),element("p", "Domain authentication does not verify the person or guarantee safe content.", "small"));
  }
  function securityActions(m, container, decision){
    const actions=container;
    for(const [label,action] of [["Spam","spam"],["Not spam","not_spam"],["Report phishing","phishing"],...(decision?.state==="quarantine"?[["Confirm phishing","confirmed_phishing"],["Release after review","release"]]:[])]){
      const b=element("button",label);b.type="button";
      if(action==="release"){b.disabled=true;b.dataset.reviewRelease="true";b.title="Review the plain text first";}
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
    }
  }
  async function openMessage(m){
    if(!canLeave())return;const current=++generation;
    const decision=await request("security/"+encodeURIComponent(m.message_id));
    if(current!==generation)return;
    if(decision.state!=="released"){
      clearTimeout(autosave);$("editor").hidden=true;dirty=false;showReader(true);current_actions=null;
      const head=element("div","","reading-head"),bar=element("div","","toolbar");head.append(element("h2",m.subject||"(No subject)"),element("p","From: "+m.sender),bar,securityBadges(decision));$("reading").replaceChildren(head);
      const sec=section("Security details",true);securityDetails(decision,sec);$("reading").append(sec);
      const review=element("button","Review plain text without AVA");review.onclick=safely(async()=>{
        if(!window.confirm("Display potentially malicious correspondence as plain text for manual review? Attachments and AVA remain unavailable."))return;
        const result=await request("review",{message_id:m.message_id,acknowledged:true});
        const body=element("section","","thread-message");renderMail(result.message,body);$("reading").append(body);review.disabled=true;for(const button of bar.querySelectorAll("[data-review-release]")){button.disabled=false;button.title="Release after your review; security checks still apply";}
      });bar.append(review);$("reading").append(element("p","This message is outside the inbox. First review plain text, then choose Release after review if it is legitimate. Malware findings and incomplete checks remain blocked.","notice"));securityActions(m,bar,decision);say("Held mail stays outside AVA and the normal inbox.");return;
    }
    say("Opening thread…");const data=await request("thread/"+encodeURIComponent(m.thread_id));if(current!==generation||!canLeave())return;
    clearTimeout(autosave);$("editor").hidden=true;dirty=false;showReader(true);
    const head=element("div","","reading-head"),bar=element("div","","toolbar"),msgs=data.thread.messages;head.append(element("h2",m.subject||"(No subject)"),bar,securityBadges(decision));$("reading").replaceChildren(head);
    if(msgs.length>1)$("reading").append(element("p",msgs.length+" messages in this thread · earlier messages are collapsed","small"));
    msgs.forEach((item,i)=>renderMail(item,$("reading"),i===msgs.length-1));
    const reply=element("button","Reply","primary"),archive=element("button",m.archived?"Move to inbox":"Archive"),read=element("button","Mark unread"),tag=element("button","Tags");
    reply.title="Draft a reply (r)";archive.title="Archive (e)";
    const replyData=()=>({to:[(m.sender.match(/<([^<>]+)>/)||[null,m.sender])[1]],subject:/^re:/i.test(m.subject)?m.subject:"Re: "+m.subject,original_recipient:m.recipients.length===1?m.recipients[0]:"",thread_id:m.thread_id,source_message_id:m.message_id,in_reply_to:m.message_id});
    reply.onclick=()=>showEditor(replyData());archive.onclick=safely(async()=>{await request("flags",{message_id:m.message_id,archived:!m.archived});await load();say(m.archived?"Moved to inbox.":"Archived in Mail Room. Source mail is retained.");});read.onclick=safely(async()=>{await request("flags",{message_id:m.message_id,is_read:false});await load();say("Marked unread.");});tag.onclick=safely(async()=>{const text=window.prompt("Tags, separated by commas",(m.tags||[]).join(", "));if(text===null)return;await request("flags",{message_id:m.message_id,tags:text.split(",").map(t=>t.trim()).filter(Boolean)});await load();say("Tags saved.");});
    bar.append(reply,archive,read,tag,element("span","","sep"));securityActions(m,bar,decision);current_actions={reply,archive};
    const sec=section("Security details");securityDetails(decision,sec);
    const box=section("AVA assistance");box.append(element("p","Ask AVA’s configured model to review this thread. Suggestions stay editable; nothing is sent or applied automatically."));const summary=element("button","Summarize thread"),suggest=element("button","Suggest reply"),output=element("pre",""),use=element("button","Use suggestion in a draft");use.hidden=true;
    for(const [b,operation] of [[summary,"summary"],[suggest,"reply"]])b.onclick=safely(async()=>{summary.disabled=suggest.disabled=true;use.hidden=true;output.textContent="AVA is reviewing the thread…";try{const d=await request("assist",{operation,thread_id:m.thread_id});output.textContent=d.text+(d.truncated_context?"\n\nOnly the latest bounded excerpts were reviewed.":"");use.hidden=operation!=="reply";use.onclick=()=>showEditor({...replyData(),body:d.text});}finally{summary.disabled=suggest.disabled=false;}});
    const tools=element("div","","actions");tools.append(summary,suggest);box.append(tools,output,use);$("reading").append(box,sec);
    await request("flags",{message_id:m.message_id,is_read:true});
    const attachments=await request("attachments/"+encodeURIComponent(m.message_id));const check=section("Attachments"+(attachments.attachments.length?" ("+attachments.attachments.length+")":""),attachments.attachments.length>0);check.append(element("p",attachments.indexed===false?"Attachment inventory not yet indexed. Downloads blocked.":attachments.attachments.length?"Downloads remain disabled pending attachment acceptance.":"No attachments found in the native archive."));for(const a of attachments.attachments)check.append(element("p",a.filename+" · "+Math.ceil(a.size_bytes/1024)+" KB · "+a.state.replaceAll("_"," ")));$("reading").append(check);say("Thread opened. Email content is displayed as plain text.");
  }
  function select(b){for(const x of listItems)x.classList.toggle("selected",x===b);selectedKey=b.dataset.key;b.scrollIntoView({block:"nearest"});}
  function step(delta){if(!listItems.length)return;const i=listItems.findIndex(b=>b.classList.contains("selected"));const next=listItems[Math.min(listItems.length-1,Math.max(0,i<0?0:i+delta))];if(next&&!next.classList.contains("selected"))next.click();}
  function updateFilterCount(){let n=0;for(const [k,v] of new FormData($("search")))if(k!=="q"&&v&&!(k==="room"&&v==="all")&&!(k==="folder"&&v==="inbox"))n++;$("filter-count").textContent=n?"("+n+" active)":"";}
  function reviewFolder(folder){
    if(!canLeave())return;
    mode="inbox";offset=0;$("search").hidden=false;
    for(const name of views)$(name).classList.toggle("active",name==="inbox");
    $("search").reset();$("search").elements.folder.value=folder;
    updateFilterCount();return load();
  }
  function folderContext(){
    const target=$("folder-context");target.hidden=mode!=="inbox";
    if(target.hidden)return;
    const f=$("search").elements.folder, folder=f.value;
    const descriptions={inbox:"Only cleared messages appear here. Quarantine, Junk, Pending checks and Import holds are outside this inbox.",unread:"Only unread, cleared messages appear here. Held messages are in the review queues above.",archive:"Archived, cleared messages. Held messages are in separate review queues.",all:"All cleared messages, including archived mail. This does not include quarantine, junk, pending checks or import holds.",quarantine:"Outside the inbox. Open a message, review its plain text, then release it if the security checks allow.",junk:"Outside the inbox. Open a legitimate message and choose Not spam.",pending:"Outside the inbox while security checks finish. Incomplete checks cannot be overridden."};
    target.replaceChildren(element("strong",f.options[f.selectedIndex].textContent),element("p",descriptions[folder]||"","small"));
    const domain=$("domain").value;if(domain)target.append(element("p","Filtered to "+domain,"small"));
  }
  function renderReviewQueues(report){
    const target=$("review-queues"),q=report.backlog||{},counts=q.classification_counts||{};
    target.replaceChildren(element("strong","Review queues"));target.title="These messages are outside the inbox. Shortcuts clear your search filters.";
    const bar=element("div","","review-shortcuts");
    for(const [folder,label,count] of [["quarantine","Quarantine",counts.quarantine||0],["junk","Junk",counts.junk||0],["pending","Pending checks",q.pending_or_unchecked||0]]){
      const b=element("button",label+" ("+count+")");b.type="button";b.onclick=safely(()=>reviewFolder(folder));bar.append(b);
    }
    const held=q.held_normalization||0,b=element("button","Import holds ("+held+")");b.type="button";
    b.onclick=()=>{
      if(!canLeave())return;showReader(true);$("editor").hidden=true;
      $("reading").replaceChildren(element("h2","Import holds · "+held),element("p","These archived messages have not entered the Mail Room message list. They are separate from security quarantine and cannot be released with the quarantine button."),element("p","An administrator must inspect the import failure, correct the import metadata or parser, then retry ingestion. Imported mail must still pass security checks before entering the inbox."),element("p","Original messages remain preserved. AVA cannot read them here.","small"));
    };bar.append(b);target.append(bar);
    const updated=element("span","Updated "+new Date(report.generated_at).toLocaleTimeString()+(Date.now()-Date.parse(report.generated_at)>15*60000?" · Stale":""),"queue-updated small");updated.title="Counts checked "+new Date(report.generated_at).toLocaleString();target.append(updated);
  }
  async function refreshReviewQueues(){
    try{renderReviewQueues(await request("readiness"));}
    catch(e){$("review-queues").replaceChildren(element("strong","Outside the inbox"),element("p","Review counts unavailable. Use Folder to open Quarantine, Junk or Pending checks.","small"));}
  }
  async function load(){
    const current=++generation;folderContext();if(mode==="inbox")refreshReviewQueues();$("list").replaceChildren(element("p","Loading…"));const filters=new URLSearchParams(new FormData($("search")));filters.set("offset",offset);
    if(mode==="readiness"){
      const report=await request("readiness");if(current!==generation)return;renderReviewQueues(report);
      $("list").replaceChildren(element("p","Readiness evidence for each domain. Live sending status and commissioning evidence for each domain."));
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
      for(const d of report.domains){const b=element("button",d.domain+(d.commissioned?" · Live on Edge1":" · Commissioning pending"),"message");b.onclick=()=>{
        if(!canLeave())return;clearTimeout(autosave);$("editor").hidden=true;dirty=false;
        $("reading").replaceChildren(element("h2","Domain readiness · "+d.domain),element("p",d.registered_senders+" registered sender identities · "+(d.sending_enabled?"Sending enabled":"Sending disabled")));
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
    listItems=[];for(const m of items){const b=element("button","","message"+(!m.is_read&&mode==="inbox"?" unread":""));const when=m.occurred_at||m.updated;b.title=new Date(when).toLocaleString();b.append(element("div",mode==="inbox"?senderName(m.sender):mode==="drafts"?"Saved draft":({sent:"Sent",sending:"Sending…",send_outcome_unknown:"Send outcome unknown — check before retrying"}[m.state]||"Prepared · not sent"),"who"),element("div",shortDate(when),"when"),element("div",m.subject||"(No subject)","subject"));if(m.tags?.length)b.append(element("div",m.tags.join(" · "),"tags"));b.dataset.key=m.message_id||m.id||m.draft_id||"";b.onclick=safely(()=>{select(b);return mode==="inbox"?openMessage(m):request("draft/"+(m.id||m.draft_id)).then(d=>{showReader(true);showEditor(d.payload,d.id);});});listItems.push(b);$("list").append(b);}
    const keep=listItems.find(b=>b.dataset.key&&b.dataset.key===selectedKey);if(keep)keep.classList.add("selected");
    if(!items.length)$("list").append(element("p",mode==="inbox"?"No matching messages in this folder. Check the review queues above for mail outside the inbox.":mode==="drafts"?"No saved drafts yet.":"No message activity yet."));
    $("previous").disabled=offset===0||mode!=="inbox";$("next").disabled=!more||mode!=="inbox";$("page").textContent=mode==="inbox"?"Page "+(offset/25+1):"Latest 100";
  }
  $("search").onsubmit=safely(()=>{offset=0;updateFilterCount();return load();});$("search").onchange=e=>{if(e.target.tagName==="SELECT")$("search").requestSubmit();};
  $("list").addEventListener("click",e=>{if(e.target.closest(".message"))showReader(true);});
  $("back").onclick=()=>{if(!$("editor").hidden&&!canLeave())return;showReader(false);};
  document.addEventListener("keydown",e=>{
    if(e.ctrlKey||e.metaKey||e.altKey)return;const typing=/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)||e.target.isContentEditable;
    if(e.key==="Escape"){if(typing)e.target.blur();else if(document.querySelector(".workspace.reading"))$("back").click();return;}
    if(typing)return;
    const ready=current_actions&&$("editor").hidden&&current_actions.reply.isConnected;
    if(e.key==="/"){e.preventDefault();$("search").elements.q.focus();}
    else if(e.key==="j"){e.preventDefault();step(1);}
    else if(e.key==="k"){e.preventDefault();step(-1);}
    else if(e.key==="r"&&ready)current_actions.reply.click();
    else if(e.key==="e"&&ready)current_actions.archive.click();
  });
  for(const name of views)$(name).onclick=safely(()=>{mode=name;current_actions=null;offset=0;$("search").hidden=name!=="inbox";for(const n of views)$(n).classList.toggle("active",n===name);return load();});
  $("previous").onclick=safely(()=>{offset=Math.max(0,offset-25);return load();});$("next").onclick=safely(()=>{offset+=25;return load();});
  $("compose").onclick=()=>{showReader(true);showEditor();};$("close").onclick=()=>{if(canLeave()){clearTimeout(autosave);$("editor").hidden=true;dirty=false;editorSession++;}};
  $("editor").addEventListener("invalid",()=>{$("editor").querySelector("details").open=true;},true);$("editor").oninput=changed;
  $("from").onchange=()=>{signature(true);changed();};$("editor").elements.original_recipient.onchange=()=>{senderChoices($("editor").elements.original_recipient.value);signature();changed();};
  $("save").onclick=safely(()=>{clearTimeout(autosave);return save();});
  $("remember-signature").onclick=safely(async()=>{const item=selected();if(!item)throw new Error("Select a sender first.");const signature={};for(const k of ["signer_name","signer_title","mailing_address"])signature[k]=$("editor").elements[k].value.trim();await request("signature",{address:item.address,signature});item.signature=signature;say("Signature remembered for "+item.address);});
  $("editor").onsubmit=safely(async()=>{clearTimeout(autosave);const d=await save();const result=await request("prepare",{id:d.id});if(draftId!==d.id||JSON.stringify(payload())!==JSON.stringify(d.payload)){say("Earlier version prepared. Prepare your new changes for an updated preview.");return;}$("prepared").textContent="Prepared for review — not sent\n\nFrom: "+result.request.from_address+"\nTo: "+result.request.recipients.join(", ")+"\nSubject: "+result.request.subject+"\n\n"+result.body;$("prepared").hidden=false;prepared={id:d.id,request:result.request};const live=result.sender_selection?.live_enabled===true;$("send").hidden=!(sendEnabled&&live);say("Prepared with organization signature and footer. Nothing sent."+(sendEnabled&&!live?" This sender is not enabled for sending.":""));});
  $("send").onclick=safely(async()=>{
    const p=prepared;if(!p||p.id!==draftId||dirty)throw new Error("Prepare the current version before sending.");
    const r=p.request,list=k=>(r[k]||[]).join(", ")||"—";
    if(!window.confirm("Send this message now?\n\nFrom: "+r.from_address+"\nTo: "+list("recipients")+"\nCC: "+list("cc")+"\nBCC: "+list("bcc")+"\nSubject: "+r.subject+"\n\nThis cannot be undone."))return;
    $("send").disabled=true;
    try{const result=await request("send",{id:p.id,confirm:true});prepared=null;$("send").hidden=true;$("editor").hidden=true;dirty=false;editorSession++;
      say("Sent from "+result.from_address+" to "+result.delivery.recipient_count+" recipient(s) at "+new Date(result.delivery.submitted_at).toLocaleTimeString()+".");await load();}
    finally{$("send").disabled=false;}
  });
  window.addEventListener("beforeunload",e=>{if(dirty){e.preventDefault();e.returnValue="";}});
  // Contact suggestions for To/CC/BCC: searches the last comma-separated entry against Contacts (email points only).
  function contactSuggest(field){
    const box=element("div","","suggest");box.hidden=true;box.setAttribute("role","listbox");field.parentNode.append(box);field.setAttribute("autocomplete","off");
    let timer=null,seq=0,active=-1;
    const token=()=>field.value.split(",").pop().trim();
    const close=()=>{box.hidden=true;box.replaceChildren();active=-1;};
    const pick=email=>{const parts=field.value.split(",");parts[parts.length-1]=" "+email;field.value=parts.join(",").replace(/^\s+/,"")+", ";close();field.focus();field.dispatchEvent(new Event("input",{bubbles:true}));};
    const highlight=i=>{const items=[...box.children];active=Math.max(0,Math.min(items.length-1,i));items.forEach((b,n)=>b.classList.toggle("active",n===active));};
    field.addEventListener("input",()=>{clearTimeout(timer);const q=token();if(q.length<2||q.includes("@")&&/\.\w{2,}$/.test(q)){close();return;}
      timer=setTimeout(async()=>{const mine=++seq;try{
        const r=await fetch("/edge1-ops/contacts/api/contacts/search?"+new URLSearchParams({q,kind:"emails",limit:"8"}),{credentials:"same-origin",headers:{Accept:"application/json"}});
        if(!r.ok||mine!==seq)return;const body=await r.json();const rows=Array.isArray(body)?body:body.rows||body.results||body.items||[];
        const seen=new Set(),items=[];for(const row of rows){const email=String(row.display_value||row.normalized_value||"").trim().toLowerCase();if(!email.includes("@")||seen.has(email))continue;seen.add(email);items.push({email,name:row.display_name||row.canonical_name||""});}
        box.replaceChildren();for(const it of items){const b=element("button","","");b.type="button";b.setAttribute("role","option");b.append(element("strong",it.name||it.email),element("span",it.name?it.email:""));b.onmousedown=e=>{e.preventDefault();pick(it.email);};box.append(b);}
        box.hidden=!items.length;active=-1;}catch(_){close();}},200);});
    field.addEventListener("keydown",e=>{if(box.hidden)return;
      if(e.key==="ArrowDown"){e.preventDefault();highlight(active+1);}else if(e.key==="ArrowUp"){e.preventDefault();highlight(active-1);}
      else if(e.key==="Enter"&&active>=0){e.preventDefault();box.children[active].dispatchEvent(new MouseEvent("mousedown"));}else if(e.key==="Escape"){e.stopPropagation();close();}});
    field.addEventListener("blur",()=>setTimeout(close,150));
  }
  for(const name of ["to","cc","bcc"])contactSuggest($("editor").elements[name]);
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
  request("status").then(s=>{sendEnabled=s.send_enabled===true;$("connection").textContent="Mail Room ready · Security gate active · "+(sendEnabled?"Sending enabled for authorized senders":"Sending disabled");if(senders&&!$("editor").hidden)signature();if(s.updates?.warnings?.length)$("connection").textContent+=" · Security updates need attention";}).catch(e=>{$("connection").textContent=e.message;});safely(load)();
  // Deep link from Contacts: ?compose=1&to=address opens a new draft addressed to that contact.
  const linked=new URLSearchParams(location.search);
  if(linked.get("compose")==="1"){const to=(linked.get("to")||"").trim();history.replaceState(null,"",location.pathname);if(!to||(to.length<=320&&/^[^\s@,<>]+@[^\s@,<>]+$/.test(to))){showReader(true);showEditor(to?{to}:{});}}
})();

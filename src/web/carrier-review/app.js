"use strict";

const items = [
  {id:"TKT-DEMO-1001",type:"ticket",carrier:"Example Carrier A",subject:"Investigate intermittent signaling alarm",state:"new",updated:"2026-07-21T00:40:00Z",note:"Sanitized fixture. Confirm source evidence before beginning review."},
  {id:"CHG-DEMO-2001",type:"change_request",carrier:"Example Carrier B",subject:"Request review of proposed route preference",state:"in_review",updated:"2026-07-21T00:55:00Z",note:"Review only. No route change, approval, scheduling, or execution is authorized."},
  {id:"TKT-DEMO-1002",type:"ticket",carrier:"Example Carrier C",subject:"Clarify test-window documentation",state:"information_requested",updated:"2026-07-21T01:05:00Z",note:"Additional non-secret documentation has been requested."},
  {id:"CHG-DEMO-2002",type:"change_request",carrier:"Example Carrier D",subject:"Unsupported production activation request",state:"rejected",updated:"2026-07-21T01:12:00Z",note:"Rejected because review actions cannot authorize production activation."}
].map((item)=>({...item,approval_granted:false,execution_authorized:false}));

const stateFilter=document.querySelector("#state-filter");
const typeFilter=document.querySelector("#type-filter");
const queryFilter=document.querySelector("#query-filter");
const queueList=document.querySelector("#queue-list");
const visibleCount=document.querySelector("#visible-count");
let selectedId=null;

function label(value){return value.replaceAll("_"," ").replace(/\b\w/g,(c)=>c.toUpperCase());}
function filtered(){const q=queryFilter.value.trim().toLowerCase();return items.filter((item)=>(stateFilter.value==="all"||item.state===stateFilter.value)&&(typeFilter.value==="all"||item.type===typeFilter.value)&&(!q||[item.id,item.carrier,item.subject].some((value)=>value.toLowerCase().includes(q))));}
function updateSummary(){document.querySelector("#count-total").textContent=items.length;document.querySelector("#count-new").textContent=items.filter((i)=>i.state==="new").length;document.querySelector("#count-review").textContent=items.filter((i)=>i.state==="in_review").length;document.querySelector("#count-info").textContent=items.filter((i)=>i.state==="information_requested").length;}
function selectItem(id){selectedId=id;const item=items.find((entry)=>entry.id===id);document.querySelector("#detail-title").textContent=item.subject;document.querySelector("#detail-metadata").innerHTML=[["Record ID",item.id],["Type",label(item.type)],["Carrier",item.carrier],["Review state",label(item.state)],["Updated",new Date(item.updated).toLocaleString()]].map(([term,value])=>`<div><dt>${term}</dt><dd>${value}</dd></div>`).join("");document.querySelector("#detail-note").textContent=item.note;document.querySelector("#execution-authorized").textContent=String(item.execution_authorized);document.querySelector("#approval-granted").textContent=String(item.approval_granted);render();}
function render(){const visible=filtered();visibleCount.textContent=`${visible.length} of ${items.length}`;queueList.replaceChildren();if(!visible.length){queueList.textContent="No review items match these filters.";return;}visible.forEach((item)=>{const button=document.createElement("button");button.type="button";button.className="queue-item";button.setAttribute("aria-pressed",String(item.id===selectedId));button.innerHTML=`<h3>${item.subject}</h3><div class="queue-meta"><span class="badge">${label(item.state)}</span><span>${item.id}</span><span>${item.carrier}</span></div>`;button.addEventListener("click",()=>selectItem(item.id));queueList.append(button);});}
[stateFilter,typeFilter,queryFilter].forEach((control)=>control.addEventListener("input",render));
document.querySelector("#reset-filters").addEventListener("click",()=>{stateFilter.value="all";typeFilter.value="all";queryFilter.value="";render();});
updateSummary();render();

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('src/web/mail-room/app.js','utf8');
const fn=source.slice(source.indexOf('  function securityActions('),source.indexOf('  async function openMessage('));
async function fixture(decision){
 const calls=[],buttons=[],messages=[];let reviews=0;
 const container={dataset:{},append:b=>buttons.push(b)};
 const sandbox={reasonCache:new Map(),element:(tag,label)=>({textContent:label,dataset:{}}),safely:fn=>fn,window:{confirm:()=>true},request:async(path,data)=>{calls.push({path,data});return {state:'released',related_flagged:0}},$:()=>({replaceChildren(){}}),load:async()=>{},say:m=>messages.push(m)};
 vm.createContext(sandbox);vm.runInContext(fn,sandbox);
 sandbox.securityActions({message_id:'<test@example.test>'},container,decision,async()=>{reviews++;container.dataset.plainTextReviewed='true'});
 return {calls,buttons,messages,get reviews(){return reviews}};
}
(async()=>{
 const eligible=await fixture({state:'quarantine',scan_complete:true,hard_block:false});
 const notSpam=eligible.buttons.find(b=>b.textContent==='Not spam');
 assert.equal(notSpam.disabled,false);await notSpam.onclick();assert.equal(eligible.reviews,1);assert.equal(eligible.calls.length,0);assert.match(notSpam.textContent,/Move to inbox/);
 await notSpam.onclick();assert.equal(eligible.calls.length,1);assert.equal(eligible.calls[0].data.action,'release');assert.equal(eligible.calls[0].data.reviewed,true);
 for(const decision of [{state:'quarantine',scan_complete:true,hard_block:true},{state:'pending',scan_complete:false,hard_block:false},{state:'quarantine',scan_complete:true,hard_block:false,operator_report:'confirmed_phishing'}]){
  const held=await fixture(decision);assert.equal(held.buttons.find(b=>b.textContent==='Not spam').disabled,true);
 }
 const junk=await fixture({state:'junk',scan_complete:true,hard_block:false});await junk.buttons.find(b=>b.textContent==='Not spam').onclick();assert.equal(junk.calls[0].data.action,'not_spam');assert.equal(junk.calls[0].data.reviewed,false);
 console.log('Not spam UI flow passed: quarantine review then release, junk correction, and blocked-state guards.');
})().catch(error=>{console.error(error);process.exitCode=1});

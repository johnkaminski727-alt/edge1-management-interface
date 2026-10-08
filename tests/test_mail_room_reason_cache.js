const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/web/mail-room/app.js','utf8');
let now=0,calls=0;
const sandbox={Date:{now:()=>now},request:async()=>{calls++;return {state:'junk'}}};
vm.createContext(sandbox);vm.runInContext(source.slice(source.indexOf('  const reasonCache='),source.indexOf('  function say(')),sandbox);
(async()=>{
 await sandbox.listSecurityDecision('one');await sandbox.listSecurityDecision('one');assert.equal(calls,1);
 now=60001;await sandbox.listSecurityDecision('one');assert.equal(calls,2);
 vm.runInContext('reasonCache.clear()',sandbox);await sandbox.listSecurityDecision('one');assert.equal(calls,3);
 assert.match(source,/const decision=await request\("security\/"\+encodeURIComponent\(m.message_id\)\)/);
 console.log('Reason cache: repeated rows reuse checks; expiry and invalidation refresh; opening checks live state.');
})().catch(e=>{console.error(e);process.exitCode=1});

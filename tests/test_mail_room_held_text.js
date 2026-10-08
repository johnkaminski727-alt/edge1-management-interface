const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/web/mail-room/app.js','utf8');
const sandbox={};vm.createContext(sandbox);vm.runInContext(source.slice(source.indexOf('  function heldReviewText('),source.indexOf('  async function openMessage(')),sandbox);
const text=sandbox.heldReviewText('Hello John. Visit https://evil.example/track?a=1 or www.example.test. Phone 555-1234.');
assert.match(text,/Hello John/);assert.match(text,/555-1234/);assert.doesNotMatch(text,/https?:\/\/|www\./);assert.match(text,/\[Web link removed\]/);
assert.match(source,/await review.onclick\(\);return;/);
assert.match(source,/element\("div",heldReviewText\(result.message.body_text\),"mail-text"\)/);
assert.match(source,/if\(current!==generation\)return;/);
console.log('Held review text strips URLs, keeps message text, auto-loads and renders as inert text.');

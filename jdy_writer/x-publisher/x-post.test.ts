import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CN_ACCOUNT, readPostText, assertCanSubmit, planPostPage, verificationUrl, sha256, buildManifest, bindReceipt, writeReceipt, loadReceipt, canonicalPostUrl, assertPublished, backfillVerified, withReceiptLock, type PostReceipt, type PublishedSnapshot } from './x-post-state.ts';
import { runPostFlow, type PostDriver } from './x-post-flow.ts';
import { postToX } from './x-browser.ts';
import { getDefaultProfileDir } from './x-utils.ts';

const url=`https://x.com/${CN_ACCOUNT}/status/123456`;
const text='要是晚睡二十分钟\n\n完整正文，含社区测算限定。';
function fixture(t: any, imageCount=4) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'x-post-test-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const sources=['x-note.md','source.md'].map(name=>{const f=path.join(dir,name);fs.writeFileSync(f,'# 原稿\n\n![](https://img.jdy.systems/manual/a.webp)\n\n## 关联\n\n- [[来源]]\n');return f;});
  const images=Array.from({length:imageCount},(_,i)=>{const f=path.join(dir,`${i}.png`);fs.writeFileSync(f,`image-${i}`);return f;});
  const manifest=buildManifest(text,images,path.join(dir,'profile'),sources);
  const receipt:PostReceipt={version:1,manifest,stage:'waiting_login'};
  const snapshot:PublishedSnapshot={url,author:CN_ACCOUNT,text,photos:images.map((_,i)=>`/${CN_ACCOUNT}/status/123456/photo/${i+1}`),loaded:true};
  return {dir,sources,images,receipt,snapshot,state:path.join(dir,'receipt.json')};
}
function driver(snapshot:PublishedSnapshot) {
  const calls={compose:0,submit:0,verify:0};
  const d:PostDriver={async compose(_resume,before){calls.compose++;before();},async submit(before){before();calls.submit++;return url;},async verify(){calls.verify++;return snapshot;}};
  return {d,calls};
}
test('full workflow persists uncertain submission before click, verifies before backfill',async t=>{
 const f=fixture(t),{d,calls}=driver(f.snapshot);const stages:string[]=[];
 d.submit=async before=>{before();calls.submit++;assert.equal(loadReceipt(f.state).stage,'submitting');return url;};
 const save=()=>{stages.push(f.receipt.stage);writeReceipt(f.state,f.receipt);};
 await runPostFlow(f.receipt,d,save,{submit:true});
 assert.deepEqual(stages,['composing','ready','submitting','submitted','verified']);
 backfillVerified(f.receipt);backfillVerified(f.receipt);
 assert.equal(fs.readFileSync(f.sources[0],'utf8').split(url).length-1,1);
 assert.match(fs.readFileSync(f.sources[1],'utf8'),/> X 长帖：https:/);
 assert.equal(calls.submit,1);assert.equal(fs.statSync(f.state).mode&0o777,0o600);
});
test('lost submission response never causes a second click, even on repeated runs',async t=>{
 const f=fixture(t),{d,calls}=driver(f.snapshot);const save=()=>writeReceipt(f.state,f.receipt);
 d.submit=async before=>{before();calls.submit++;throw Error('response lost');};
 await assert.rejects(runPostFlow(f.receipt,d,save,{submit:true}),/response lost/);
 assert.equal(f.receipt.stage,'submitting');
 for(let i=0;i<2;i++)await assert.rejects(runPostFlow(f.receipt,d,save,{submit:true}),/Never submit again/);
 assert.equal(calls.submit,1);
 await runPostFlow(f.receipt,d,save,{submit:false,verifyOnly:true,publishedUrl:url});
 assert.equal(f.receipt.stage,'verified');assert.equal(calls.submit,1);
});
test('login interruption preserves receipt and does not fill or publish',async t=>{
 const f=fixture(t),{d,calls}=driver(f.snapshot);
 d.compose=async()=>{throw Error('Login required');};
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:true}),/Login required/);
 assert.equal(f.receipt.stage,'waiting_login');assert.equal(calls.submit,0);
});
test('account mismatch, missing images or incomplete text stop before submission',async t=>{
 for(const reason of ['wrong account','missing image','partial text']){
 const f=fixture(t),{d,calls}=driver(f.snapshot);d.compose=async(_r,before)=>{before();throw Error(reason);};
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:true}),new RegExp(reason));assert.equal(calls.submit,0);
 }
});
test('published text or media mismatch retains submitted and blocks backfill',async t=>{
 const f=fixture(t),{d,calls}=driver({...f.snapshot,photos:f.snapshot.photos.slice(0,3)});
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:true}),/media/);
 assert.equal(f.receipt.stage,'submitted');assert.throws(()=>backfillVerified(f.receipt),/verified/);
 d.verify=async()=>({...f.snapshot,text:'截断正文'});
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:true}),/text mismatch/);assert.equal(calls.submit,1);
});
test('manual publication recovery verifies without composing or submitting',async t=>{
 const f=fixture(t),{d,calls}=driver(f.snapshot);f.receipt.stage='ready';
 await runPostFlow(f.receipt,d,()=>{}, {submit:false,verifyOnly:true,publishedUrl:url});
 assert.equal(calls.compose,0);assert.equal(calls.submit,0);assert.equal(f.receipt.stage,'verified');
});
test('mismatched recovery URL cannot poison receipt binding',async t=>{
 const f=fixture(t),{d}=driver({...f.snapshot,text:'another post'});
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:false,verifyOnly:true,publishedUrl:url}),/text mismatch/);
 assert.equal(f.receipt.url,undefined);
});
test('canonical URL rejects foreign account, host and non-status URLs',()=>{
 assert.equal(canonicalPostUrl(url+'?s=20'),url);
 for(const value of ['https://evil.example/_ThrowException/status/1','https://x.com/other/status/1','https://x.com/_ThrowException/status/1/photo/1','http://x.com/_ThrowException/status/1'])assert.throws(()=>canonicalPostUrl(value));
});
test('media count, loaded state and order are all required',t=>{
 const f=fixture(t);f.receipt.url=url;
 assertPublished(f.receipt,f.snapshot);
 for(const changed of [{photos:[...f.snapshot.photos].reverse()},{photos:f.snapshot.photos.slice(1)},{loaded:false},{author:'other'},{photos:f.snapshot.photos.map(p=>'https://foreign.example'+p)}])assert.throws(()=>assertPublished(f.receipt,{...f.snapshot,...changed}));
});
test('changed source blocks all backfill edits; retry after partial backfill is idempotent',t=>{
 const f=fixture(t);f.receipt.url=url;f.receipt.stage='verified';
 const original=fs.readFileSync(f.sources[1],'utf8');fs.appendFileSync(f.sources[1],'用户新增内容');
 assert.throws(()=>backfillVerified(f.receipt),/source changed/);assert.ok(!fs.readFileSync(f.sources[0],'utf8').includes(url));
 fs.writeFileSync(f.sources[1],original);
 fs.appendFileSync(f.sources[0],`\n> 发布链接：${url}\n`);
 backfillVerified(f.receipt);assert.equal(fs.readFileSync(f.sources[0],'utf8').split(url).length-1,1);
});
test('receipt binding catches changed text, image bytes and sources',t=>{
 const f=fixture(t);writeReceipt(f.state,f.receipt);
 assert.equal(bindReceipt(f.state,f.receipt.manifest).stage,'waiting_login');
 for(const altered of [{...f.receipt.manifest,textSha256:sha256('different')},{...f.receipt.manifest,images:[]}])assert.throws(()=>bindReceipt(f.state,altered),/differs/);
 fs.writeFileSync(f.images[0],'changed');
 assert.throws(()=>bindReceipt(f.state,buildManifest(text,f.images,f.receipt.manifest.profile,f.sources)),/differs/);
 assert.throws(()=>buildManifest(text,[...f.images,f.images[0]],'profile',[]),/at most four/);
 assert.throws(()=>buildManifest(text,['/no-such-test-image'],'profile',[]));
});
test('receipt lock excludes simultaneous runs and releases after failure',async t=>{
 const f=fixture(t);
 await withReceiptLock(f.state,async()=>{await assert.rejects(async()=>withReceiptLock(f.state,async()=>{}),/EEXIST/);});
 await assert.rejects(withReceiptLock(f.state,async()=>{throw Error('failed');}),/failed/);
 assert.ok(!fs.existsSync(f.state+'.lock'));
});
test('default profile ignores shared profile environment overrides',()=>{
 const before=process.env.BAOYU_CHROME_PROFILE_DIR, old=process.env.X_BROWSER_PROFILE_DIR;
 try{process.env.BAOYU_CHROME_PROFILE_DIR='/wrong-shared';process.env.X_BROWSER_PROFILE_DIR='/wrong-env';assert.ok(getDefaultProfileDir().endsWith('/.local/share/x-browser-profile-cn'));}
 finally{if(before===undefined)delete process.env.BAOYU_CHROME_PROFILE_DIR;else process.env.BAOYU_CHROME_PROFILE_DIR=before;if(old===undefined)delete process.env.X_BROWSER_PROFILE_DIR;else process.env.X_BROWSER_PROFILE_DIR=old;}
});
test('CLI API rejects unsafe invocation before opening a browser',async()=>{
 await assert.rejects(postToX({text:'approved',submit:true}),/explicit --state-file/);
 await assert.rejects(postToX({verifyOnly:true}),/requires --state-file/);
 await assert.rejects(postToX({text:'new',verifyOnly:true,stateFile:'/unused'}),/not new publication inputs/);
});

test('last pre-click validation failure leaves a retryable prepared receipt',async t=>{
 const f=fixture(t),{d,calls}=driver(f.snapshot);f.receipt.stage='ready';
 d.submit=async()=>{throw Error('preview changed before click');};
 await assert.rejects(runPostFlow(f.receipt,d,()=>{}, {submit:true}),/preview changed/);
 assert.equal(f.receipt.stage,'ready');assert.equal(calls.submit,0);
});

test('uncertain publication can open a read-only recovery page after original tab or browser closes',t=>{
 const f=fixture(t);f.receipt.stage='submitting';f.receipt.targetId='closed-target';
 assert.equal(verificationUrl(f.receipt,true,url),url);
 assert.equal(f.receipt.url,undefined); // Candidate must not be bound until the actual post matches.
 assert.deepEqual(planPostPage(f.receipt,[],url),{targetId:undefined,url});
 assert.throws(()=>planPostPage(f.receipt,[]),/Original composer/);
 assert.throws(()=>verificationUrl(f.receipt,true),/actual post/);
});
test('read-only verification preserves a new draft in the old task tab',t=>{
 const f=fixture(t);f.receipt.targetId='old-task';f.receipt.url=url;
 const targets=[{targetId:'old-task',url:'https://x.com/compose/post'}];
 assert.equal(planPostPage(f.receipt,targets,url).targetId,undefined);
 assert.equal(planPostPage(f.receipt,[{targetId:'old-task',url}],url).targetId,undefined); // Preserve unsent replies too.
});
test('only a ready unpublished receipt may submit; partial composition cannot bypass preview review',t=>{
 const f=fixture(t);
 for(const stage of ['waiting_login','composing','submitting','submitted'] as const){f.receipt.stage=stage;assert.throws(()=>assertCanSubmit(f.receipt),/Only a ready/);}
 f.receipt.stage='ready';assert.doesNotThrow(()=>assertCanSubmit(f.receipt));
 f.receipt.stage='submitted';f.receipt.url=url;assert.doesNotThrow(()=>assertCanSubmit(f.receipt));
});
test('manual backfill reconciliation closes without changing new author edits or duplicating URLs',t=>{
 const f=fixture(t);f.receipt.url=url;f.receipt.stage='verified';
 const edited=fs.readFileSync(f.sources[0],'utf8')+`\n作者新增段落。\n\n> 发布链接：${url}\n\n保留末尾补充。\n`;
 fs.writeFileSync(f.sources[0],edited);
 backfillVerified(f.receipt);backfillVerified(f.receipt);
 assert.equal(fs.readFileSync(f.sources[0],'utf8'),edited);
 fs.appendFileSync(f.sources[0],`> 发布链接：${url}\n`);
 assert.throws(()=>backfillVerified(f.receipt),/Duplicate publication links/);
});

test('rendered URLs are recovered only from matching approved link metadata',t=>{
 const f=fixture(t,0),url='https://example.com/full/source';
 const m=buildManifest('来源 ('+url+')',[],f.receipt.manifest.profile,[]);assert.deepEqual(m.links,[url]);
 const anchor={innerText:'example.com/full/…',getAttribute:(key:string)=>key==='title'?url:key==='href'?'https://t.co/short':null};
 const node={innerText:'来源 (example.com/full/…)',querySelectorAll:()=>[anchor]};
 assert.equal(readPostText(node,m.links),'来源 ('+url+')');
 assert.equal(readPostText({...node,querySelectorAll:()=>[{...anchor,getAttribute:()=>null}]},m.links),node.innerText);
});
test('ambiguous repeated link displays and unrelated metadata never fabricate approved text',()=>{
 const display='example.com/…';const anchor={innerText:display,getAttribute:(key:string)=>key==='title'?'https://example.com/other':null};
 const node={innerText:display+' '+display,querySelectorAll:()=>[anchor]};
 assert.equal(readPostText(node,['https://example.com/other']),node.innerText);
 assert.equal(readPostText({...node,innerText:display},['https://example.com/expected']),display);
 const mention={innerText:'@example.com',getAttribute:()=> 'https://example.com/other'};
 assert.equal(readPostText({innerText:'@example.com',querySelectorAll:()=>[mention]},['https://example.com/other']),'@example.com');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { launchChrome, getFreePort, gracefulKillChrome } from './vendor/baoyu-chrome-cdp/src/index.ts';
import { CdpConnection, findChromeExecutable, STABLE_CHROME, waitForChromeDebugPort } from './x-utils.ts';
import { makeDriver } from './x-browser.ts';
import { assertComposerReady, buildManifest, type PostReceipt } from './x-post-state.ts';

const executable=findChromeExecutable(STABLE_CHROME);
test('real CDP adapter composes four ordered file-input images and clicks once on an isolated local fixture', {skip:!executable,timeout:30000},async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'x-browser-fixture-'));
 const html=`<!doctype html><body><a data-testid="AppTabBar_Profile_Link" href="/_ThrowException">Profile</a>
 <div role="dialog"><div data-testid="tweetTextarea_0" contenteditable="plaintext-only" style="white-space:pre-wrap"></div>
 <div data-testid="attachments"></div><input type="file" data-testid="fileInput" multiple>
 <button data-testid="tweetButton" disabled>Post</button></div><script>
 window.clicks=0;
 const editor=document.querySelector('[contenteditable]');
 // Like X's controlled editor, preserve the input event text instead of browser-generated div breaks.
 editor.onbeforeinput=e=>{e.preventDefault();editor.textContent+=e.data??'\\n';};
 document.querySelector('input').onchange=async e=>{
 const box=document.querySelector('[data-testid="attachments"]');
 for(const file of e.target.files){const image=new Image();image.src=URL.createObjectURL(file);box.append(image);await image.decode();}
 document.querySelector('button').disabled=false;
 };
 document.querySelector('button').onclick=()=>{window.clicks++;const toast=document.createElement('div');toast.dataset.testid='toast';toast.innerHTML='<a href="https://x.com/_ThrowException/status/123456">View</a>';document.body.append(toast);document.querySelector('[role="dialog"]').remove();};
 </script>`;
 const server=Bun.serve({hostname:'127.0.0.1',port:0,fetch:()=>new Response(html,{headers:{'content-type':'text/html'}})});
 const port=await getFreePort();
 const chrome=await launchChrome({chromePath:executable!,profileDir:path.join(dir,'profile'),port,url:`http://127.0.0.1:${server.port}`,headless:true,extraArgs:['--disable-background-networking']});
 let cdp:CdpConnection|undefined;
 t.after(async()=>{cdp?.close();await gracefulKillChrome(chrome,port);server.stop(true);fs.rmSync(dir,{recursive:true,force:true});});
 cdp=await CdpConnection.connect(await waitForChromeDebugPort(port,10000),10000);
 const {targetInfos}=await cdp.send<any>('Target.getTargets');const target=targetInfos.find((v:any)=>v.url.includes('127.0.0.1'));
 const {sessionId}=await cdp.send<any>('Target.attachToTarget',{targetId:target.targetId,flatten:true});
 await cdp.send('DOM.enable',{}, {sessionId});
 const result=await cdp.send<any>('Runtime.evaluate',{expression:`['red','green','blue','white'].map(color=>{const c=document.createElement('canvas');c.width=c.height=20;const x=c.getContext('2d');x.fillStyle=color;x.fillRect(0,0,20,20);return c.toDataURL().split(',')[1]})`,returnByValue:true},{sessionId});
 const images=result.result.value.map((b64:string,i:number)=>{const file=path.join(dir,`${i}.png`);fs.writeFileSync(file,Buffer.from(b64,'base64'));return file;});
 const text='中文长帖\n\n完整正文，不截断。\n收益数字为发帖者测算。';
 const receipt:PostReceipt={version:1,manifest:buildManifest(text,images,path.join(dir,'profile'),[]),stage:'waiting_login'};
 const driver=makeDriver(cdp,sessionId,receipt,text,3000,path.join(dir,'receipt.json'),()=>{});
 await driver.compose(false,()=>{});
 assert.equal(receipt.previewHashes?.length,4);assert.equal(new Set(receipt.previewHashes).size,4);
 // The same ready composer can be verified again without appending text or images.
 await driver.compose(true,()=>{throw Error('resume must not mutate');});
 assert.equal(await driver.submit(()=>{}),'https://x.com/_ThrowException/status/123456');
 const count=await cdp.send<any>('Runtime.evaluate',{expression:'window.clicks',returnByValue:true},{sessionId});assert.equal(count.result.value,1);
});
test('composer guards reject wrong account, truncation, missing/unloaded media and disabled long-post button',()=>{
 const receipt:PostReceipt={version:1,stage:'ready',manifest:{account:'_ThrowException',profile:'/test',textSha256:'test',images:Array.from({length:4},()=>({file:'image',sha256:'hash'})),sources:[]}};
 const ready={account:'/_ThrowException',editor:true,text:'完整中文',count:4,loaded:true,enabled:true};
 assertComposerReady(receipt,ready,ready.text);
 for(const change of [{account:'/other'},{text:'截断'},{count:3},{loaded:false},{enabled:false},{editor:false}])assert.throws(()=>assertComposerReady(receipt,{...ready,...change},ready.text));
});

import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { findChromeExecutable, STABLE_CHROME, waitForChromeDebugPort, CdpConnection } from './x-utils.ts';

const executable=findChromeExecutable(STABLE_CHROME);
test('Chrome survives launcher exit and cleanup of the launcher process group',
 {skip:!executable||process.platform==='win32',timeout:45000},async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'x-browser-lifecycle-'));
 const state=path.join(dir,'launch.json'),worker=path.join(dir,'launch.ts');
 const utils=new URL('./x-utils.ts',import.meta.url).pathname;
 let chromePid:number|undefined,port:number|undefined;
 t.after(async()=>{
   if(chromePid){
     try{process.kill(chromePid,'SIGTERM');}catch{}
     const deadline=Date.now()+5000;
     while(Date.now()<deadline){try{process.kill(chromePid,0);}catch{break;}await new Promise(r=>setTimeout(r,100));}
     try{process.kill(chromePid,'SIGKILL');}catch{}
   }
   fs.rmSync(dir,{recursive:true,force:true});
 });
 fs.writeFileSync(worker,`import fs from 'node:fs';
 import {launchChrome,STABLE_CHROME} from ${JSON.stringify(utils)};
 const {chrome,port}=await launchChrome('about:blank',${JSON.stringify(path.join(dir,'profile'))},STABLE_CHROME);
 fs.writeFileSync(${JSON.stringify(state)},JSON.stringify({pid:chrome.pid,port}));
 chrome.unref();
 `);
 const launcher=spawn(process.execPath,[worker],{stdio:['ignore','ignore','pipe'],detached:true});
 let diagnostic='';launcher.stderr?.on('data',b=>{diagnostic=(diagnostic+b).slice(-2000);});
 const exit=await new Promise<number|null>((resolve,reject)=>{
   launcher.once('error',reject);launcher.once('exit',resolve);
 });
 assert.equal(exit,0,diagnostic);
 ({pid:chromePid,port}=JSON.parse(fs.readFileSync(state,'utf8')));
 assert.ok(chromePid&&port&&launcher.pid);
 // Simulate the agent/terminal cleaning up the finished command's process group.
 try{process.kill(-launcher.pid!,'SIGTERM');}catch(e){assert.equal((e as NodeJS.ErrnoException).code,'ESRCH');}
 await new Promise(r=>setTimeout(r,500));
 process.kill(chromePid!,0);
 const cdp=await CdpConnection.connect(await waitForChromeDebugPort(port!,3000),3000);
 try{
   const version=await cdp.send<{product:string}>('Browser.getVersion');
   assert.match(version.product,/^Chrome\//);
 }finally{cdp.close();}
});

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { sha, savePrivate, outsideNotes, addVerifiedLink, publicBytes, args } from './files.ts';
import { withReceiptLock } from '../x-publisher/x-post-state.ts';
import type { MediaLedger } from './media-ledger.ts';
const norm=(s:string)=>s.replace(/\u00a0/g,' ').replace(/\s+/g,' ').trim();
export function wechatUrl(value:string) {
 const u=new URL(value);
 if(u.protocol!=='https:'||u.hostname!=='mp.weixin.qq.com'||u.username||u.password||u.port||!/^\/s(?:\/[^/]+)?$/.test(u.pathname))throw Error('Expected an official WeChat article URL.');
 u.hash='';return u.href;
}
export async function loadAdapter(directory=path.resolve(import.meta.dir,'../../jdy-url-to-markdown')) {
 const adapter=path.join(directory,'scripts/adapters/wechat.ts');
 if(!fs.existsSync(adapter))throw Error('jdy-url-to-markdown adapter unavailable; supply --url-skill. No generic text-only fallback.');
 const loaded=await import(adapter);
 const require=createRequire(adapter);const dom=await import(require.resolve('linkedom'));
 return {...loaded,parseHTML:dom.parseHTML};
}
interface Snapshot {canonicalUrl?:string;title:string;text:string;images:string[];links:string[];media:{kind:string;author:string;title:string;before:string}[];markdown:string}
export function snapshot(html:string,url:string,adapter:any):Snapshot {
 const {document}=adapter.parseHTML(adapter.prepareWechatHtml(html));const body=document.querySelector('#js_content, .rich_media_content');
 if(!body)throw Error('Official article body unavailable (possibly login/captcha); no verification or backfill.');
 const selector='mp-common-videosnap,video,mpvideo,iframe,[data-mpvid]';
 const media:Snapshot['media']=[];let before='';
 function walk(node:any):string {
  if(node.nodeType===3){before+=node.textContent;return node.textContent;}
  if(node.nodeType!==1)return '';
  if(node.matches(selector)) {
   const read=(...keys:string[])=>keys.map(k=>node.getAttribute(k)).find(Boolean)||'';
   media.push({kind:node.localName==='mp-common-videosnap'?'channels':'local',author:read('data-nickname','data-author'),title:read('data-desc','data-title','title'),before:norm(before)});return '';
  }
  if(/^(script|style|noscript|template)$/.test(node.localName))return '';
  const block=/^(p|div|section|article|h[1-6]|li|br)$/.test(node.localName);let value='';
  if(block){value+=' ';before+=' ';}
  for(const child of [...node.childNodes])value+=walk(child);
  if(block){value+=' ';before+=' ';}return value;
 }
 const text=norm(walk(body));
 for(const node of [...body.querySelectorAll(selector)] as any[])node.remove();
 const images=[...body.querySelectorAll('img')].map((img:any)=>{
  const raw=img.getAttribute('src');if(!raw)throw Error('Unresolved article image.');const u=new URL(raw,url);
  if(u.hostname==='mmbiz.qpic.cn'&&/^\/(?:sz_)?mmbiz_(jpg|png|gif|webp)\/[A-Za-z0-9]+\/(0|640)$/.test(u.pathname))return u.origin+u.pathname.replace(/\/640$/,'/0');
  return u.href;
 });
 const links=[...body.querySelectorAll('a[href]')].map((a:any)=>a.getAttribute('href'));
 const parsed=adapter.parseWechatHtml(document.documentElement.outerHTML,url);
 if(!parsed.metadata.title||parsed.metadata.title==='Untitled'||!text)throw Error('Untrustworthy article title or empty body.');
 const canonicalUrl=document.querySelector('link[rel="canonical"]')?.getAttribute('href')||document.querySelector('meta[property="og:url"]')?.getAttribute('content')||undefined;
 return {canonicalUrl,title:norm(parsed.metadata.title),text,images,links,media,markdown:parsed.markdown};
}
export function compare(expected:Snapshot,actual:Snapshot,ledger?:MediaLedger) {
 const items=ledger?Object.values(ledger.items):[];
 const mediaMatch=ledger?actual.media.length===items.length&&items.every((item,i)=>{
  const seen=actual.media[i];return seen&&seen.kind===item.kind&&norm(seen.title)===norm(item.title)&&(!item.author||norm(seen.author)===norm(item.author))&&seen.before.endsWith(norm(item.after));
 }):JSON.stringify(actual.media)===JSON.stringify(expected.media);
 const checks={title:actual.title===expected.title,text:actual.text===expected.text,images:JSON.stringify(actual.images)===JSON.stringify(expected.images),links:JSON.stringify(actual.links)===JSON.stringify(expected.links),media:mediaMatch};
 return {passed:Object.values(checks).every(Boolean),checks};
}
export function draftBaseline(file:string) {
 const draft=JSON.parse(fs.readFileSync(file,'utf8'));let article=draft.pending?.article||draft.article;
 if(!article?.content&&draft.publication?.backup) {
  const backup=draft.publication.backup;
  if(typeof backup!=='string'||path.basename(backup)!==backup||!backup.startsWith(path.basename(file)+'.before-published-')||!backup.endsWith('.json'))throw Error('Unsafe or unrelated publication backup.');
  const backupFile=path.join(path.dirname(path.resolve(file)),backup);
  if(fs.lstatSync(backupFile).isSymbolicLink())throw Error('Publication backup must not be a symlink.');
  const old=JSON.parse(fs.readFileSync(backupFile,'utf8'));article=old.pending?.article||old.article;
  if(old.mediaId!==draft.mediaId||old.identity!==draft.identity||article?.title!==draft.publication.title)throw Error('Publication backup identity differs from confirmed draft.');
 }
 if(!draft.mediaId||!article?.content||!article.title)throw Error('Expected a known draft ID and rendered article snapshot (or its identity-bound publication backup).');
 return {draft,article};
}
export async function verifyPublication(options:{source:string;draftReceipt:string;stateFile:string;url:string;urlSkill?:string;htmlFile?:string;ledgerFile?:string;acceptReport?:string;reviewNote?:string},fetchHtml=(u:string)=>publicBytes(u,['mp.weixin.qq.com'],8*1024*1024).then(b=>b.toString('utf8'))) {
 const url=wechatUrl(options.url),source=path.resolve(options.source),stateFile=path.resolve(options.stateFile);
 outsideNotes(stateFile,source);
 return withReceiptLock(stateFile,async()=>{
  const {draft,article}=draftBaseline(options.draftReceipt);
  const ledger:MediaLedger|undefined=options.ledgerFile?JSON.parse(fs.readFileSync(options.ledgerFile,'utf8')):undefined;
  if(ledger&&(ledger.version!==1||ledger.kind!=='wechat-media'||ledger.draftId!==draft.mediaId||ledger.title!==article.title))throw Error('Media ledger belongs to another draft.');
  const binding={source,url,draftId:draft.mediaId,baseline:sha(JSON.stringify(article))};
  const prior=fs.existsSync(stateFile)?JSON.parse(fs.readFileSync(stateFile,'utf8')):undefined;
  if(prior&&JSON.stringify(prior.binding)!==JSON.stringify(binding))throw Error('Publication receipt binding differs; preserve it and inspect.');
  const sourceHash=prior?.sourceHash||sha(fs.readFileSync(source));
  const adapter=await loadAdapter(options.urlSkill);
  const html=options.htmlFile?fs.readFileSync(options.htmlFile,'utf8'):await fetchHtml(url);
  const escaped=String(article.title).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const expected=snapshot(`<html><head></head><body><h1 id="activity-name">${escaped}</h1><div id="js_content">${article.content}</div></body></html>`,url,adapter);
  const actual=snapshot(html,url,adapter),result=compare(expected,actual,ledger);
  const report={binding,mediaLedgerSha256:options.ledgerFile?sha(fs.readFileSync(options.ledgerFile)):null,checks:result.checks,expected,actual};const reportHash=sha(JSON.stringify(report));
  const reportFile=stateFile+'.comparison-'+reportHash+'.json';savePrivate(reportFile,report);
  const reviewed=options.acceptReport===reportHash&&!!options.reviewNote?.trim();
  if(options.acceptReport&&!reviewed)throw Error('Review hash is stale or review note is missing. Refetch and inspect the new private comparison.');
  const state={version:1,kind:'wechat-publication',binding,sourceHash,evidence:options.htmlFile?'provided-html':'fetched-live',status:result.passed?'article_compared':reviewed?'article_reviewed':'differences',reportHash,reportFile,checks:result.checks,checkedAt:new Date().toISOString(),playback:'unknown',...(reviewed?{reviewNote:options.reviewNote}:{})};
  savePrivate(stateFile,state);
  if(!result.passed&&!reviewed)return {status:state.status,reportFile,reportHash,checks:result.checks,backfilled:false};
  if(options.htmlFile&&actual.canonicalUrl!==url)return {status:state.status,evidence:state.evidence,reportFile,reportHash,backfilled:false,linkVerification:'capture-url-unverified'};
  addVerifiedLink(source,sourceHash,url);
  savePrivate(stateFile,{...state,backfilled:true});
  return {status:state.status,evidence:state.evidence,url,reportFile,reportHash,backfilled:true,playback:'unknown'};
 });
}
if(import.meta.main)(async()=>{
 if(process.argv.includes('--help')){console.log('bun wechat-publication.ts --source <vault-note.md> --draft-receipt <private-draft.json> --state-file <private-publication.json> --url <official-url> [--url-skill <skill-dir>] [--html <provided-capture.html>] [--media-ledger <private-media.json>] [--accept-report <reviewed-hash> --review-note <reason>]\nRead-only remote comparison; append verified link only. Provided HTML and live fetch remain distinct evidence. No video playback verification, no source-body replacement, no draft writes.');return;}
 const a=args(process.argv.slice(2),['--source','--draft-receipt','--state-file','--url','--url-skill','--html','--media-ledger','--accept-report','--review-note']);
 for(const key of ['--source','--draft-receipt','--state-file','--url'])if(!a[key])throw Error(`${key} is required.`);
 const result=await verifyPublication({source:String(a['--source']),draftReceipt:String(a['--draft-receipt']),stateFile:String(a['--state-file']),url:String(a['--url']),urlSkill:a['--url-skill'] as string,htmlFile:a['--html'] as string,ledgerFile:a['--media-ledger'] as string,acceptReport:a['--accept-report'] as string,reviewNote:a['--review-note'] as string});
 console.log(JSON.stringify(result));if(result.status==='differences')process.exitCode=2;
})().catch(e=>{console.error('Publication check stopped: '+e.message.replace(/https?:\/\/\S+/g,'[URL]'));process.exitCode=1;});

import fs from 'node:fs';
import path from 'node:path';
import { sha, savePrivate, privateLocation, args } from './files.ts';
import { withReceiptLock } from '../x-publisher/x-post-state.ts';
export interface MediaItem { kind:'channels'|'local'; source:string; author:string; title:string; after:string; sourceSha256?:string; events:{event:'inserted'|'playback'|'published';result:'pass'|'fail'|'unknown';evidence:'user-confirmed'|'inspected';note:string;at:string;artifact?:{file:string;sha256:string}}[] }
export interface MediaLedger {version:1;kind:'wechat-media';draftId:string;title:string;items:Record<string,MediaItem>}
export async function updateMedia(file:string, input:Record<string,string|boolean>) {
  privateLocation(file);
  return withReceiptLock(file,async()=>{
    let state:MediaLedger;
    if(fs.existsSync(file))state=JSON.parse(fs.readFileSync(file,'utf8'));
    else state={version:1,kind:'wechat-media',draftId:String(input['--draft-id']||''),title:String(input['--article-title']||''),items:{}};
    if(state.version!==1||state.kind!=='wechat-media'||!state.draftId||!state.title)throw Error('A bound draft ID and article title are required.');
    if(input['--draft-id']&&input['--draft-id']!==state.draftId||input['--article-title']&&input['--article-title']!==state.title)throw Error('Media ledger belongs to another draft.');
    const key=String(input['--key']||'');if(!key)throw Error('--key is required.');
    if(input['--action']==='add') {
      if(state.items[key])throw Error('Media key already exists; preserve identity and record events instead.');
      const kind=input['--type'];if(kind!=='channels'&&kind!=='local')throw Error('--type must be channels or local.');
      const item:MediaItem={kind,source:String(input['--source']||''),author:String(input['--author']||''),title:String(input['--media-title']||''),after:String(input['--after']||''),events:[]};
      if(!item.source||!item.title||!item.after)throw Error('Source, media title and insertion anchor are required.');
      if(kind==='channels'){const u=new URL(item.source);if(u.protocol!=='https:'||u.hostname!=='weixin.qq.com'||!u.pathname.startsWith('/sph/')||u.search||u.hash)throw Error('Use the original public Channels share URL, not a signed player URL.');}
      if(kind==='local'){if(!fs.statSync(item.source).isFile())throw Error('Local video source must be a file.');item.sourceSha256=sha(fs.readFileSync(item.source));}
      state.items[key]=item;
    } else if(input['--action']==='record') {
      const item=state.items[key];if(!item)throw Error('Declare the media identity before recording evidence.');
      const event=input['--event'],result=input['--result'],evidence=input['--evidence'],note=String(input['--note']||'');
      if(!['inserted','playback','published'].includes(String(event))||!['pass','fail','unknown'].includes(String(result))||!['user-confirmed','inspected'].includes(String(evidence))||!note.trim())throw Error('Explicit event, result, evidence and note are required.');
      const artifact=input['--evidence-file']?{file:path.resolve(String(input['--evidence-file'])),sha256:sha(fs.readFileSync(String(input['--evidence-file'])))}:undefined;
      if(evidence==='inspected'&&!artifact)throw Error('Inspected evidence requires a local artifact already reviewed by the agent.');
      item.events.push({event:event as any,result:result as any,evidence:evidence as any,note,at:new Date().toISOString(),...(artifact?{artifact}:{})});
    } else throw Error('--action must be add or record.');
    savePrivate(file,state);
    return {draftId:state.draftId,key,status:state.items[key]!.events.at(-1)?.event||'declared',playback:state.items[key]!.events.filter(e=>e.event==='playback').at(-1)?.result||'unknown'};
  });
}
if(import.meta.main)(async()=>{
 if(process.argv.includes('--help')){console.log('bun media-ledger.ts --state-file <private.json> --key <id> --action add --draft-id <id> --article-title <title> --type channels|local --source <share-url|file> --media-title <title> --author <author> --after <paragraph>\nRecord independently: --action record --event inserted|playback|published --result pass|fail|unknown --evidence user-confirmed|inspected --note <reason> [--evidence-file <reviewed-artifact>]\nThis command only records evidence; it never uploads, inserts, plays or publishes.');return;}
 const a=args(process.argv.slice(2),['--state-file','--key','--action','--draft-id','--article-title','--type','--source','--media-title','--author','--after','--event','--result','--evidence','--note','--evidence-file']);
 if(!a['--state-file'])throw Error('--state-file is required.');console.log(JSON.stringify(await updateMedia(String(a['--state-file']),a)));
})().catch(e=>{console.error(e.message);process.exitCode=1;});

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { sha, savePrivate, outsideNotes, publicBytes, args } from './files.ts';
export interface PreparedX {
  version: 1; kind: 'x-images'; source: { file: string; sha256: string };
  related: { file: string; sha256: string }[];
  text: { file: string; sha256: string };
  images: { file: string; source: string; sha256: string; caption: string }[];
}
export function projectX(markdown: string) {
  let body=markdown.replace(/\r\n/g,'\n').replace(/^---\n[\s\S]*?\n---\s*\n/,'').replace(/<!--[\s\S]*?-->/g,'');
  body=body.replace(/^## 关联\s*\n[\s\S]*?(?=^## |$(?![\s\S]))/gm,'').replace(/^>\s*(?:发布链接|X 长帖)：.*$/gm,'');
  const images: { source: string; caption: string }[]=[];
  body=body.replace(/!\[([^\]\n]*)\]\((https:\/\/img\.jdy\.systems\/[^\s)]+\.webp)\)/g,(match,alt,source,offset)=>{
    const previous=body.slice(0,offset).trim().split(/\n\s*\n/).pop()||'';
    images.push({source,caption:alt||previous.replace(/^#+\s*/,'')});return '';
  });
  if(images.length>4)throw Error('More than four images: select the approved screenshots before preparing.');
  if(/!\[|!\[\[|\[\[|```|^\s*\|/m.test(body))throw Error('Unsupported/unresolved Markdown: review media, internal links, code or tables before preparing.');
  body=body.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,'$1 ($2)').replace(/^## 配图\s*$/gm,'配图：').replace(/^#{1,6}\s+/gm,'').replace(/^\s*---\s*$/gm,'').replace(/\*\*([^*]+)\*\*/g,'$1');
  if(/<\/?[A-Za-z][^>]*>/.test(body))throw Error('HTML requires an explicit plain-text rendering before preparing.');
  const text=body.replace(/[ \t]+$/gm,'').replace(/\n{3,}/g,'\n\n').trim();
  if(!text&&!images.length)throw Error('Empty X payload.');
  return {text,images};
}
export async function prepareX(source: string, out?: string, related: string[] = [], download = (u:string)=>publicBytes(u,['img.jdy.systems'],20*1024*1024)) {
  const sourceFile=path.resolve(source), raw=fs.readFileSync(sourceFile,'utf8');
  const projected=projectX(raw), sourceHash=sha(raw);
  const directory=path.resolve(out||path.join(os.tmpdir(),'jdy-writer-prepared',sha(sourceFile+sourceHash).slice(0,24)));
  outsideNotes(directory,sourceFile);
  fs.mkdirSync(directory,{recursive:true,mode:0o700});
  const file=path.join(directory,'prepared.json');
  if(fs.existsSync(file)) {
    const loaded=loadPrepared(file);
    if(loaded.manifest.source.file!==sourceFile||loaded.manifest.source.sha256!==sourceHash||JSON.stringify(loaded.manifest.related.map(r=>r.file))!==JSON.stringify(related.map(p=>path.resolve(p))))throw Error('Prepared output belongs to different inputs. Use a fresh directory.');
    return file;
  }
  if(fs.readdirSync(directory).length)throw Error('Prepared directory contains incomplete or unrelated files; inspect it or use a fresh private directory.');
  const manifest:PreparedX={version:1,kind:'x-images',source:{file:sourceFile,sha256:sourceHash},related:related.map(p=>({file:path.resolve(p),sha256:sha(fs.readFileSync(p))})),text:{file:path.join(directory,'approved.txt'),sha256:sha(projected.text)},images:[]};
  for(const [index,img] of projected.images.entries()) {
    const bytes=await download(img.source);
    if(bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WEBP')throw Error(`Image ${index+1} is not a WebP; no prepared manifest was committed.`);
    const imageFile=path.join(directory,`${String(index+1).padStart(2,'0')}.webp`);
    fs.writeFileSync(imageFile,bytes,{mode:0o600});manifest.images.push({...img,file:imageFile,sha256:sha(bytes)});
  }
  if(sha(fs.readFileSync(sourceFile))!==sourceHash)throw Error('Source changed during preparation.');
  fs.writeFileSync(manifest.text.file,projected.text,{mode:0o600});
  savePrivate(file,manifest);return file;
}
export function loadPrepared(file: string) {
  const manifest=JSON.parse(fs.readFileSync(file,'utf8')) as PreparedX;
  if(manifest.version!==1||manifest.kind!=='x-images'||!Array.isArray(manifest.images)||manifest.images.length>4||!Array.isArray(manifest.related))throw Error('Invalid prepared X manifest.');
  for(const artifact of [manifest.text,...manifest.images]) {
    if(path.dirname(fs.realpathSync(artifact.file))!==fs.realpathSync(path.dirname(file)))throw Error('Prepared artifacts must remain inside their private output directory.');
  }
  for(const item of [manifest.source,...manifest.related,manifest.text,...manifest.images])if(sha(fs.readFileSync(item.file))!==item.sha256)throw Error('Prepared input changed; review and prepare again, preserving any existing publication receipt.');
  return {manifest,text:fs.readFileSync(manifest.text.file,'utf8'),images:manifest.images.map(i=>i.file),sources:[manifest.source.file,...manifest.related.map(i=>i.file)]};
}
if(import.meta.main)(async()=>{
  if(process.argv.includes('--help')) { console.log('bun prepare-x.ts --source <approved-x.md> [--out <private-dir>] [--related-source <original.md>]\nOutputs prepared.json, exact approved.txt, and ordered local WebP files. Never publishes or changes notes.');return; }
  const a=args(process.argv.slice(2),['--source','--out','--related-source']);
  if(!a['--source'])throw Error('--source is required.');
  console.log(await prepareX(a['--source'] as string,a['--out'] as string|undefined,a['--related-source']?[a['--related-source'] as string]:[]));
})().catch(e=>{console.error(e.message);process.exitCode=1;});

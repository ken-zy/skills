import { test, expect } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { counterNumber, receiptNumbers, inspectArticleNumbers } from './wechat-number.ts';
function fixture() {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wechat-number-'));
  const counter=path.join(dir,'article-counter.txt');fs.writeFileSync(counter,'215\n');
  const receipts=path.join(dir,'receipts');fs.mkdirSync(receipts);
  return {dir,counter,receipts,clean:()=>fs.rmSync(dir,{recursive:true,force:true})};
}
const record=(n:number)=>({version:1,identity:'bound',mediaId:`draft-${n}`,uploads:{},article:{title:`${n}. Article`,content:'body'}});
test('combine private baseline and receipts without Git or network dependencies',()=>{
 const f=fixture();
 try {
  fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(216)));
  fs.writeFileSync(path.join(f.receipts,'b.json'),JSON.stringify(record(217)));
  const plan=inspectArticleNumbers(f.counter,f.receipts);
  expect(plan.next).toBe(218);expect(plan.reservation).toBe(false);
  expect(plan.evidence.map(x=>x.number)).toEqual([215,216,217]);
  expect(fs.readFileSync(f.counter,'utf8')).toBe('215\n');
 } finally {f.clean();}
});
test('private baseline ahead of receipts is preserved',()=>{
 const f=fixture();
 try {fs.writeFileSync(f.counter,'219\n');fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(217)));expect(inspectArticleNumbers(f.counter,f.receipts).next).toBe(220);}finally{f.clean();}
});
test('receipts suffice without a baseline; empty installations stop rather than reuse a number',()=>{
 const f=fixture();try {
  fs.unlinkSync(f.counter);
  expect(()=>inspectArticleNumbers(f.counter,f.receipts)).toThrow('No numbering evidence');
  fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(221)));
  expect(inspectArticleNumbers(f.counter,f.receipts).next).toBe(222);
 }finally{f.clean();}
});
test('CLI reads private state outside Git with no git or gh executable available',()=>{
 const f=fixture();try {
  fs.writeFileSync(f.counter,'221\n');
  const result=Bun.spawnSync([process.execPath,path.join(import.meta.dir,'wechat-number.ts'),'--counter-file',f.counter,'--receipts-dir',f.receipts],{cwd:f.dir,env:{...process.env,PATH:''}});
  expect(result.exitCode).toBe(0);
  expect(JSON.parse(result.stdout.toString())).toMatchObject({next:222,reservedThrough:221,reservation:false});
 }finally{f.clean();}
});
test('pending or malformed receipt stops numbering, but known private backups do not reserve twice',()=>{
 const f=fixture();try {
  const file=path.join(f.receipts,'a.json');const pending={...record(217),mediaId:undefined,pending:{operation:'create',article:{title:'217. Article'}}};
  fs.writeFileSync(file,JSON.stringify(pending));expect(()=>receiptNumbers(f.receipts)).toThrow('Unresolved');
  fs.renameSync(file,file.replace('.json','.before-verify-1.json'));expect(receiptNumbers(f.receipts)).toEqual([]);
  fs.writeFileSync(file,'{bad');expect(()=>receiptNumbers(f.receipts)).toThrow('Unreadable');
 }finally{f.clean();}
});
test('invalid private counter or symlink stops numbering',()=>{
 const f=fixture();try {
  for(const raw of ['','0','-1','215oops','1.5','9007199254740991']) {
   expect(()=>counterNumber(raw)).toThrow();
   fs.writeFileSync(f.counter,raw);
   expect(()=>inspectArticleNumbers(f.counter,f.receipts)).toThrow();
  }
  fs.unlinkSync(f.counter);fs.symlinkSync(path.join(f.dir,'missing'),f.counter);
  fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(221)));
  expect(()=>inspectArticleNumbers(f.counter,f.receipts)).toThrow();
 }finally{f.clean();}
});

test('conflicting confirmed drafts sharing one number require reconciliation',()=>{
 const f=fixture();try{
  fs.writeFileSync(path.join(f.receipts,'one.json'),JSON.stringify(record(217)));
  fs.writeFileSync(path.join(f.receipts,'two.json'),JSON.stringify({...record(217),mediaId:'different-draft'}));
  expect(()=>receiptNumbers(f.receipts)).toThrow('Duplicate');
 }finally{f.clean();}
});

test('known-ID readback differences reserve occupied numbers without blocking unrelated articles',()=>{
 const f=fixture();try{
  fs.writeFileSync(path.join(f.receipts,'known.json'),JSON.stringify({...record(219),pending:{operation:'create',article:{title:'219. Article'}}}));
  expect(receiptNumbers(f.receipts)).toEqual([{source:'receipt-known-draft:known.json',number:219}]);
  fs.writeFileSync(path.join(f.receipts,'collision.json'),JSON.stringify({...record(219),mediaId:'other-draft'}));
  expect(()=>receiptNumbers(f.receipts)).toThrow('Duplicate');
 }finally{f.clean();}
});

test('user-confirmed publication keeps its number without fabricating a verified draft snapshot',async()=>{
 const {DraftSession}=await import('./wechat-draft.ts');const f=fixture();try{
  const file=path.join(f.receipts,'published.json');
  fs.writeFileSync(file,JSON.stringify({...record(219),article:undefined,pending:{operation:'create',article:{title:'219. Article'}}}),{mode:0o600});
  DraftSession.recordPublished(file,'/legacy/article.md','draft-219','219. Article','User confirmed publication');
  expect(receiptNumbers(f.receipts)).toEqual([{source:'receipt:published.json',number:219}]);
  const saved=JSON.parse(fs.readFileSync(file,'utf8'));saved.publication.evidence='guessed';fs.writeFileSync(file,JSON.stringify(saved));
  expect(()=>receiptNumbers(f.receipts)).toThrow('Invalid publication');
 }finally{f.clean();}
});

test('a pending title change reserves both old and newly occupied numbers for the same known draft',()=>{
 const f=fixture();try{
  fs.writeFileSync(path.join(f.receipts,'renamed.json'),JSON.stringify({...record(218),pending:{operation:'update',article:{title:'219. Renamed'}}}));
  expect(receiptNumbers(f.receipts).map(e=>e.number)).toEqual([218,219]);
 }finally{f.clean();}
});

test('receipt evidence has deterministic file order even when the filesystem enumerates in reverse',()=>{
 const f=fixture(),read=fs.readdirSync;
 try {
  fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(216)));
  fs.writeFileSync(path.join(f.receipts,'b.json'),JSON.stringify(record(217)));
  fs.readdirSync=((directory:any,...rest:any[])=>directory===f.receipts?['b.json','a.json']:(read as any)(directory,...rest)) as typeof fs.readdirSync;
  expect(receiptNumbers(f.receipts).map(item=>item.number)).toEqual([216,217]);
 }finally{fs.readdirSync=read;f.clean();}
});

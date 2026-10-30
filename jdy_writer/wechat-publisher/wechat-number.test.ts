import { test, expect } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { counterNumber, receiptNumbers, inspectArticleNumbers } from './wechat-number.ts';
function fixture() {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wechat-number-'));
  fs.mkdirSync(path.join(dir,'jdy_writer'));fs.writeFileSync(path.join(dir,'jdy_writer/article-counter.txt'),'215\n');
  const receipts=path.join(dir,'receipts');fs.mkdirSync(receipts);
  return {dir,receipts,clean:()=>fs.rmSync(dir,{recursive:true,force:true})};
}
const record=(n:number)=>({version:1,identity:'bound',mediaId:`draft-${n}`,uploads:{},article:{title:`${n}. Article`,content:'body'}});
function runner(prNumber=218) {
 const calls:string[][]=[];
 const run=(program:string,args:string[])=>{
  calls.push([program,...args]);
  if(program==='git') {
   if(args[0]==='fetch')return '';
   if(args[0]==='show')return '215\n';
   return 'git@github.com:ken-zy/skills.git\n';
  }
  const endpoint=args.at(-1)!;
  if(endpoint.includes('/contents/'))return JSON.stringify({encoding:'base64',content:Buffer.from(String(prNumber)+'\n').toString('base64')});
  if(endpoint.includes('/files?'))return JSON.stringify([[{filename:'jdy_writer/article-counter.txt',status:'modified'}]]);
  const pr={number:38,head:{sha:'a'.repeat(40)},state:'open'};
  return JSON.stringify(endpoint.includes('?state=open')?[[pr]]:pr);
 };
 return {run,calls};
}
test('combine main/local/confirmed receipts/open PR head counters rather than reusing main+1',()=>{
 const f=fixture(),r=runner();
 try {
  fs.writeFileSync(path.join(f.receipts,'a.json'),JSON.stringify(record(216)));
  fs.writeFileSync(path.join(f.receipts,'b.json'),JSON.stringify(record(217)));
  const plan=inspectArticleNumbers(f.dir,f.receipts,r.run);
  expect(plan.next).toBe(219);expect(plan.reservation).toBe(false);
  expect(plan.evidence.map(x=>x.number)).toEqual([215,215,216,217,218]);
  expect(r.calls.some(c=>c.at(-1)?.endsWith('?ref='+'a'.repeat(40)))).toBe(true);
 } finally {f.clean();}
});
test('local counter ahead of main is preserved; no receipt is required for a new installation',()=>{
 const f=fixture(),r=runner(216);
 try {fs.writeFileSync(path.join(f.dir,'jdy_writer/article-counter.txt'),'217\n');expect(inspectArticleNumbers(f.dir,f.receipts,r.run).next).toBe(218);}finally{f.clean();}
});
test('pending or malformed receipt stops numbering, but known private backups do not reserve twice',()=>{
 const f=fixture();try {
  const file=path.join(f.receipts,'a.json');const pending={...record(217),mediaId:undefined,pending:{operation:'create',article:{title:'217. Article'}}};
  fs.writeFileSync(file,JSON.stringify(pending));expect(()=>receiptNumbers(f.receipts)).toThrow('Unresolved');
  fs.renameSync(file,file.replace('.json','.before-verify-1.json'));expect(receiptNumbers(f.receipts)).toEqual([]);
  fs.writeFileSync(file,'{bad');expect(()=>receiptNumbers(f.receipts)).toThrow('Unreadable');
 }finally{f.clean();}
});
test('counter parse and failed remote evidence fail closed',()=>{
 for(const raw of ['','0','-1','215oops','1.5','9007199254740991'])expect(()=>counterNumber(raw)).toThrow();
 const f=fixture();try{expect(()=>inspectArticleNumbers(f.dir,f.receipts,()=>{throw new Error('offline')})).toThrow();}finally{f.clean();}
});
test('PR changing during inspection and counter deletion cannot produce a candidate',()=>{
 for(const mode of ['moved','deleted']) {
  const f=fixture(),r=runner();
  try {
   expect(()=>inspectArticleNumbers(f.dir,f.receipts,(program,args)=>{
    if(mode==='moved'&&args.at(-1)==='repos/ken-zy/skills/pulls/38')return JSON.stringify({state:'open',head:{sha:'b'.repeat(40)}});
    if(mode==='deleted'&&args.at(-1)?.includes('/files?'))return JSON.stringify([[{filename:'jdy_writer/article-counter.txt',status:'removed'}]]);
    return r.run(program,args);
   })).toThrow();
  }finally{f.clean();}
 }
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

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { projectX, prepareX, loadPrepared } from './prepare-x.ts';
import { loadAdapter, snapshot, compare, verifyPublication, draftBaseline } from './wechat-publication.ts';
import { updateMedia } from './media-ledger.ts';
const url='https://mp.weixin.qq.com/s/public-article';
const image='https://mmbiz.qpic.cn/mmbiz_png/Asset123/0?wx_fmt=png';
function fixture(t:any) {
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'writer-pipeline-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 fs.mkdirSync(path.join(dir,'notes'));const source=path.join(dir,'notes/article.md');fs.writeFileSync(source,'# 原文章\n\n原正文。\n\n## 关联\n\n- [[来源]]\n');
 return {dir,source,state:path.join(dir,'private/publication.json')};
}
const paragraph='看到异常应该再查一下信息源头，不能看到维护提示就停下。这是作者仍在复盘的判断。';
const body=`<p>${paragraph}</p><p>社区收益只是发帖者测算。</p><img src="${image}"><p><a href="https://example.com/source">来源</a></p>`;
const html=(content=body)=>`<html><head><meta property="og:url" content="${url}"></head><body><h2 id="activity-name">220. 原文章</h2><div id="js_content">${content}</div></body></html>`;
test('X projection retains exact voice, captions and citations, strips vault metadata and selects four ordered screenshots',()=>{
 const pictures=Array.from({length:4},(_,i)=>`图${i+1}说明，仍属猜测。\n\n![](https://img.jdy.systems/manual/${i+1}.webp)`).join('\n\n');
 const result=projectX(`# 原标题\n\n有点不甘心。\n\n[来源](https://example.com/a)\n\n## 配图\n\n${pictures}\n\n## 关联\n\n- [[原稿]]\n\n<!-- 私有注释 -->\n> 发布链接：https://x.com/test/status/1`);
 assert.equal(result.images.length,4);assert.ok(result.images[3].source.endsWith('/4.webp'));
 assert.ok(result.text.includes('有点不甘心。'));assert.ok(result.text.includes('来源 (https://example.com/a)'));assert.ok(result.text.includes('图4说明，仍属猜测。'));
 assert.ok(!/关联|私有注释|发布链接|!\[/.test(result.text));
});
test('unsupported Markdown and too many screenshots stop before preparing',()=>{
 for(const raw of ['[[未处理]]','![](https://other.example/a.png)','```code```','| 表格 |',Array.from({length:5},(_,i)=>`![](https://img.jdy.systems/manual/${i}.webp)`).join('\n')])assert.throws(()=>projectX(raw));
});
test('prepared payload caches inputs, preserves source, catches edits and rejects failed image downloads',async t=>{
 const f=fixture(t);const md='# 原标题\n\n正文。\n\n图一。\n\n![](https://img.jdy.systems/manual/1.webp)';fs.writeFileSync(f.source,md);
 const bytes=Buffer.from('RIFF0000WEBPtest');let downloads=0;
 const file=await prepareX(f.source,path.join(f.dir,'prepared'),[],async()=>{downloads++;return bytes;});
 const prepared=loadPrepared(file);assert.equal(prepared.images.length,1);assert.equal(fs.readFileSync(f.source,'utf8'),md);
 await prepareX(f.source,path.join(f.dir,'prepared'),[],async()=>{throw Error('must reuse');});assert.equal(downloads,1);
 fs.writeFileSync(prepared.manifest.text.file,'changed');assert.throws(()=>loadPrepared(file),/changed/);
 await assert.rejects(prepareX(f.source,path.join(f.dir,'bad'),[],async()=>Buffer.from('not an image')),/not a WebP/);
 assert.ok(!fs.existsSync(path.join(f.dir,'bad/prepared.json')));
 await assert.rejects(prepareX(f.source,path.join(f.dir,'notes/private'),[],async()=>bytes),/outside/);
});
test('public article parser preserves lazy images and detects changed text, image order and lost links',async()=>{
 const adapter=await loadAdapter(),expected=snapshot(html(),url,adapter);
 const lazy=snapshot(html(body.replace(`src="${image}"`,`data-src="${image.replace('/0?','/640?')}&from=appmsg"`)),url,adapter);
 assert.ok(compare(expected,lazy).passed);
 for(const changed of [body.replace('社区收益','确定收益'),body.replace('Asset123','Other123'),body.replace('<a href="https://example.com/source">来源</a>','来源')])assert.ok(!compare(expected,snapshot(html(changed),url,adapter)).passed);
 assert.throws(()=>snapshot('<html>登录</html>',url,adapter),/body unavailable/);
});
test('declared video identity and insertion anchor are independently compared; signed player URL is excluded from report',async()=>{
 const adapter=await loadAdapter();const native='<mp-common-videosnap data-nickname="作者" data-desc="视频标题" data-url="https://signed.example/video?token=SECRET"></mp-common-videosnap>';
 const actual=snapshot(html(body.replace('</p>',`</p>${native}`)),url,adapter),expected=snapshot(html(),url,adapter);
 const ledger:any={items:{clip:{kind:'channels',source:'https://weixin.qq.com/sph/public',author:'作者',title:'视频标题',after:paragraph,events:[]}}};
 assert.ok(compare(expected,actual,ledger).passed);assert.ok(!compare(expected,actual).passed);
 ledger.items.clip.after='另一个段落';assert.ok(!compare(expected,actual,ledger).passed);
 assert.ok(!JSON.stringify(actual).includes('SECRET'));
});
test('official comparison is idempotent, does not modify draft receipt and keeps provided HTML evidence distinct',async t=>{
 const f=fixture(t),receipt=path.join(f.dir,'draft.json'),capture=path.join(f.dir,'capture.html');
 const draft=JSON.stringify({mediaId:'draft-1',article:{title:'220. 原文章',content:body},uploads:{}});fs.writeFileSync(receipt,draft);fs.writeFileSync(capture,html());
 const options={source:f.source,draftReceipt:receipt,stateFile:f.state,url,htmlFile:capture};
 const first=await verifyPublication(options,async()=>{throw Error('must use provided HTML');});assert.equal(first.status,'article_compared');assert.equal(first.evidence,'provided-html');
 await verifyPublication(options);assert.equal(fs.readFileSync(f.source,'utf8').split(url).length-1,1);assert.equal(fs.readFileSync(receipt,'utf8'),draft);
 assert.equal(JSON.parse(fs.readFileSync(f.state,'utf8')).playback,'unknown');
});
test('differences require a current reviewed hash; fresh changes invalidate acceptance and preserve author edits',async t=>{
 const f=fixture(t),receipt=path.join(f.dir,'draft.json');fs.writeFileSync(receipt,JSON.stringify({mediaId:'draft-1',article:{title:'220. 原文章',content:body},uploads:{}}));
 const options={source:f.source,draftReceipt:receipt,stateFile:f.state,url};
 const first=await verifyPublication(options,async()=>html(body.replace('社区收益','作者修改收益')));assert.equal(first.status,'differences');assert.ok(!fs.readFileSync(f.source,'utf8').includes(url));
 await assert.rejects(verifyPublication({...options,acceptReport:first.reportHash,reviewNote:'已查看差异'},async()=>html(body.replace('社区收益','再次修改收益'))),/stale/);
 const reviewed=await verifyPublication({...options,acceptReport:first.reportHash,reviewNote:'已审查并保留后台修改'},async()=>html(body.replace('社区收益','作者修改收益')));
 assert.equal(reviewed.status,'article_reviewed');assert.equal(reviewed.evidence,'fetched-live');assert.ok(fs.readFileSync(f.source,'utf8').includes('原正文'));
});
test('concurrent source changes and another draft ledger block unsafe completion',async t=>{
 const f=fixture(t),receipt=path.join(f.dir,'draft.json');fs.writeFileSync(receipt,JSON.stringify({mediaId:'draft-1',article:{title:'220. 原文章',content:body}}));
 const options={source:f.source,draftReceipt:receipt,stateFile:f.state,url};
 await assert.rejects(verifyPublication(options,async()=>{fs.appendFileSync(f.source,'作者新增内容');return html();}),/Source changed/);
 assert.ok(fs.readFileSync(f.source,'utf8').includes('作者新增内容'));assert.ok(!fs.readFileSync(f.source,'utf8').includes(url));
 const ledger=path.join(f.dir,'media.json');fs.writeFileSync(ledger,JSON.stringify({version:1,kind:'wechat-media',draftId:'other',title:'220. 原文章',items:{}}));
 await assert.rejects(verifyPublication({...options,ledgerFile:ledger},async()=>html()),/another draft/);
});
test('media events do not infer playback or publication and bind draft identity',async t=>{
 const f=fixture(t),file=path.join(f.dir,'media.json');
 const add={'--action':'add','--key':'fish','--draft-id':'draft-1','--article-title':'220. 原文章','--type':'channels','--source':'https://weixin.qq.com/sph/public','--author':'作者','--media-title':'视频标题','--after':paragraph};
 assert.equal((await updateMedia(file,add)).playback,'unknown');
 const record={'--action':'record','--key':'fish','--event':'inserted','--result':'pass','--evidence':'user-confirmed','--note':'用户确认插入同一篇文章'};
 assert.equal((await updateMedia(file,record)).playback,'unknown');
 await assert.rejects(updateMedia(file,{...record,'--draft-id':'other'}),/another draft/);
 await assert.rejects(updateMedia(file,{...record,'--event':'playback','--evidence':'inspected'}),/artifact/);
 const evidence=path.join(f.dir,'observed.txt');fs.writeFileSync(evidence,'已观察播放器实际播放');
 await updateMedia(file,{...record,'--event':'playback','--evidence':'inspected','--evidence-file':evidence});
 const state=JSON.parse(fs.readFileSync(file,'utf8'));assert.equal(state.items.fish.events.length,2);assert.ok(!state.items.fish.events.some((e:any)=>e.event==='published'));
 assert.equal(fs.statSync(file).mode&0o777,0o600);
});

test('closed legacy draft uses only an identity-bound same-directory publication backup',t=>{
 const f=fixture(t),file=path.join(f.dir,'draft.json'),backup='draft.json.before-published-test.json';
 const state={mediaId:'draft-1',identity:'account-source',publication:{title:'220. 原文章',backup}};
 fs.writeFileSync(file,JSON.stringify(state));fs.writeFileSync(path.join(f.dir,backup),JSON.stringify({mediaId:'draft-1',identity:'account-source',pending:{article:{title:'220. 原文章',content:body}}}));
 assert.equal(draftBaseline(file).article.content,body);
 fs.writeFileSync(path.join(f.dir,backup),JSON.stringify({mediaId:'other',identity:'account-source',article:{title:'220. 原文章',content:body}}));assert.throws(()=>draftBaseline(file),/identity differs/);
 fs.writeFileSync(file,JSON.stringify({...state,publication:{...state.publication,backup:'../foreign.json'}}));assert.throws(()=>draftBaseline(file),/Unsafe/);
});

test('provided HTML without a matching canonical URL compares but cannot backfill an unverified link',async t=>{
 const f=fixture(t),receipt=path.join(f.dir,'draft.json'),capture=path.join(f.dir,'capture.html');
 fs.writeFileSync(receipt,JSON.stringify({mediaId:'draft-1',article:{title:'220. 原文章',content:body}}));
 fs.writeFileSync(capture,html().replace(`<meta property="og:url" content="${url}">`,''));
 const result=await verifyPublication({source:f.source,draftReceipt:receipt,stateFile:f.state,url,htmlFile:capture});
 assert.equal(result.status,'article_compared');assert.equal(result.backfilled,false);assert.ok(!fs.readFileSync(f.source,'utf8').includes(url));
});
test('private preparation refuses a symlink back into the note directory',async t=>{
 const f=fixture(t);const link=path.join(f.dir,'private-link');fs.symlinkSync(path.dirname(f.source),link,'dir');
 await assert.rejects(prepareX(f.source,path.join(link,'output')),/outside/);
});

test('public source redirects stop without following captcha or fetching a second URL',async()=>{
 const {publicBytes}=await import('./files.ts');const previous=globalThis.fetch;let requests=0;
 try{globalThis.fetch=(async()=>{requests++;return new Response(null,{status:302,headers:{location:'https://mp.weixin.qq.com/mp/captcha?token=private'}});}) as typeof fetch;
 await assert.rejects(publicBytes(url,['mp.weixin.qq.com'],1024),/redirected/);assert.equal(requests,1);
 }finally{globalThis.fetch=previous;}
});

test('changed table rows, cell associations, span or header semantics cannot pass as identical article text',async()=>{
 const adapter=await loadAdapter();
 const expected=snapshot(html(body+'<table><tr><th>A</th><th>B</th></tr><tr><td>C</td><td>D</td></tr></table>'),url,adapter);
 for(const table of ['<table><tr><th>A</th><th>B</th><td>C</td><td>D</td></tr></table>','<table><tr><th colspan="2">AB</th></tr><tr><td>C</td><td>D</td></tr></table>','<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>']){
  const result=compare(expected,snapshot(html(body+table),url,adapter));assert.equal(result.checks.tables,false);assert.equal(result.passed,false);
 }
});
test('link labels remain bound to their targets even if global article text and href order match',async()=>{
 const adapter=await loadAdapter();
 const expected=snapshot(html(body+'<p><a href="https://example.com/a">ETH</a><a href="https://example.com/b">BTC</a></p>'),url,adapter);
 const actual=snapshot(html(body+'<p><a href="https://example.com/a">ETHBTC</a><a href="https://example.com/b"></a></p>'),url,adapter);
 assert.equal(expected.text,actual.text);assert.equal(compare(expected,actual).checks.links,false);
});
test('blank media anchors and missing Channels authors fail before evidence is saved',async t=>{
 const f=fixture(t),file=path.join(f.dir,'media.json');
 const base={'--action':'add','--key':'clip','--draft-id':'draft-1','--article-title':'220. 原文章','--type':'channels','--source':'https://weixin.qq.com/sph/public','--author':'作者','--media-title':'视频标题','--after':paragraph};
 for(const changed of [{'--after':'   '},{'--author':''},{'--media-title':'\n '}])await assert.rejects(updateMedia(file,{...base,...changed}),/required/);
 assert.ok(!fs.existsSync(file));
 const adapter=await loadAdapter(),expected=snapshot(html(),url,adapter);
 assert.throws(()=>compare(expected,expected,{items:{clip:{kind:'channels',source:'https://weixin.qq.com/sph/public',author:'作者',title:'视频标题',after:' ',events:[]}}} as any),/required/);
});

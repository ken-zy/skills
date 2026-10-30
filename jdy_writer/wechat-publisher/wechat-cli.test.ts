import { test, expect } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Full CLI with fake credentials and in-process fake API. No real WeChat/R2 request is allowed.
test("CLI roundtrip: metadata -> original URL, one create, cached images, one in-place update, stable number, same-cover crop after mobile editing", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-cli-test-"));
  const file = path.join(dir, "article.md");
  const state = path.join(dir, "state.json");
  const image = path.join(dir, "image.png");
  const api = path.join(import.meta.dir, "wechat-api.ts");
  const remote = path.join(dir, "remote.json");
  const log = path.join(dir, "calls.jsonl");
  const prelude = `
    import fs from "node:fs";
    const remote=${JSON.stringify(remote)}, log=${JSON.stringify(log)};
    globalThis.fetch=async(input,init)=>{
      const url=String(input); const pathname=new URL(url).pathname;
      fs.appendFileSync(log,JSON.stringify({pathname, ...(pathname.endsWith("/update") ? {sentCover:JSON.parse(init.body).articles.thumb_media_id,sentCrop:JSON.parse(init.body).articles.cover_info} : {})})+"\\n");
      if(url==="https://img.example/0") return new Response(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6X1sAAAAASUVORK5CYII=","base64"),{headers:{"Content-Type":"image/png"}});
      if(!url.startsWith("https://api.weixin.qq.com/")) throw new Error("Unexpected request");
      if(pathname.endsWith("/token")) return Response.json({access_token:"FAKE_TOKEN"});
      if(pathname.endsWith("/uploadimg")) return Response.json({url:"https://mmbiz.qpic.cn/body"});
      if(pathname.endsWith("/add_material")) return Response.json({media_id:"cover",url:"https://mmbiz.qpic.cn/cover"});
      const payload=JSON.parse(init.body);
      if(pathname.endsWith("/add")){fs.writeFileSync(remote,JSON.stringify({...payload.articles[0],thumb_url:"https://mmbiz.qpic.cn/article-cover"}));return Response.json({media_id:"same-draft"});}
      if(pathname.endsWith("/get")) return Response.json({news_item:[JSON.parse(fs.readFileSync(remote,"utf8"))]});
      if(pathname.endsWith("/update")){fs.writeFileSync(remote,JSON.stringify({...JSON.parse(fs.readFileSync(remote,"utf8")),...payload.articles}));return Response.json({errcode:0});}
      throw new Error("Unexpected endpoint");
    };
    process.argv=[process.execPath,${JSON.stringify(api)},...JSON.parse(process.env.FAKE_ARGS)];
    await import(${JSON.stringify(api)});
  `;
  const run = (extra: string[]) => Bun.spawnSync([process.execPath, "-e", prelude], {
    cwd: dir,
    env: { ...process.env, HOME: dir, WECHAT_APP_ID: "FAKE_APP", WECHAT_APP_SECRET: "FAKE_SECRET", FAKE_ARGS: JSON.stringify([file, "--state-file", state, ...extra]) },
  });
  try {
    fs.writeFileSync(image, Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6X1sAAAAASUVORK5CYII=", "base64"));
    fs.writeFileSync(file, '# Title\n\nBody one.\n\n![](./image.png)\n\n[观看宣传片](https://v.example/one.mp4)\n\n<!-- 公众号阅读原文: https://v.example/one.mp4 -->\n');
    const dry = run(["--dry-run"]);
    if (dry.exitCode) throw new Error(dry.stderr.toString());
    expect(dry.exitCode).toBe(0);
    expect(JSON.parse(dry.stdout.toString()).sourceUrl).toBe("https://v.example/one.mp4");
    expect(fs.existsSync(log)).toBe(false);
    const first = run(["--title", "215. Title", "--cover", image]);
    if (first.exitCode) throw new Error(first.stderr.toString());
    expect(JSON.parse(first.stdout.toString())).toMatchObject({ operation: "created", published: false, status: "draft_verified" });
    fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace("Body one.", "Body two."));
    const second = run([]);
    if (second.exitCode) throw new Error(second.stderr.toString());
    expect(JSON.parse(second.stdout.toString())).toMatchObject({ operation: "updated", media_id: "same-draft", title: "215. Title" });
    const third = run([]);
    if (third.exitCode) throw new Error(third.stderr.toString());
    expect(JSON.parse(third.stdout.toString()).operation).toBe("unchanged");
    const saved = JSON.parse(fs.readFileSync(remote, "utf8"));
    expect(saved.content).toContain("Body two.");
    expect(saved.content).toContain("引用链接");
    expect(saved.content_source_url).toBe("https://v.example/one.mp4");
    expect(saved.content).not.toContain("公众号阅读原文");
    const paths = fs.readFileSync(log, "utf8").trim().split("\n").map(x => JSON.parse(x).pathname);
    for (const endpoint of ["/cgi-bin/draft/add", "/cgi-bin/draft/update", "/cgi-bin/material/add_material", "/cgi-bin/media/uploadimg"]) expect(paths.filter(x => x === endpoint)).toHaveLength(1);
    const receipt = fs.readFileSync(state, "utf8");
    expect(receipt).not.toContain("FAKE_TOKEN"); expect(receipt).not.toContain("FAKE_SECRET");
    const mobileCrop = { crop_percent_list: [{ ratio: "1_1", x1: "0.25", x2: "0.75" }] };
    fs.writeFileSync(remote, JSON.stringify({ ...saved, thumb_media_id: "", cover_info: mobileCrop }));
    fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace("Body two.", "Merged mobile body."));
    const mobile = run(["--accept-remote", "--cover", image]);
    if (mobile.exitCode) throw new Error(mobile.stderr.toString());
    expect(JSON.parse(mobile.stdout.toString())).toMatchObject({ operation: "updated", media_id: "same-draft" });
    const final = JSON.parse(fs.readFileSync(remote, "utf8"));
    expect(final.thumb_media_id).toBe("cover");
    expect(final.cover_info).toEqual(mobileCrop);
    const calls = fs.readFileSync(log, "utf8").trim().split("\n").map(x => JSON.parse(x));
    const writes = calls.filter(x => x.pathname === "/cgi-bin/draft/update");
    expect(writes).toHaveLength(2);
    expect(writes[1].sentCover).toBe("cover");
    expect(writes[1].sentCrop).toEqual(mobileCrop);
    expect(calls.filter(x => x.pathname === "/cgi-bin/material/add_material")).toHaveLength(1);

  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test("CLI accepts HTTP/HTTPS cover URLs and still resolves local relative cover paths", () => {
  for (const cover of ["http://img.example/0", "https://img.example/0", "covers/relative cover.png"]) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-cover-cli-"));
    const file = path.join(dir, "article.html");
    const calls = path.join(dir, "calls.json");
    const api = path.join(import.meta.dir, "wechat-api.ts");
    const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6X1sAAAAASUVORK5CYII=";
    const prelude = `
      import fs from "node:fs";
      let article; const calls=[];
      globalThis.fetch=async(input,init)=>{
        const url=String(input); calls.push(url); fs.writeFileSync(${JSON.stringify(calls)},JSON.stringify(calls));
        if(url===${JSON.stringify(cover)}) return new Response(Buffer.from(${JSON.stringify(png)},"base64"),{headers:{"Content-Type":"image/png"}});
        if(!url.startsWith("https://api.weixin.qq.com/")) throw new Error("Unexpected request");
        const pathname=new URL(url).pathname;
        if(pathname.endsWith("/token")) return Response.json({access_token:"FAKE_TOKEN"});
        if(pathname.endsWith("/add_material")) return Response.json({media_id:"cover",url:"https://mmbiz.qpic.cn/cover"});
        const body=JSON.parse(init.body);
        if(pathname.endsWith("/add")){article=body.articles[0];return Response.json({media_id:"draft"});}
        if(pathname.endsWith("/get")) return Response.json({news_item:[article]});
        throw new Error("Unexpected endpoint");
      };
      process.argv=[process.execPath,${JSON.stringify(api)},${JSON.stringify(file)},"--cover",${JSON.stringify(cover)}];
      await import(${JSON.stringify(api)});
    `;
    try {
      fs.writeFileSync(file, "<html><head><title>Cover test</title></head><body><p>No body images.</p></body></html>");
      if (!cover.startsWith("http")) {
        fs.mkdirSync(path.join(dir, "covers"));
        fs.writeFileSync(path.join(dir, cover), Buffer.from(png, "base64"));
      }
      const result = Bun.spawnSync([process.execPath, "-e", prelude], {
        cwd: dir, env: { ...process.env, HOME: dir, WECHAT_APP_ID: "FAKE_APP", WECHAT_APP_SECRET: "FAKE_SECRET" },
      });
      if (result.exitCode) throw new Error(result.stderr.toString());
      expect(JSON.parse(result.stdout.toString())).toMatchObject({ operation: "created", status: "draft_verified", published: false });
      const urls: string[] = JSON.parse(fs.readFileSync(calls, "utf8"));
      expect(urls.filter(url => new URL(url).pathname === "/cgi-bin/material/add_material")).toHaveLength(1);
      expect(urls.filter(url => url === cover)).toHaveLength(cover.startsWith("http") ? 1 : 0);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  }
});

test('verify-only uses receipt identity after source cleanup and only calls token/get; mismatch keeps pending', () => {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wechat-verify-cli-'));
  const source=path.join(dir,'deleted-publish.md'),state=path.join(dir,'state.json'),log=path.join(dir,'calls.jsonl');
  const api=path.join(import.meta.dir,'wechat-api.ts');
  const expected={title:'217. PF',content:'<p><img src="https://mmbiz.qpic.cn/mmbiz_jpg/abc123/0?from=appmsg"><br>35%</p>',thumb_media_id:'cover',cover_info:{crop:'keep'}};
  const {createHash}=require('node:crypto');
  const key=createHash('sha256').update('FAKE_APP').digest('hex');
  const identity=createHash('sha256').update(key+'\0'+source).digest('hex');
  const initial={version:1,identity,mediaId:'existing-draft',uploads:{},pending:{operation:'create',article:expected}};
  const prelude=`
    import fs from 'node:fs';
    globalThis.fetch=async(input,init)=>{
      const pathname=new URL(String(input)).pathname;
      fs.appendFileSync(${JSON.stringify(log)},pathname+'\\n');
      if(pathname.endsWith('/token'))return Response.json({access_token:'FAKE_TOKEN'});
      if(pathname.endsWith('/draft/get')){
        const a=${JSON.stringify(expected)};
        a.content=a.content.replace('src=','data-src=').replace('/0?','/640?').replace('<br>','<br></br>');
        if(process.env.CORRUPT==='yes')a.content=a.content.replace('35%','100%');
        return Response.json({news_item:[a]});
      }
      throw new Error('Unexpected mutation/upload/render request');
    };
    process.argv=[process.execPath,${JSON.stringify(api)},${JSON.stringify(source)},'--state-file',${JSON.stringify(state)},'--verify-only',...JSON.parse(process.env.EXTRA||'[]')];
    await import(${JSON.stringify(api)});
  `;
  const run=(corrupt=false,extra:string[]=[])=>Bun.spawnSync([process.execPath,'-e',prelude],{cwd:dir,env:{...process.env,HOME:dir,WECHAT_APP_ID:'FAKE_APP',WECHAT_APP_SECRET:'FAKE_SECRET',CORRUPT:corrupt?'yes':'no',EXTRA:JSON.stringify(extra)}});
  try {
    fs.writeFileSync(state,JSON.stringify(initial),{mode:0o600});
    const bad=run(true);expect(bad.exitCode).toBe(1);expect(JSON.parse(fs.readFileSync(state,'utf8')).pending).toBeDefined();
    const ok=run();if(ok.exitCode)throw new Error(ok.stderr.toString());
    expect(JSON.parse(ok.stdout.toString())).toMatchObject({operation:'verified',published:false,title:'217. PF'});
    expect(JSON.parse(fs.readFileSync(state,'utf8')).pending).toBeUndefined();
    const calls=fs.readFileSync(log,'utf8').trim().split('\n');
    expect(calls).toEqual(['/cgi-bin/token','/cgi-bin/draft/get','/cgi-bin/token','/cgi-bin/draft/get']);
    expect(fs.existsSync(source)).toBe(false);
    const before=fs.readFileSync(log,'utf8');
    expect(run(false,['--title','overwrite']).exitCode).toBe(1);
    expect(fs.readFileSync(log,'utf8')).toBe(before);
    fs.unlinkSync(state);expect(run().exitCode).toBe(1);
    expect(fs.readFileSync(log,'utf8')).toBe(before);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('CLI inspect/reconcile keeps remote content, enforces the inspected hash and rejects mixed edits before network',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wechat-reconcile-cli-'));
 const api=path.join(import.meta.dir,'wechat-api.ts'), source=path.join(dir,'deleted-publish.md'),state=path.join(dir,'state.json'),remote=path.join(dir,'remote.json'),log=path.join(dir,'calls.jsonl');
 const {createHash}=require('node:crypto');const key=createHash('sha256').update('FAKE_APP').digest('hex');
 const expected={title:'219. Test',content:'<p>Original <a href="https://example.test">reference</a></p>',thumb_media_id:'cover'};
 const initial={version:1,identity:createHash('sha256').update(key+'\0'+source).digest('hex'),mediaId:'draft-219',uploads:{},pending:{operation:'create',article:expected}};
 const prelude=`
  import fs from 'node:fs';
  globalThis.fetch=async(input,init)=>{
   const p=new URL(String(input)).pathname;fs.appendFileSync(${JSON.stringify(log)},p+'\\n');
   if(p.endsWith('/token'))return Response.json({access_token:'FAKE_TOKEN'});
   if(p.endsWith('/draft/get'))return Response.json({news_item:[JSON.parse(fs.readFileSync(${JSON.stringify(remote)},'utf8'))]});
   throw new Error('Unexpected write/upload');
  };
  process.argv=[process.execPath,${JSON.stringify(api)},${JSON.stringify(source)},'--state-file',${JSON.stringify(state)},...JSON.parse(process.env.EXTRA)];await import(${JSON.stringify(api)});
 `;
 const run=(extra:string[])=>Bun.spawnSync([process.execPath,'-e',prelude],{cwd:dir,env:{...process.env,HOME:dir,WECHAT_APP_ID:'FAKE_APP',WECHAT_APP_SECRET:'FAKE_SECRET',EXTRA:JSON.stringify(extra)}});
 try{
  fs.writeFileSync(state,JSON.stringify(initial));fs.writeFileSync(remote,JSON.stringify({...expected,content:'<p>Original reference</p><mp-common-videosnap data-id="inserted"></mp-common-videosnap>'}));
  const before=fs.readFileSync(state,'utf8'),inspect=run(['--inspect-only']);if(inspect.exitCode)throw new Error(inspect.stderr.toString());
  const report=JSON.parse(inspect.stdout.toString());expect(report.content).toMatchObject({textEqual:true,linksEqual:false,nativeMediaEqual:false});
  expect(fs.readFileSync(state,'utf8')).toBe(before);
  const rejected=run(['--reconcile-receipt','--readback-sha256','0'.repeat(64),'--review-note','Reviewed']);expect(rejected.exitCode).toBe(1);expect(fs.readFileSync(state,'utf8')).toBe(before);
  const accepted=run(['--reconcile-receipt','--readback-sha256',report.readbackSha256,'--review-note','Reviewed link behavior and preserved the inserted video card']);if(accepted.exitCode)throw new Error(accepted.stderr.toString());
  expect(JSON.parse(accepted.stdout.toString())).toMatchObject({status:'draft_reconciled',remoteWrites:false,published:false});
  const saved=JSON.parse(fs.readFileSync(state,'utf8'));expect(saved.pending).toBeUndefined();expect(saved.article.content).toContain('mp-common-videosnap');
  const calls=fs.readFileSync(log,'utf8');expect(calls.trim().split('\n').every(p=>['/cgi-bin/token','/cgi-bin/draft/get'].includes(p))).toBe(true);
  for(const extra of [['--inspect-only','--cover','overwrite'],['--reconcile-receipt','--readback-sha256',report.readbackSha256,'--review-note','Reviewed','--title','overwrite'],['--verify-only','--inspect-only']]){
   expect(run(extra).exitCode).toBe(1);expect(fs.readFileSync(log,'utf8')).toBe(calls);
  }
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('CLI record-published is credential-free and offline, preserves unresolved evidence and is idempotent',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wechat-close-cli-')),api=path.join(import.meta.dir,'wechat-api.ts');
 const source=path.join(dir,'deleted.md'),state=path.join(dir,'state.json');
 const initial={version:1,identity:'legacy-account-bound',mediaId:'draft-219',uploads:{},pending:{operation:'create',article:{title:'219. Test',content:'<p>Original</p>'}}};
 const prelude=`
  import fs from 'node:fs';const original=fs.readFileSync;
  fs.readFileSync=function(file,...args){if(String(file).endsWith('/.env')||String(file).includes('wechat-network.json'))throw new Error('Credential/config read forbidden');return original.call(fs,file,...args);};
  globalThis.fetch=async()=>{throw new Error('Network forbidden');};
  process.argv=[process.execPath,${JSON.stringify(api)},${JSON.stringify(source)},'--state-file',${JSON.stringify(state)},'--record-published','--expected-media-id','draft-219','--expected-title','219. Test','--confirmation-note','User confirmed publication',...JSON.parse(process.env.EXTRA||'[]')];await import(${JSON.stringify(api)});
 `;
 const run=(extra:string[]=[])=>{const env={...process.env,HOME:dir,EXTRA:JSON.stringify(extra)};delete env.WECHAT_APP_ID;delete env.WECHAT_APP_SECRET;return Bun.spawnSync([process.execPath,'-e',prelude],{cwd:dir,env});};
 try{
  fs.writeFileSync(state,JSON.stringify(initial),{mode:0o600});const before=fs.readFileSync(state,'utf8');
  expect(run(['--cover','unexpected']).exitCode).toBe(1);expect(fs.readFileSync(state,'utf8')).toBe(before);
  const first=run();if(first.exitCode)throw new Error(first.stderr.toString());expect(JSON.parse(first.stdout.toString())).toMatchObject({status:'publication_user_confirmed',evidence:'user-confirmed',remoteWrites:false});
  const saved=JSON.parse(fs.readFileSync(state,'utf8'));expect(saved.pending).toBeUndefined();expect(saved.publication.draftVerification).toBe('unverified');
  expect(JSON.parse(fs.readFileSync(path.join(dir,saved.publication.backup),'utf8'))).toEqual(initial);
  const second=run();if(second.exitCode)throw new Error(second.stderr.toString());expect(JSON.parse(second.stdout.toString()).operation).toBe('unchanged');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});

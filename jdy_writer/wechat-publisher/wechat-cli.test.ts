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

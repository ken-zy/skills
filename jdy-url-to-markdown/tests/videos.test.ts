import { describe, expect, test } from "bun:test";
import { parseWechatHtml } from "../scripts/adapters/wechat";
import { persistVideos, VideoPersistenceError, validateMp4 } from "../scripts/media/persist-videos";
import { parse } from "../scripts/parser";
import { uploadWithR2Script } from "../scripts/media/r2-script";
import { parseExtend } from "../scripts/config";
import { mkdtemp, readFile, readdir, rm, writeFile, chmod } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";

const page = "https://mp.weixin.qq.com/s/example";
function article(body: string) {
  return `<html><head><title>视频归档测试</title></head><body><div id="js_content"><p>第一段正文。</p>${body}<p>最后一段正文。</p></div></body></html>`;
}
const mp4 = Buffer.concat([Buffer.from([0, 0, 0, 24]), Buffer.from("ftypisom"), Buffer.alloc(64)]);

describe("video extraction", () => {
  test("preserves WeChat containers once, in place, and resolves relative MP4 sources", () => {
    const result = parseWechatHtml(article('<span data-mpvid="wxv_123" class="video_iframe"><video src="//mpvideo.qpic.cn/test.mp4?key=private"></video></span><video><source src="/second.mp4" type="video/mp4"></video>'), page);
    expect(result.videos).toHaveLength(2);
    expect(result.videos![0].url).toBe("https://mpvideo.qpic.cn/test.mp4?key=private");
    expect(result.videos![1].url).toBe("https://mp.weixin.qq.com/second.mp4");
    expect(result.markdown.indexOf(result.videos![0].marker)).toBeGreaterThan(result.markdown.indexOf("第一段"));
    expect(result.markdown.indexOf(result.videos![1].marker)).toBeLessThan(result.markdown.indexOf("最后一段"));
  });
  test("keeps unresolved video placeholders rather than dropping them", () => {
    const result = parseWechatHtml(article('<iframe class="video_iframe" data-src="https://mp.weixin.qq.com/mp/readtemplate?vid=wxv_123"></iframe>'), page);
    expect(result.videos).toHaveLength(1);
    expect(result.videos![0].url).toBeUndefined();
    expect(result.markdown).toContain(result.videos![0].marker);
  });
  test("generic articles preserve video inside a figure without losing captions", () => {
    const result = parse(article('<figure><img src="/poster.jpg"><video src="/clip.mp4"></video><figcaption>演示片段</figcaption></figure>'),page,undefined,"#js_content");
    expect(result.videos).toHaveLength(1);
    expect(result.markdown).toContain(result.videos![0].marker);
    expect(result.markdown).toContain("演示片段");
    expect(result.markdown).toContain("/poster.jpg");
  });
});

describe("video persistence", () => {
  test("CLI returns exit 5 and preserves an existing archive on unresolved video", async () => {
    const root = await mkdtemp(join(tmpdir(),"video-cli-test-"));
    const body = '<article><h1>测试视频归档</h1><p>'+"这是用于验证失败关闭行为的完整正文段落。".repeat(15)+'</p><iframe class="video_iframe" src="https://example.com/video/embed"></iframe><p>'+"这里是第二段正文，必须保留既有的笔记内容。".repeat(15)+'</p></article>';
    const server = Bun.serve({hostname:"127.0.0.1",port:0,fetch:()=>new Response(`<html><head><title>测试视频归档</title></head><body>${body}</body></html>`,{headers:{"content-type":"text/html"}})});
    try {
      const target=join(root,"archive.md");
      await writeFile(target,"existing user archive\n");
      const proc=Bun.spawn(["bun",join(import.meta.dir,"../scripts/main.ts"),`http://127.0.0.1:${server.port}/article`,"--images","none","--videos","r2","-o",target],{cwd:root,stdout:"pipe",stderr:"pipe"});
      const [code,,err]=await Promise.all([proc.exited,new Response(proc.stdout).text(),new Response(proc.stderr).text()]);
      expect(code).toBe(5); expect(err).toContain("no downloadable MP4");
      expect(await readFile(target,"utf8")).toBe("existing user archive\n");
    } finally {server.stop(true); await rm(root,{recursive:true,force:true});}
  });
  test("downloads once, preserves both positions, verifies MP4, then cleans temp files", async () => {
    const root = await mkdtemp(join(tmpdir(), "video-test-"));
    try {
      const result = parseWechatHtml(article('<video src="https://cdn.example/a.mp4"></video><video src="https://cdn.example/a.mp4"></video>'), page);
      let downloads = 0, uploads = 0;
      const output = await persistVideos(result.markdown, result.videos, {
        mode: "r2", sourceUrl: page, tempRoot: root,
        fetchImpl: async (url, init) => {
          if (String(url).includes("cdn.example")) { downloads++; return new Response(mp4, {headers: {"content-type":"video/mp4"}}); }
          if (init?.method === "HEAD") return new Response(null, {headers: {"content-type":"video/mp4", "content-length":String(mp4.length)}});
          return new Response(mp4, {headers: {"content-type":"video/mp4"}});
        },
        validateFile: async path => { expect(await readFile(path)).toEqual(mp4); },
        uploader: async (path, key) => { uploads++; expect(await readFile(path)).toEqual(mp4); return `https://img.jdy.systems/${key}.mp4`; },
      });
      expect(downloads).toBe(1); expect(uploads).toBe(1);
      expect(output.match(/<video /g)).toHaveLength(2);
      expect(output).not.toContain("JDYVIDEO");
      expect(await readdir(root)).toEqual([]);
    } finally { await rm(root, {recursive:true, force:true}); }
  });
  test("unresolved video fails before any upload; none is an explicit opt out", async () => {
    const result = parseWechatHtml(article('<mpvideo vid="wxv_unresolved"></mpvideo>'), page);
    await expect(persistVideos(result.markdown, result.videos, {mode:"r2", sourceUrl:page})).rejects.toBeInstanceOf(VideoPersistenceError);
    const output = await persistVideos(result.markdown, result.videos, {mode:"none", sourceUrl:page});
    expect(output).not.toContain("JDYVIDEO");
    expect(output).toContain("未下载");
  });
  test("rejects HTML masquerading as MP4 and keeps downloads on verification failure", async () => {
    const root = await mkdtemp(join(tmpdir(), "video-test-"));
    const result = parseWechatHtml(article('<video src="https://cdn.example/a.mp4"></video>'), page);
    try {
      let uploads = 0;
      await expect(persistVideos(result.markdown, result.videos, {
        mode:"r2", sourceUrl:page, tempRoot:root,
        fetchImpl: async () => new Response("<html>denied</html>", {headers:{"content-type":"text/html"}}),
        uploader: async () => {uploads++; return "https://img.jdy.systems/bad.mp4";},
      })).rejects.toThrow("content type");
      expect(uploads).toBe(0);
      await expect(persistVideos(result.markdown, result.videos, {
        mode:"r2", sourceUrl:page, tempRoot:root,
        fetchImpl: async () => new Response(mp4, {headers:{"content-type":"video/mp4"}}),
        validateFile: async () => {},
        uploader: async () => {uploads++; return "https://evil.example/other.mp4";},
      })).rejects.toThrow("unexpected");
      expect(uploads).toBe(1);
      expect((await readdir(root)).length).toBeGreaterThan(0);
    } finally { await rm(root,{recursive:true,force:true}); }
  });
  test("validates configured video settings", () => {
    expect(parseExtend("default_video_mode: r2\nr2_video_upload_script: scripts/video.sh")).toEqual({defaultVideoMode:"r2",r2VideoUploadScript:"scripts/video.sh"});
    expect(() => parseExtend("default_video_mode: piclist")).toThrow();
  });
  test("streaming download enforces size cap before any uploader runs", async () => {
    const root = await mkdtemp(join(tmpdir(),"video-test-"));
    let uploads = 0;
    const result = parseWechatHtml(article('<video src="https://cdn.example/a.mp4"></video>'),page);
    try {
      await expect(persistVideos(result.markdown,result.videos,{
        mode:"r2",sourceUrl:page,tempRoot:root,maxBytes:32,
        fetchImpl:async()=>new Response(mp4,{headers:{"content-type":"video/mp4"}}),
        uploader:async()=>{uploads++;return "";},
      })).rejects.toThrow("size limit");
      expect(uploads).toBe(0);
    } finally {await rm(root,{recursive:true,force:true});}
  });
  test("retries truncated source reads, never retries an upload, and keeps the MP4", async () => {
    const root = await mkdtemp(join(tmpdir(),"video-test-"));
    let reads=0, uploads=0;
    const result = parseWechatHtml(article('<video src="https://cdn.example/a.mp4?token=SECRET"></video>'),page);
    try {
      await expect(persistVideos(result.markdown,result.videos,{
        mode:"r2",sourceUrl:page,tempRoot:root,
        fetchImpl:async()=>{reads++; if(reads===1) throw new Error("socket https://cdn.example/?token=SECRET"); return new Response(mp4,{headers:{"content-type":"video/mp4"}});},
        validateFile:async()=>{},
        uploader:async()=>{uploads++;throw new Error("uncertain remote result");},
      })).rejects.toThrow("uncertain remote result");
      expect(reads).toBe(2); expect(uploads).toBe(1);
      const [dir]=await readdir(root);
      expect(await readFile(join(root,dir,"video-001.mp4"))).toEqual(mp4);
    } finally {await rm(root,{recursive:true,force:true});}
  });
  test("does not upload any video if a later local video is invalid", async()=>{
    const root=await mkdtemp(join(tmpdir(),"video-test-"));
    const result=parseWechatHtml(article('<video src="https://cdn.example/a.mp4"></video><video src="https://cdn.example/b.mp4"></video>'),page);
    let uploads=0, validations=0;
    try {
      await expect(persistVideos(result.markdown,result.videos,{
        mode:"r2",sourceUrl:page,tempRoot:root,
        fetchImpl:async()=>new Response(mp4,{headers:{"content-type":"video/mp4"}}),
        validateFile:async()=>{if(++validations===2)throw new Error("invalid media");},
        uploader:async()=>{uploads++;return "";},
      })).rejects.toThrow("invalid media");
      expect(uploads).toBe(0);
    } finally {await rm(root,{recursive:true,force:true});}
  });
  test("fails public verification without deleting downloaded videos", async()=>{
    const root=await mkdtemp(join(tmpdir(),"video-test-"));
    const result=parseWechatHtml(article('<video src="https://cdn.example/a.mp4"></video>'),page);
    try {
      await expect(persistVideos(result.markdown,result.videos,{
        mode:"r2",sourceUrl:page,tempRoot:root,
        fetchImpl:async(_url,init)=>init?.method==="HEAD" ? new Response(null,{headers:{"content-type":"text/html"}}) : new Response(mp4,{headers:{"content-type":"video/mp4"}}),
        validateFile:async()=>{},uploader:async(_path,key)=>`https://img.jdy.systems/${key}.mp4`,
      })).rejects.toThrow("public MP4 metadata");
      const [dir]=await readdir(root);
      expect(await readFile(join(root,dir,"video-001.mp4"))).toEqual(mp4);
    } finally {await rm(root,{recursive:true,force:true});}
  });
  test("ffprobe validates real video and uploader passes MP4 MIME without removing input",async()=>{
    const root=await mkdtemp(join(tmpdir(),"video-test-"));
    try {
      const input=join(root,"sample.mp4");
      const gen=Bun.spawn(["ffmpeg","-v","error","-f","lavfi","-i","color=black:s=16x16:d=0.2","-an","-c:v","libx264","-pix_fmt","yuv420p",input],{stdout:"ignore",stderr:"pipe"});
      expect(await gen.exited).toBe(0);
      await expect(validateMp4(input)).resolves.toBeUndefined();
      const bad=join(root,"bad.mp4"); await writeFile(bad,mp4);
      await expect(validateMp4(bad)).rejects.toThrow();
      const npx=join(root,"npx");
      await writeFile(npx,'#!/bin/bash\nprintf "%s\\n" "$@" > "$VIDEO_TEST_ARGS"\n');
      await chmod(npx,0o700);
      const args=join(root,"args.txt");
      const script=join(import.meta.dir,"../scripts/media/r2-upload-video.sh");
      const proc=Bun.spawn(["bash",script,input,"web-articles/example/story/video-001"],{env:{...process.env,PATH:`${root}:${process.env.PATH}`,IMG_SUBDOMAIN:"img.test",R2_BUCKET:"test",VIDEO_TEST_ARGS:args},stdout:"pipe",stderr:"pipe"});
      const [code,out]=await Promise.all([proc.exited,new Response(proc.stdout).text(),new Response(proc.stderr).text()]);
      expect(code).toBe(0);
      expect(out.trim()).toBe("https://img.test/web-articles/example/story/video-001.mp4");
      expect(await readFile(args,"utf8")).toContain("--content-type=video/mp4");
      expect((await readFile(input)).length).toBeGreaterThan(0);
      const badKey=Bun.spawn(["bash",script,input,"web-articles/../video-001"],{stdout:"pipe",stderr:"pipe"});
      expect(await badKey.exited).toBe(1);
      const wrapper=join(root,"upload.sh");
      await writeFile(wrapper,'echo "https://img.jdy.systems/$2.mp4"\n');
      await expect(uploadWithR2Script(input,"web-articles/example/video-001",{scriptPath:wrapper,extension:"mp4"})).resolves.toEndWith(".mp4");
    } finally {await rm(root,{recursive:true,force:true});}
  });
});

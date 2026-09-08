import { mkdtemp, open, rm, stat } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import type { VideoReference } from "../types";
import type { FetchLike } from "./piclist";
import { buildR2ArticleKeyPrefix, uploadWithR2Script } from "./r2-script";

export type VideoMode = "remote" | "r2" | "none";
// The bundled uploader uses Wrangler single-object puts. Keep files bounded.
export const MAX_VIDEO_BYTES = 250 * 1024 * 1024;
export class VideoPersistenceError extends Error {
  constructor(message: string) { super(message); this.name = "VideoPersistenceError"; }
}
interface Options {
  mode: VideoMode;
  sourceUrl: string;
  scriptPath?: string;
  persistentHosts?: string[];
  tempRoot?: string;
  fetchImpl?: FetchLike;
  uploader?: (path: string, key: string) => Promise<string>;
  validateFile?: (path: string) => Promise<void>;
  maxBytes?: number;
}
function escapeHtml(value: string): string {
  return value.replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function isMp4(bytes: Uint8Array): boolean {
  return bytes.length >= 12 && Buffer.from(bytes).subarray(4,8).toString() === "ftyp";
}
export async function validateMp4(path: string): Promise<void> {
  const proc = Bun.spawn(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries", "format=format_name,duration:stream=codec_type", "-of", "json", path], {stdout:"pipe",stderr:"pipe"});
  const timer = setTimeout(() => proc.kill(), 30000);
  try {
    const [code, output] = await Promise.all([proc.exited, new Response(proc.stdout).text(), new Response(proc.stderr).text()]);
    if (code !== 0) throw new Error("ffprobe rejected the video");
    const info = JSON.parse(output);
    if (!info.format?.format_name?.split(",").includes("mp4") || !(Number(info.format.duration) > 0)
      || !info.streams?.some((s: {codec_type:string}) => s.codec_type === "video")) {
      throw new Error("file is not a playable MP4 video");
    }
  } finally { clearTimeout(timer); }
}
async function download(url: string, path: string, options: Options): Promise<void> {
  // Retry only source reads. Never retry uploads with an uncertain outcome.
  for (let attempt = 1; attempt <= 3; attempt++) {
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let file: Awaited<ReturnType<typeof open>> | undefined;
    try {
      const parsed = new URL(url);
      if (!["https:","http:"].includes(parsed.protocol) || parsed.username || parsed.password) throw new Error("unsupported video URL");
      const response = await (options.fetchImpl ?? fetch)(url, {
        headers: {referer:options.sourceUrl, "user-agent":"Mozilla/5.0 jdy-url-to-markdown"},
        signal: AbortSignal.timeout(120000),
      });
      reader = response.body?.getReader();
      if (!response.ok) throw new Error(`download HTTP ${response.status}`);
      const type = response.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
      if (type !== "video/mp4" && type !== "application/octet-stream") throw new Error("unsupported video content type");
      const limit = Math.min(options.maxBytes ?? MAX_VIDEO_BYTES, MAX_VIDEO_BYTES);
      const expected = response.headers.get("content-length");
      if (expected && Number(expected) > limit) throw new Error("video exceeds size limit");
      if (!reader) throw new Error("empty video response");
      file = await open(path, "w");
      let total = 0;
      let header = Buffer.alloc(0);
      while (true) {
        const {value,done} = await reader.read();
        if (done) break;
        total += value.length;
        if (total > limit) throw new Error("video exceeds size limit");
        if (header.length < 32) header = Buffer.concat([header, Buffer.from(value.subarray(0, 32-header.length))]);
        let offset = 0;
        while (offset < value.length) {
          const {bytesWritten} = await file.write(value, offset, value.length-offset);
          if (!bytesWritten) throw new Error("local write failed");
          offset += bytesWritten;
        }
      }
      if (!isMp4(header)) throw new Error("invalid MP4 header");
      if (expected && Number(expected) !== total) throw new Error("truncated video download");
      return;
    } catch (error) {
      // Avoid disclosing signed source URLs from network-library error messages.
      const message = error instanceof Error ? error.message : "network error";
      const safeMessage = /^(unsupported video|video exceeds|empty video|invalid MP4|truncated video|download HTTP|local write)/.test(message) ? message : "video download connection failed";
      if (attempt === 3 || /^(unsupported|video exceeds|invalid MP4|download HTTP 4)/.test(safeMessage)) throw new Error(safeMessage);
      await Bun.sleep(300 * attempt);
    } finally {
      await reader?.cancel().catch(() => {});
      await file?.close();
    }
  }
}
async function verify(url: string, size: number | undefined, fetchImpl: FetchLike): Promise<void> {
  const response = await fetchImpl(url, {method:"HEAD", redirect:"error", signal:AbortSignal.timeout(30000)});
  const length = Number(response.headers.get("content-length"));
  if (!response.ok || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "video/mp4"
    || !Number.isSafeInteger(length) || length <= 0 || (size !== undefined && length !== size)) throw new Error("public MP4 metadata verification failed");
  const sample = await fetchImpl(url, {headers:{Range:"bytes=0-31"}, redirect:"error", signal:AbortSignal.timeout(30000)});
  const reader = sample.body?.getReader();
  try {
    if (!sample.ok || !reader) throw new Error("public MP4 read failed");
    let header = Buffer.alloc(0);
    while (header.length < 12) {
      const {value,done} = await reader.read();
      if (done) break;
      header = Buffer.concat([header, Buffer.from(value.subarray(0,32-header.length))]);
    }
    if (!isMp4(header)) throw new Error("public object is not MP4");
  } finally { await reader?.cancel().catch(() => {}); }
}
export async function persistVideos(markdown: string, refs: VideoReference[] = [], options: Options): Promise<string> {
  if (!refs.length) return markdown;
  if (options.mode !== "r2") {
    for (const [i,ref] of refs.entries()) {
      const replacement = options.mode === "remote" && ref.url
        ? `<video controls preload="metadata" src="${escapeHtml(ref.url)}"></video>`
        : `[视频 ${i+1}（未下载，请查看原文）](<${options.sourceUrl.replace(/>/g,"%3E")}>)`;
      markdown = markdown.replaceAll(ref.marker,replacement);
    }
    return markdown;
  }
  const unresolved = refs.findIndex(ref => !ref.url);
  if (unresolved >= 0) throw new VideoPersistenceError(`Video ${unresolved+1}: no downloadable MP4 source; no Markdown written. Load the player in Chrome, or explicitly use --videos none.`);
  const hosts = options.persistentHosts ?? ["img.jdy.systems"];
  const fetchImpl = options.fetchImpl ?? fetch;
  const directory = await mkdtemp(join(options.tempRoot ?? tmpdir(),"jdy-url-videos-"));
  const prefix = buildR2ArticleKeyPrefix(options.sourceUrl);
  const targets = new Map<string,string>();
  let stage = "download";
  let index = 0;
  try {
    const prepared: Array<{url:string,path:string,key:string,size:number}> = [];
    for (const url of new Set(refs.map(ref => ref.url!))) {
      index++;
      const parsed = new URL(url);
      if (hosts.includes(parsed.hostname)) {
        if (parsed.protocol !== "https:" || !parsed.pathname.endsWith(".mp4") || parsed.search || parsed.hash) throw new Error("unexpected persistent URL");
        await verify(url,undefined,fetchImpl);
        targets.set(url,url);
        continue;
      }
      const path = join(directory,`video-${String(index).padStart(3,"0")}.mp4`);
      console.error(`[video ${index}] downloading MP4`);
      await download(url,path,options);
      stage = "local validation";
      await (options.validateFile ?? validateMp4)(path);
      prepared.push({url,path,key:`${prefix}/video-${String(index).padStart(3,"0")}`,size:(await stat(path)).size});
      stage = "download";
    }
    // All source files validated before the first upload. Retain originals on
    // any ambiguous upload/public verification failure; never delete R2 objects.
    for (const [i,item] of prepared.entries()) {
      index = i+1; stage = "upload";
      console.error(`[video ${index}] uploading MP4 (${item.size} bytes)`);
      const target = await (options.uploader ?? ((path,key) => uploadWithR2Script(path,key,{
        scriptPath:options.scriptPath ?? join(import.meta.dir,"r2-upload-video.sh"),extension:"mp4",
      })))(item.path,item.key);
      const parsed = new URL(target);
      if (parsed.protocol !== "https:" || !hosts.includes(parsed.hostname) || parsed.pathname !== `/${item.key}.mp4` || parsed.username || parsed.password || parsed.search || parsed.hash) throw new Error("unexpected uploader URL");
      stage = "public verification";
      await verify(target,item.size,fetchImpl);
      targets.set(item.url,target);
    }
    for (const ref of refs) markdown = markdown.replaceAll(ref.marker,`<video controls preload="metadata" src="${escapeHtml(targets.get(ref.url!)!)}"></video>`);
    await rm(directory,{recursive:true,force:true});
    return markdown;
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    // Suppress URL-bearing tool diagnostics, including query credentials.
    const safe = /https?:\/\//.test(message) ? "operation failed (source URL omitted)" : message;
    throw new VideoPersistenceError(`Video ${index} ${stage}: ${safe}. Temporary videos retained at ${directory}; no Markdown written.`);
  }
}

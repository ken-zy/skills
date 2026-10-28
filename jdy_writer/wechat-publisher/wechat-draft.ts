import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash } from "node:crypto";
import { WechatApiRejectedError, type WechatApiClient } from "./wechat-network.ts";

import { sameWechatHtml } from "./wechat-html.ts";

export type DraftArticle = Record<string, unknown> & { content: string; title: string };
type UploadReceipt = { media_id: string; url: string };
interface Receipt {
  version: 1;
  identity: string;
  mediaId?: string;
  article?: DraftArticle;
  uploads: Record<string, UploadReceipt>;
  cover?: { mediaId: string; url: string };
  pending?: { operation: "create" | "update"; article: DraftArticle };
}
const writable = ["article_type", "title", "author", "digest", "content", "content_source_url", "thumb_media_id", "cover_info", "need_open_comment", "only_fans_can_comment", "image_info"];
const observed = [...writable, "thumb_url"];
const hash = (value: string) => createHash("sha256").update(value).digest("hex");
export function defaultReceiptPath(source: string, account: string) {
  return path.join(os.homedir(), ".local/state/jdy-writer/drafts", hash(account + "\0" + path.resolve(source)) + ".json");
}
export function validateSourceUrl(value: string): string {
  if (!value) return ""; // Explicit clearing is supported.
  let url: URL;
  try { url = new URL(value); } catch { throw new Error("Invalid read-original URL"); }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || Buffer.byteLength(value) > 1024) throw new Error("Invalid read-original URL");
  return value;
}
export function readOriginalMetadata(text: string): string | undefined {
  const values = [...text.matchAll(/<!--\s*公众号阅读原文\s*[:：]\s*([^<>]*?)\s*-->/g)].map(m => m[1]!.trim());
  if (new Set(values).size > 1) throw new Error("Conflicting read-original metadata");
  return values.length ? validateSourceUrl(values[0]!) : undefined;
}
export function assertSupportedMedia(html: string) {
  if (/<\s*(?:iframe|video|mpvideo)\b|\bdata-(?:mpvid|vidtype)\s*=/i.test(html)) {
    throw new Error("Native video publishing is unverified; use a reference link and read-original URL, or the official editor");
  }
}
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k,v]) => [k, canonical(v)]));
  return value;
}
function field(value: unknown) { return JSON.stringify(canonical(value ?? "")); }
function same(a: Record<string, unknown>, b: Record<string, unknown>, keys = observed, platformFormatting = false) {
  return keys.every(key => {
    if (platformFormatting && key === "content" && typeof a[key] === "string" && typeof b[key] === "string") return sameWechatHtml(a[key], b[key]);
    return field(key === "article_type" ? a[key] || "news" : a[key]) === field(key === "article_type" ? b[key] || "news" : b[key]);
  });
}
function select(article: DraftArticle): DraftArticle {
  return Object.fromEntries(writable.filter(k => article[k] !== undefined).map(k => [k, article[k]])) as DraftArticle;
}

/** Private local receipt + exclusive lock. It contains article text, never API credentials. */
export class DraftSession {
  private state: Receipt;
  private lock: number;
  private released = false;
  private originalCover = "";
  private constructor(readonly file: string, readonly identity: string) {
    const dir = path.dirname(file);
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    if (fs.existsSync(file) && fs.lstatSync(file).isSymbolicLink()) throw new Error("Receipt must not be a symlink");
    this.lock = fs.openSync(file + ".lock", "wx", 0o600);
    fs.writeFileSync(this.lock, JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() }));
    try {
      this.state = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : { version: 1, identity, uploads: {} };
      if (this.state.version !== 1 || this.state.identity !== identity || !this.state.uploads || typeof this.state.uploads !== "object") throw new Error("Receipt identity or schema mismatch");
      fs.chmodSync(file + ".lock", 0o600);
    } catch (error) { this.close(); throw error; }
  }
  static open(file: string, source: string, account: string) {
    return new DraftSession(file, hash(account + "\0" + path.resolve(source)));
  }
  close() {
    if (this.released) return;
    this.released = true;
    fs.closeSync(this.lock);
    fs.unlinkSync(this.file + ".lock");
  }
  private persist() {
    const temp = this.file + ".tmp";
    const fd = fs.openSync(temp, "wx", 0o600);
    try { fs.writeFileSync(fd, JSON.stringify(this.state, null, 2)); fs.fsyncSync(fd); }
    finally { fs.closeSync(fd); }
    fs.renameSync(temp, this.file);
  }
  cachedUpload(key: string) { return this.state.uploads[key]; }
  recordUpload(key: string, receipt: UploadReceipt) {
    this.state.uploads[key] = receipt;
    this.persist();
  }
  private async get(mediaId: string, token: string, client: WechatApiClient): Promise<DraftArticle> {
    const data = await client.json<{ news_item?: DraftArticle[] }>("draft", `https://api.weixin.qq.com/cgi-bin/draft/get?access_token=${encodeURIComponent(token)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ media_id: mediaId }),
    });
    if (!Array.isArray(data.news_item) || data.news_item.length !== 1 || typeof data.news_item[0]?.content !== "string" || typeof data.news_item[0]?.title !== "string") throw new Error("Expected one article in draft; multi-article drafts require the official editor");
    return data.news_item[0];
  }
  async prepare(token: string, client: WechatApiClient, explicitId?: string, acceptRemote = false): Promise<DraftArticle | undefined> {
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt; use a separate receipt for another draft");
    const mediaId = explicitId || this.state.mediaId;
    if (!mediaId) {
      if (this.state.pending) throw new Error("Previous draft creation outcome unknown; inspect the draft box and supply --update-media-id, never blindly retry creation");
      return undefined;
    }
    const live = await this.get(mediaId, token, client);
    const previous = this.state.cover;
    if (!live.thumb_media_id && previous?.url && previous.url === live.thumb_url) this.originalCover = previous.mediaId;
    if (live.thumb_media_id && live.thumb_url) this.state.cover = { mediaId: String(live.thumb_media_id), url: String(live.thumb_url) };
    if (this.state.pending) {
      if (!same(select(live), this.state.pending.article, Object.keys(this.state.pending.article), true)) throw new Error("Previous draft write outcome unresolved; inspect remotely before editing or retrying");
      delete this.state.pending;
    } else if (this.state.article && !same(live, this.state.article)) {
      if (acceptRemote) {
        fs.writeFileSync(this.file + `.before-adopt-${Date.now()}.json`, JSON.stringify(this.state, null, 2), { flag: "wx", mode: 0o600 });
      } else {
        throw new Error("Draft changed in the official editor; reconcile local content, then use --accept-remote to adopt the latest metadata");
      }
    }
    this.state.mediaId = mediaId;
    this.state.article = live;
    this.persist();
    return structuredClone(live);
  }
  async verifyOnly(token: string, client: WechatApiClient, explicitId?: string) {
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt");
    const mediaId = this.state.mediaId || explicitId;
    const expected = this.state.pending?.article || this.state.article;
    if (!mediaId || !expected) throw new Error("Verification requires an existing receipt and a known draft ID");
    const live = await this.get(mediaId, token, client);
    const matches = this.state.pending
      ? same(live, expected, Object.keys(expected), true)
      : same(live, expected); // Editor changes remain strict after confirmation.
    if (!matches) throw new Error("Draft verification differs; receipt and pending preserved, no remote writes sent");
    fs.writeFileSync(this.file + `.before-verify-${Date.now()}.json`, JSON.stringify(this.state, null, 2), { flag: "wx", mode: 0o600 });
    this.state.mediaId = mediaId;
    this.state.article = live;
    if (live.thumb_media_id && live.thumb_url) this.state.cover = { mediaId: String(live.thumb_media_id), url: String(live.thumb_url) };
    delete this.state.pending;
    this.persist();
    return { media_id: mediaId, title: live.title, operation: "verified", status: "draft_verified", published: false };
  }
  recoverCover(live: DraftArticle) {
    // Never substitute a cropped thumbnail URL for a permanent full-image cover.
    return typeof live.thumb_media_id === "string" && live.thumb_media_id ? live.thumb_media_id : this.originalCover;
  }
  async save(article: DraftArticle, token: string, client: WechatApiClient) {
    assertSupportedMedia(article.content);
    if (article.content_source_url !== undefined) validateSourceUrl(String(article.content_source_url));
    const candidate = select(article);
    const mediaId = this.state.mediaId;
    if (mediaId) {
      const fresh = await this.get(mediaId, token, client);
      if (!this.state.article || !same(fresh, this.state.article)) throw new Error("Draft changed while preparing upload; no update sent");
      if (same(fresh, candidate, Object.keys(candidate), true)) return { media_id: mediaId, operation: "unchanged", status: "draft_verified", published: false };
    }
    if ((candidate.article_type ?? "news") === "news" && !candidate.thumb_media_id) throw new Error("Permanent article cover ID missing; supply --cover-media-id for the verified original image, or --cover for a new image");
    this.state.pending = { operation: mediaId ? "update" : "create", article: candidate };
    this.persist(); // A timeout/crash must not trigger an automatic duplicate create.
    const url = `https://api.weixin.qq.com/cgi-bin/draft/${mediaId ? "update" : "add"}?access_token=${encodeURIComponent(token)}`;
    let result: { media_id?: string; errcode?: number };
    try {
      result = await client.json("draft", url, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mediaId ? { media_id: mediaId, index: 0, articles: candidate } : { articles: [candidate] }),
      });
    } catch (error) {
      if (error instanceof WechatApiRejectedError) {
        // The platform explicitly refused this write. Keep the draft snapshot and
        // uploaded images, but let a corrected request proceed on a later run.
        delete this.state.pending;
        this.persist();
      }
      throw error;
    }
    if (mediaId && result.errcode !== 0) throw new Error("Draft update not confirmed; inspect before retrying");
    const savedId = mediaId || result.media_id;
    if (typeof savedId !== "string" || !savedId.trim()) throw new Error("Draft creation not confirmed; inspect before retrying");
    this.state.mediaId = savedId;
    this.persist();
    const verified = await this.get(savedId, token, client);
    if (!same(verified, candidate, Object.keys(candidate), true)) throw new Error("Draft readback differs; inspect remotely before retrying");
    this.state.article = verified;
    if (verified.thumb_media_id && verified.thumb_url) this.state.cover = { mediaId: String(verified.thumb_media_id), url: String(verified.thumb_url) };
    delete this.state.pending;
    this.persist();
    return { media_id: savedId, operation: mediaId ? "updated" : "created", status: "draft_verified", published: false };
  }
}

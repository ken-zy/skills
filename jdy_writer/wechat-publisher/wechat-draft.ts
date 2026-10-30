import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash, randomUUID } from "node:crypto";
import { WechatApiRejectedError, type WechatApiClient } from "./wechat-network.ts";

import { sameWechatHtml, describeWechatHtmlDifference } from "./wechat-html.ts";

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
  sourcePath?: string;
  reconciliation?: { snapshotHash: string; reviewedAt: string; note: string; backup: string };
  publication?: { status: "published"; evidence: "user-confirmed"; mediaId: string; title: string; confirmedAt: string; note: string; url?: string; draftVerification: "verified" | "reviewed" | "unverified"; backup: string };
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
  if (/<\s*(?:iframe|video|mpvideo|mp-common-videosnap)\b|\bdata-(?:mpvid|vidtype)\s*=/i.test(html)) {
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

export const draftSnapshotHash = (article: DraftArticle, mediaId: string) => hash(JSON.stringify(canonical({ mediaId, article })));
export function validPublication(receipt: Receipt): boolean {
  const p = receipt.publication;
  return !!p && p.status === "published" && p.evidence === "user-confirmed" && typeof p.mediaId === "string" && !!p.mediaId.trim() && p.mediaId === receipt.mediaId &&
    typeof p.title === "string" && !!p.title.trim() && typeof p.note === "string" && !!p.note.trim() &&
    typeof p.confirmedAt === "string" && Number.isFinite(Date.parse(p.confirmedAt)) &&
    ["verified", "reviewed", "unverified"].includes(p.draftVerification) && typeof p.backup === "string" && !!p.backup &&
    (p.url === undefined || isPublicationUrl(p.url));
}
function isPublicationUrl(value: string) {
  try { const u = new URL(value); return u.protocol === "https:" && u.hostname === "mp.weixin.qq.com" && !u.username && !u.password && (u.pathname === "/s" || u.pathname.startsWith("/s/")); } catch { return false; }
}
export function describeDraftDifference(expected: DraftArticle, live: DraftArticle, keys = Object.keys(expected), platformFormatting = true, mediaId = "") {
  return {
    differingFields: keys.filter(key => !same(live, expected, [key], platformFormatting)),
    content: describeWechatHtmlDifference(expected.content, live.content),
    readbackSha256: draftSnapshotHash(live, mediaId),
  };
}
export class DraftReadbackError extends Error {
  constructor(message: string, readonly report: ReturnType<typeof describeDraftDifference>) { super(message); this.name = "DraftReadbackError"; }
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
      if (this.state.version !== 1 || this.state.identity !== identity || !this.state.uploads || typeof this.state.uploads !== "object" || Array.isArray(this.state.uploads) || (this.state.publication && !validPublication(this.state))) throw new Error("Receipt identity or schema mismatch");
      fs.chmodSync(file + ".lock", 0o600);
    } catch (error) { this.close(); throw error; }
  }
  static open(file: string, source: string, account: string) {
    const session = new DraftSession(file, hash(account + "\0" + path.resolve(source)));
    session.state.sourcePath = path.resolve(source);
    return session;
  }
  /** Local-only closure: explicit receipt + ID + title, no credentials/network. */
  static recordPublished(file: string, source: string, expectedId: string, expectedTitle: string, note: string, url?: string) {
    if (!expectedId.trim() || !expectedTitle.trim() || !note.trim() || note.length > 2000 || (url !== undefined && !isPublicationUrl(url))) throw new Error("Publication confirmation requires an exact ID/title, a note and an optional official article URL");
    if (fs.lstatSync(file).isSymbolicLink()) throw new Error("Receipt must not be a symlink");
    const identity = JSON.parse(fs.readFileSync(file, "utf8")).identity;
    if (typeof identity !== "string" || !identity.trim()) throw new Error("Invalid receipt identity");
    const session = new DraftSession(file, identity);
    try {
      const state = session.state;
      if (state.sourcePath && state.sourcePath !== path.resolve(source)) throw new Error("Receipt source path conflicts with confirmation");
      const title = state.publication?.title || state.pending?.article.title || state.article?.title;
      if (state.mediaId !== expectedId || title !== expectedTitle) throw new Error("Publication confirmation ID/title differs from receipt");
      if (state.publication) {
        if (url !== undefined && url !== state.publication.url) throw new Error("Publication URL differs from recorded confirmation; review before changing it");
        return { operation: "unchanged", status: "publication_user_confirmed", evidence: "user-confirmed", remoteWrites: false };
      }
      const backup = session.backup("published");
      state.publication = { status: "published", evidence: "user-confirmed", mediaId: expectedId, title: expectedTitle, confirmedAt: new Date().toISOString(), note, ...(url ? { url } : {}), draftVerification: state.pending ? "unverified" : !state.article ? "unverified" : state.reconciliation?.snapshotHash === draftSnapshotHash(state.article, expectedId) ? "reviewed" : "verified", backup };
      state.sourcePath = path.resolve(source);
      delete state.pending; // Original write and expected HTML remain in the private backup.
      session.persist();
      return { operation: "recorded", status: "publication_user_confirmed", evidence: "user-confirmed", remoteWrites: false, backup };
    } finally { session.close(); }
  }
  private backup(reason: string) {
    const file = this.file + `.before-${reason}-${randomUUID()}.json`;
    fs.writeFileSync(file, JSON.stringify(this.state, null, 2), { flag: "wx", mode: 0o600 });
    return path.basename(file);
  }
  private assertActive() {
    if (this.state.publication) throw new Error("Receipt is marked published; draft writes and verification are closed, use the official editor for published content");
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
    this.assertActive();
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt; use a separate receipt for another draft");
    const mediaId = explicitId || this.state.mediaId;
    if (!mediaId) {
      if (this.state.pending) throw new Error("Previous draft creation outcome unknown; inspect the draft box and supply --update-media-id, never blindly retry creation");
      return undefined;
    }
    const live = await this.get(mediaId, token, client);
    // A local Markdown body cannot safely preserve an editor-inserted player/card.
    assertSupportedMedia(live.content);
    const previous = this.state.cover;
    if (!live.thumb_media_id && previous?.url && previous.url === live.thumb_url) this.originalCover = previous.mediaId;
    if (live.thumb_media_id && live.thumb_url) this.state.cover = { mediaId: String(live.thumb_media_id), url: String(live.thumb_url) };
    if (this.state.pending) {
      if (!same(select(live), this.state.pending.article, Object.keys(this.state.pending.article), true)) throw new DraftReadbackError("Previous draft write outcome unresolved; inspect remotely before editing or retrying", describeDraftDifference(this.state.pending.article, live, Object.keys(this.state.pending.article), true, mediaId));
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
    this.assertActive();
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt");
    const mediaId = this.state.mediaId || explicitId;
    const expected = this.state.pending?.article || this.state.article;
    if (!mediaId || !expected) throw new Error("Verification requires an existing receipt and a known draft ID");
    const live = await this.get(mediaId, token, client);
    const matches = this.state.pending
      ? same(live, expected, Object.keys(expected), true)
      : same(live, expected); // Editor changes remain strict after confirmation.
    if (!matches) throw new DraftReadbackError("Draft verification differs; receipt and pending preserved, no remote writes sent", describeDraftDifference(expected, live, this.state.pending ? Object.keys(expected) : observed, !!this.state.pending, mediaId));
    fs.writeFileSync(this.file + `.before-verify-${Date.now()}.json`, JSON.stringify(this.state, null, 2), { flag: "wx", mode: 0o600 });
    this.state.mediaId = mediaId;
    this.state.article = live;
    if (live.thumb_media_id && live.thumb_url) this.state.cover = { mediaId: String(live.thumb_media_id), url: String(live.thumb_url) };
    delete this.state.pending;
    this.persist();
    return { media_id: mediaId, title: live.title, operation: "verified", status: "draft_verified", published: false };
  }
  async inspectOnly(token: string, client: WechatApiClient, explicitId?: string) {
    this.assertActive();
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt");
    const mediaId = this.state.mediaId || explicitId;
    const expected = this.state.pending?.article || this.state.article;
    if (!mediaId || !expected) throw new Error("Inspection requires an existing receipt and a known draft ID");
    const live = await this.get(mediaId, token, client);
    const report = describeDraftDifference(expected, live, this.state.pending ? Object.keys(expected) : observed, !!this.state.pending, mediaId);
    const directory = path.join(path.dirname(this.file), ".inspections");
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    const inspectionFile = path.join(directory, `${path.basename(this.file)}-${randomUUID()}.json`);
    fs.writeFileSync(inspectionFile, JSON.stringify({ mediaId, expected, live, report }, null, 2), { flag: "wx", mode: 0o600 });
    return { operation: "inspected", status: "draft_found", published: false, remoteWrites: false, media_id: mediaId, inspectionFile, ...report };
  }
  async reconcileOnly(token: string, client: WechatApiClient, expectedHash: string, note: string, explicitId?: string) {
    this.assertActive();
    if (!/^[a-f0-9]{64}$/.test(expectedHash) || !note.trim() || note.length > 2000) throw new Error("Reconciliation requires the inspected snapshot hash and a review note");
    if (explicitId && this.state.mediaId && explicitId !== this.state.mediaId) throw new Error("Draft ID conflicts with receipt");
    const mediaId = this.state.mediaId || explicitId;
    const expected = this.state.pending?.article || this.state.article;
    if (!mediaId || !expected) throw new Error("Reconciliation requires a known draft ID and expected article");
    const live = await this.get(mediaId, token, client);
    if (draftSnapshotHash(live, mediaId) !== expectedHash) throw new Error("Draft changed since inspection or draft ID differs; inspect and review again");
    if (live.title !== expected.title) throw new Error("Draft title differs; reconcile article identity before accepting a snapshot");
    const backup = this.backup("reconcile");
    this.state.mediaId = mediaId;
    this.state.article = live;
    delete this.state.pending;
    this.state.reconciliation = { snapshotHash: expectedHash, reviewedAt: new Date().toISOString(), note, backup };
    if (live.thumb_media_id && live.thumb_url) this.state.cover = { mediaId: String(live.thumb_media_id), url: String(live.thumb_url) };
    this.persist();
    return { operation: "reconciled", status: "draft_reconciled", published: false, remoteWrites: false, backup };
  }
  recoverCover(live: DraftArticle) {
    // Never substitute a cropped thumbnail URL for a permanent full-image cover.
    return typeof live.thumb_media_id === "string" && live.thumb_media_id ? live.thumb_media_id : this.originalCover;
  }
  async save(article: DraftArticle, token: string, client: WechatApiClient) {
    this.assertActive();
    assertSupportedMedia(article.content);
    if (article.content_source_url !== undefined) validateSourceUrl(String(article.content_source_url));
    const candidate = select(article);
    const mediaId = this.state.mediaId;
    if (mediaId) {
      const fresh = await this.get(mediaId, token, client);
      assertSupportedMedia(fresh.content);
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
    if (!same(verified, candidate, Object.keys(candidate), true)) throw new DraftReadbackError("Draft readback differs; inspect remotely before retrying", describeDraftDifference(candidate, verified, Object.keys(candidate), true, savedId));
    this.state.article = verified;
    if (verified.thumb_media_id && verified.thumb_url) this.state.cover = { mediaId: String(verified.thumb_media_id), url: String(verified.thumb_url) };
    delete this.state.pending;
    this.persist();
    return { media_id: savedId, operation: mediaId ? "updated" : "created", status: "draft_verified", published: false };
  }
}

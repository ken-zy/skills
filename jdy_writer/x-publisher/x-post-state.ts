import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const CN_ACCOUNT = '_ThrowException';
export const sha256 = (value: string | Buffer) => crypto.createHash('sha256').update(value).digest('hex');
export interface PostManifest {
  account: string;
  profile: string;
  textSha256: string;
  images: { file: string; sha256: string }[];
  sources: { file: string; sha256: string; label: string }[];
}
export interface PostReceipt {
  version: 1;
  manifest: PostManifest;
  stage: 'waiting_login' | 'composing' | 'ready' | 'submitting' | 'submitted' | 'verified' | 'complete';
  port?: number;
  targetId?: string;
  url?: string;
  previewHashes?: string[];
  submittedAt?: string;
  verifiedAt?: string;
}
export function buildManifest(text: string, images: string[], profile: string, sources: string[]): PostManifest {
  if (!text.trim() && !images.length) throw Error('Provide text or images.');
  if (new Set(sources.map(file => path.resolve(file))).size !== sources.length) throw Error('Duplicate backfill target.');
  if (images.length > 4) throw Error('A single post supports at most four images; do not silently drop extras.');
  return {
    account: CN_ACCOUNT, profile: path.resolve(profile), textSha256: sha256(text),
    images: images.map(file => ({ file: path.resolve(file), sha256: sha256(fs.readFileSync(file)) })),
    sources: sources.map((file, i) => {
      if (path.extname(file) !== '.md') throw Error('Backfill targets must be Markdown files.');
      return { file: path.resolve(file), sha256: sha256(fs.readFileSync(file)), label: i === 0 ? '发布链接' : 'X 长帖' };
    }),
  };
}
export function writeReceipt(file: string, receipt: PostReceipt): void {
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, JSON.stringify(receipt, null, 2) + '\n', { mode: 0o600 });
  fs.renameSync(temp, file);
  fs.chmodSync(file, 0o600);
}
export function loadReceipt(file: string): PostReceipt {
  const r = JSON.parse(fs.readFileSync(file, 'utf8')) as PostReceipt;
  if (r.version !== 1 || r.manifest?.account !== CN_ACCOUNT || !['waiting_login','composing','ready','submitting','submitted','verified','complete'].includes(r.stage)) throw Error('Unsupported X receipt.');
  if (r.url) r.url = canonicalPostUrl(r.url);
  return r;
}
export function bindReceipt(file: string, manifest: PostManifest): PostReceipt {
  if (!fs.existsSync(file)) return { version: 1, manifest, stage: 'waiting_login' };
  const r = loadReceipt(file);
  if (JSON.stringify(r.manifest) !== JSON.stringify(manifest)) throw Error('Receipt input differs. Preserve the receipt and inspect; do not reset it to retry.');
  return r;
}
export function withReceiptLock<T>(file: string, work: () => Promise<T>): Promise<T> {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const lock = `${file}.lock`;
  const fd = fs.openSync(lock, 'wx', 0o600);
  fs.writeFileSync(fd, String(process.pid));
  return work().finally(() => { fs.closeSync(fd); fs.unlinkSync(lock); });
}
export function canonicalPostUrl(value: string): string {
  const u = new URL(value);
  if (u.protocol !== 'https:' || u.hostname !== 'x.com' || u.username || u.password || u.port) throw Error('Expected an HTTPS x.com post URL.');
  const match = u.pathname.match(/^\/([^/]+)\/status\/(\d+)\/?$/);
  if (!match || match[1].toLowerCase() !== CN_ACCOUNT.toLowerCase()) throw Error('Post URL belongs to a different account or is not a status URL.');
  return `https://x.com/${CN_ACCOUNT}/status/${match[2]}`;
}
// Recovery is read-only and must not depend on the original composer surviving a crash.
export function verificationUrl(r: PostReceipt, verifyOnly: boolean, publishedUrl?: string): string | undefined {
  if (publishedUrl && !verifyOnly) throw Error('--published-url requires --verify-only.');
  const url = publishedUrl ? canonicalPostUrl(publishedUrl) : r.url;
  if (r.url && url !== r.url) throw Error('Receipt already binds another published URL.');
  if (verifyOnly && !url) throw Error('Find the actual post and use --verify-only --published-url; no new submission is permitted.');
  return url;
}
export function assertCanSubmit(r: PostReceipt): void {
  if (r.url) return; // An already submitted receipt is only reverified, never clicked again.
  if (r.stage !== 'ready') throw Error('Only a ready receipt may submit. Compose without --submit, inspect previews, and reuse the same receipt. For an uncertain submission, inspect the actual post and use --verify-only --published-url.');
}
export function planPostPage(r: PostReceipt, targets: { targetId: string; url: string }[], verifyUrl?: string): { targetId?: string; url: string } {
  const target = targets.find(t => t.targetId === r.targetId);
  if (verifyUrl) {
    const url = canonicalPostUrl(verifyUrl);
    // Even a status page can contain an unsent reply. Inspect in a fresh task tab.
    return { targetId: undefined, url };
  }
  if (target && /^https:\/\/x\.com\//.test(target.url)) return { targetId: target.targetId, url: target.url };
  if (r.targetId && r.stage !== 'waiting_login') throw Error('Original composer is unavailable. Inspect before recovering; do not recreate and repost.');
  return { url: 'https://x.com/compose/post' };
}
export interface ComposerSnapshot { account?: string; editor: boolean; text: string; count: number; loaded: boolean; enabled: boolean }
export function assertComposerReady(r: PostReceipt, s: ComposerSnapshot, text: string): void {
  if (s.account?.toLowerCase() !== `/${CN_ACCOUNT.toLowerCase()}`) throw Error(`Expected @${CN_ACCOUNT}; account mismatch stops publication.`);
  if (!s.editor || s.text !== text || s.count !== r.manifest.images.length || !s.loaded || !s.enabled) throw Error('Composer text, image count, upload readiness, or long-post capability check failed. No submission.');
}
export interface PublishedSnapshot { url: string; author: string; text: string; photos: string[]; loaded: boolean }
export function assertPublished(r: PostReceipt, snapshot: PublishedSnapshot): void {
  if (canonicalPostUrl(snapshot.url) !== r.url || snapshot.author.toLowerCase() !== CN_ACCOUNT.toLowerCase()) throw Error('Published account or URL mismatch.');
  if (sha256(snapshot.text) !== r.manifest.textSha256) throw Error('Published text mismatch or still collapsed.');
  const stem = new URL(r.url!).pathname;
  if (!snapshot.loaded || snapshot.photos.length !== r.manifest.images.length || snapshot.photos.some((u, i) => (new URL(u, 'https://x.com').origin !== 'https://x.com' || new URL(u, 'https://x.com').pathname !== `${stem}/photo/${i + 1}`))) throw Error('Published media missing, not loaded, or out of order.');
}
export function backfillVerified(r: PostReceipt): void {
  if (!['verified', 'complete'].includes(r.stage) || !r.url) throw Error('Only a verified post may be backfilled.');
  const url = canonicalPostUrl(r.url);
  // Plan every edit before writing. If interrupted after one file, retry recognises that exact append.
  const changes = r.manifest.sources.map(source => {
    const current = fs.readFileSync(source.file, 'utf8');
    const line = `> ${source.label}：${url}`;
    const occurrences = current.split(/\r?\n/).filter(value => value === line).length;
    if (occurrences > 1) throw Error('Duplicate publication links in backfill source; reconcile before completing.');
    if (occurrences === 1) return { file: source.file, current, append: '' };
    const suffix = `${current.endsWith('\n') ? '\n' : '\n\n'}${line}\n`;
    if (sha256(current) === source.sha256) return { file: source.file, current, append: suffix };
    throw Error(`Published, but backfill source changed: ${source.file}. Merge the verified URL manually; do not repost.`);
  });
  for (const change of changes) {
    if (fs.readFileSync(change.file, 'utf8') !== change.current) throw Error('Backfill source changed during verification; preserve edits and retry only backfill.');
    // Append only: never rewrite a whole note or discard concurrently added text.
    if (change.append) fs.appendFileSync(change.file, change.append);
  }
}

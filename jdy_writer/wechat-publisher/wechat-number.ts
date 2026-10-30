import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validPublication } from './wechat-draft.ts';

type Evidence = { source: string; number: number };
export function counterNumber(raw: string): number {
  if (!/^[1-9]\d*\s*$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) >= Number.MAX_SAFE_INTEGER) throw new Error('Invalid article counter; numbering stopped');
  return Number(raw);
}
export function receiptNumbers(directory: string): Evidence[] {
  if (!fs.existsSync(directory)) return [];
  const evidence: Evidence[] = [];
  const assigned = new Map<number, string>();
  for (const name of fs.readdirSync(directory).sort()) {
    if (!name.endsWith('.json') || name.includes('.before-')) continue;
    const file = path.join(directory, name);
    if (fs.lstatSync(file).isSymbolicLink()) throw new Error('Receipt symlink; numbering stopped');
    let receipt: any;
    try { receipt = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { throw new Error('Unreadable active receipt; numbering stopped'); }
    if (receipt.version !== 1 || typeof receipt.identity !== 'string' || !receipt.uploads || typeof receipt.uploads !== 'object' || Array.isArray(receipt.uploads)) throw new Error('Invalid active receipt; numbering stopped');
    if (receipt.publication && !validPublication(receipt)) throw new Error('Invalid publication confirmation; numbering stopped');
    if (receipt.publication && receipt.pending) throw new Error('Published receipt still has an unresolved write; reconcile first');
    if (receipt.pending && !receipt.mediaId) throw new Error('Unresolved draft creation; inspect the draft box before assigning a new number');
    if (!receipt.mediaId && !receipt.article && !receipt.publication) continue; // Image-cache-only receipt.
    if (typeof receipt.mediaId !== 'string' || !receipt.mediaId.trim()) throw new Error('Incomplete draft receipt; numbering stopped');
    if (receipt.pending && (!['create', 'update'].includes(receipt.pending.operation) || typeof receipt.pending.article?.title !== 'string')) throw new Error('Malformed pending write; numbering stopped');
    const titles = [receipt.article?.title, receipt.pending?.article.title, receipt.publication?.title].filter(t => t !== undefined);
    if (!titles.length || titles.some(t => typeof t !== 'string')) throw new Error('Incomplete draft receipt; numbering stopped');
    for (const title of new Set<string>(titles)) {
      const match = /^(\d+)\.\s+/.exec(title);
      if (!match) throw new Error('Known draft has no article number; reconcile numbering first');
      const number = counterNumber(match[1]!);
      if (assigned.has(number) && assigned.get(number) !== receipt.mediaId) throw new Error('Duplicate article number in different drafts; reconcile first');
      assigned.set(number, receipt.mediaId);
      evidence.push({ source: `${receipt.pending ? 'receipt-known-draft' : 'receipt'}:${name}`, number });
    }
  }
  return evidence;
}
export function nextArticleNumber(evidence: Evidence[]) {
  if (!evidence.length) throw new Error('No numbering evidence');
  const maximum = Math.max(...evidence.map(item => counterNumber(String(item.number))));
  return { next: maximum + 1, reservedThrough: maximum, evidence, reservation: false };
}
type Run = (program: string, args: string[], cwd: string) => string;
const run: Run = (program, args, cwd) => {
  try { return execFileSync(program, args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 8 * 1024 * 1024, timeout: 30_000 }); }
  catch { throw new Error(`${program} numbering evidence unavailable; stopped without guessing`); }
};
export function inspectArticleNumbers(repo: string, receipts: string, execute: Run = run) {
  const relative = 'jdy_writer/article-counter.txt';
  execute('git', ['fetch', 'origin', 'main'], repo);
  const local = counterNumber(fs.readFileSync(path.join(repo, relative), 'utf8'));
  const remote = counterNumber(execute('git', ['show', `origin/main:${relative}`], repo));
  const url = execute('git', ['remote', 'get-url', 'origin'], repo).trim();
  const match = /^(?:git@github\.com:|https:\/\/github\.com\/)([\w.-]+\/[\w.-]+?)(?:\.git)?$/.exec(url);
  if (!match) throw new Error('Expected configured GitHub origin; numbering stopped');
  const slug = match[1]!;
  const pages = JSON.parse(execute('gh', ['api', '--paginate', '--slurp', `repos/${slug}/pulls?state=open&per_page=100`], repo));
  if (!Array.isArray(pages) || pages.some(p => !Array.isArray(p))) throw new Error('Invalid open PR evidence');
  const evidence: Evidence[] = [{ source: 'local-counter', number: local }, { source: 'origin/main', number: remote }, ...receiptNumbers(receipts)];
  for (const pr of pages.flat()) {
    if (!Number.isSafeInteger(pr.number) || !/^[a-f0-9]{40}$/.test(pr.head?.sha || '')) throw new Error('Invalid PR identity');
    const filePages = JSON.parse(execute('gh', ['api', '--paginate', '--slurp', `repos/${slug}/pulls/${pr.number}/files?per_page=100`], repo));
    if (!Array.isArray(filePages) || filePages.some(p => !Array.isArray(p))) throw new Error('Invalid PR file evidence');
    if (filePages.flat().length >= 3000) throw new Error('PR file listing may be truncated; numbering stopped');
    const file = filePages.flat().find(f => f.filename === relative || f.previous_filename === relative);
    if (!file) continue;
    if (file.filename !== relative || !['added', 'modified'].includes(file.status)) throw new Error('Counter removed or renamed in an open PR; reconcile first');
    // Fetch at the inspected immutable head, never a moving branch name.
    const content = JSON.parse(execute('gh', ['api', `repos/${slug}/contents/${relative}?ref=${pr.head.sha}`], repo));
    if (content.encoding !== 'base64' || typeof content.content !== 'string') throw new Error('Invalid PR counter evidence');
    evidence.push({ source: `PR#${pr.number}@${pr.head.sha.slice(0, 7)}`, number: counterNumber(Buffer.from(content.content, 'base64').toString('utf8')) });
    const current = JSON.parse(execute('gh', ['api', `repos/${slug}/pulls/${pr.number}`], repo));
    if (current.state !== 'open' || current.head?.sha !== pr.head.sha) throw new Error('PR changed during numbering check; retry evidence collection');
  }
  return nextArticleNumber(evidence);
}
if (import.meta.url === `file://${process.argv[1]}` || (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]))) {
  try {
    const argv = process.argv.slice(2);
    if (argv.includes('--help')) {
      console.log('Usage: bun wechat-number.ts [--repo <skills repo>] [--receipts-dir <private active receipts>]\nChecks main/local counter, confirmed receipts and open counter PRs. Read-only planning; does not reserve a number or access WeChat credentials. Coordinate parallel uploads and recheck immediately before creation.');
    } else {
      let repo = path.resolve(import.meta.dir, '../..'), receipts = path.join(os.homedir(), '.local/state/jdy-writer/drafts');
      for (let i = 0; i < argv.length; i++) {
        const value = argv[i + 1];
        if (!['--repo', '--receipts-dir'].includes(argv[i]!) || !value || value.startsWith('--')) throw new Error('Invalid numbering arguments');
        if (argv[i] === '--repo') repo = path.resolve(value); else receipts = path.resolve(value);
        i++;
      }
      console.log(JSON.stringify(inspectArticleNumbers(repo, receipts), null, 2));
    }
  } catch (error) { console.error(error instanceof Error ? error.message : 'Numbering check failed'); process.exitCode = 1; }
}

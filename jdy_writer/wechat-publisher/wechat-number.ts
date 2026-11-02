import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { validPublication } from './wechat-draft.ts';

type Evidence = { source: string; number: number };
export function counterNumber(raw: string): number {
  if (!/^[1-9]\d*\s*$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) >= Number.MAX_SAFE_INTEGER) throw new Error('Invalid article counter; numbering stopped');
  return Number(raw);
}
export function receiptNumbers(directory: string): Evidence[] {
  let directoryStat: fs.Stats;
  try { directoryStat = fs.lstatSync(directory); }
  catch { throw new Error('Active receipt directory unavailable; restore or explicitly initialize it before numbering'); }
  if (!directoryStat.isDirectory()) throw new Error('Active receipts must use a real directory; numbering stopped');
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
export function inspectArticleNumbers(counterFile: string, receipts: string) {
  const evidence: Evidence[] = [];
  let counterStat: fs.Stats | undefined;
  try { counterStat = fs.lstatSync(counterFile); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  if (counterStat) {
    if (!counterStat.isFile()) throw new Error('Counter must be a regular file; numbering stopped');
    evidence.push({ source: 'private-counter', number: counterNumber(fs.readFileSync(counterFile, 'utf8')) });
  }
  evidence.push(...receiptNumbers(receipts));
  return nextArticleNumber(evidence);
}
if (import.meta.url === `file://${process.argv[1]}` || (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]))) {
  try {
    const argv = process.argv.slice(2);
    if (argv.includes('--help')) {
      console.log('Usage: bun wechat-number.ts [--counter-file <private baseline>] [--receipts-dir <private active receipts>]\nChecks private baseline and active receipts without Git or network access. Read-only planning; does not reserve a number or access WeChat credentials. Coordinate parallel uploads and recheck immediately before creation.');
    } else {
      let counterFile = path.join(os.homedir(), '.local/state/jdy-writer/article-counter.txt'), receipts = path.join(os.homedir(), '.local/state/jdy-writer/drafts');
      for (let i = 0; i < argv.length; i++) {
        const value = argv[i + 1];
        if (!['--counter-file', '--receipts-dir'].includes(argv[i]!) || !value || value.startsWith('--')) throw new Error('Invalid numbering arguments');
        if (argv[i] === '--counter-file') counterFile = path.resolve(value); else receipts = path.resolve(value);
        i++;
      }
      console.log(JSON.stringify(inspectArticleNumbers(counterFile, receipts), null, 2));
    }
  } catch (error) { console.error(error instanceof Error ? error.message : 'Numbering check failed'); process.exitCode = 1; }
}

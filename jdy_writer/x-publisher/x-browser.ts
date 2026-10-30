import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import {
  CHROME_CANDIDATES_FULL, CdpConnection, findExistingChromeDebugPort,
  getDefaultProfileDir, launchChrome, sleep, waitForChromeDebugPort,
} from './x-utils.js';
import {
  CN_ACCOUNT, readPostText, assertComposerReady, backfillVerified, bindReceipt, buildManifest, canonicalPostUrl,
  loadReceipt, assertCanSubmit, planPostPage, verificationUrl, sha256, withReceiptLock, writeReceipt, type PostReceipt, type PublishedSnapshot,
} from './x-post-state.ts';
import { runPostFlow, type PostDriver } from './x-post-flow.ts';
import { loadPrepared } from '../publishing/prepare-x.ts';

interface XBrowserOptions {
  text?: string;
  images?: string[];
  submit?: boolean;
  timeoutMs?: number;
  profileDir?: string;
  chromePath?: string;
  stateFile?: string;
  sources?: string[];
  verifyOnly?: boolean;
  publishedUrl?: string;
}

// All inspection stays in the visible page. No cookie or session-token extraction.
const editorSnapshot = `(()=>{
 const dialog=document.querySelector('[role="dialog"]');
 const editor=dialog?.querySelector('[data-testid="tweetTextarea_0"]');
 const images=[...dialog?.querySelectorAll('[data-testid="attachments"] img')||[]];
 const button=dialog?.querySelector('[data-testid="tweetButton"]');
 return {url:location.href,account:document.querySelector('[data-testid="AppTabBar_Profile_Link"]')?.getAttribute('href'),
 editor:!!editor,text:editor?.innerText||'',count:images.length,loaded:images.every(i=>i.complete&&i.naturalWidth>0),
 enabled:!!button&&!button.disabled&&button.getAttribute('aria-disabled')!=='true'};
})()`;

export async function postToX(options: XBrowserOptions): Promise<{ stateFile: string; stage: string; url?: string }> {
  const text = (options.text || '').replace(/\r\n/g, '\n');
  const profile = path.resolve(options.profileDir || getDefaultProfileDir());
  const verifyOnly = !!options.verifyOnly;
  if (options.submit && !options.stateFile) throw Error('--submit requires an explicit --state-file reused from composition.');
  if (verifyOnly && !options.stateFile) throw Error('--verify-only requires --state-file.');
  if (verifyOnly && (options.submit || options.text !== undefined || options.images?.length || options.sources?.length)) throw Error('--verify-only accepts a receipt, not new publication inputs.');
  if (options.publishedUrl && !verifyOnly) throw Error('--published-url requires --verify-only.');
  const manifest = verifyOnly ? undefined : buildManifest(text, options.images || [], profile, options.sources || []);
  const stateFile = path.resolve(options.stateFile || path.join(os.homedir(), '.local/state/jdy-writer/x', `${sha256(JSON.stringify(manifest))}.json`));
  return withReceiptLock(stateFile, async () => {
    const r = verifyOnly ? loadReceipt(stateFile) : bindReceipt(stateFile, manifest!);
    if (options.profileDir && path.resolve(options.profileDir) !== r.manifest.profile) throw Error('Profile differs from receipt.');
    if (options.submit) assertCanSubmit(r);
    const verifyUrl = verificationUrl(r, verifyOnly, options.publishedUrl);
    const save = () => writeReceipt(stateFile, r);
    save();
    const browser = await connectBrowser(r, options.chromePath, verifyUrl);
    try {
      save();
      const driver = makeDriver(browser.cdp, browser.sessionId, r, text, options.timeoutMs || 30_000, stateFile, save);
      await runPostFlow(r, driver, save, { submit: !!options.submit, verifyOnly, publishedUrl: options.publishedUrl });
      if (r.stage === 'verified') {
        backfillVerified(r);
        r.stage = 'complete'; save();
      }
      const result = { stateFile, stage: r.stage, url: r.url };
      console.log(JSON.stringify(result));
      return result;
    } finally {
      browser.cdp.close();
      // Keep login/drafts and uncertain outcomes available; never kill an existing browser.
      browser.chrome?.unref();
    }
  });
}

async function connectBrowser(r: PostReceipt, chromePath?: string, verifyUrl?: string) {
  fs.mkdirSync(r.manifest.profile, { recursive: true });
  let port = await findExistingChromeDebugPort(r.manifest.profile);
  let chrome: Awaited<ReturnType<typeof launchChrome>>['chrome'] | undefined;
  if (port === null) {
    if (!verifyUrl && r.targetId && r.stage !== 'waiting_login') throw Error('Original composer is unavailable. Inspect the account before attempting recovery; do not recreate and repost.');
    const launch = await launchChrome('about:blank', r.manifest.profile, CHROME_CANDIDATES_FULL, chromePath);
    port = launch.port; chrome = launch.chrome;
    chrome.unref();
  }
  const cdp = await CdpConnection.connect(await waitForChromeDebugPort(port, 30_000), 30_000, { defaultTimeoutMs: 15_000 });
  try {
    const version = await cdp.send<{ product: string; userAgent: string }>('Browser.getVersion');
    if (!version.product.startsWith('Chrome/') || /Edg\//.test(version.userAgent)) throw Error('Expected Google Chrome for the dedicated X profile.');
    const { targetInfos } = await cdp.send<{ targetInfos: { targetId: string; url: string }[] }>('Target.getTargets');
    const page = planPostPage(r, targetInfos, verifyUrl);
    let targetId = page.targetId;
    if (!targetId) {
      ({ targetId } = await cdp.send<{ targetId: string }>('Target.createTarget', { url: page.url }));
    }
    const { sessionId } = await cdp.send<{ sessionId: string }>('Target.attachToTarget', { targetId, flatten: true });
    await cdp.send('Runtime.enable', {}, { sessionId });
    await cdp.send('DOM.enable', {}, { sessionId });
    await cdp.send('Target.activateTarget', { targetId });
    r.targetId = targetId; r.port = port;
    return { cdp, sessionId, chrome };
  } catch (error) { cdp.close(); throw error; }
}

export function makeDriver(cdp: CdpConnection, sessionId: string, receipt: PostReceipt, text: string, timeoutMs: number, stateFile: string, save: () => void): PostDriver {
  const evaluate = async <T = any>(expression: string): Promise<T> => {
    const result = await cdp.send<any>('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, { sessionId });
    if (result.exceptionDetails) throw Error('X page inspection failed. Inspect the browser; no automatic repost.');
    return result.result.value;
  };
  const poll = async <T>(read: () => Promise<T>, accept: (value: T) => boolean): Promise<T> => {
    const until = Date.now() + timeoutMs;
    do { const value = await read(); if (accept(value)) return value; await sleep(500); } while (Date.now() < until);
    throw Error('Timed out waiting for X. Receipt retained; inspect before resuming.');
  };
  const snapshot = () => evaluate<any>(editorSnapshot);
  const assertComposer = (s: any) => assertComposerReady(receipt, s, text);
  const previewHashes = () => evaluate<string[]>(`(async()=>Promise.all([...document.querySelectorAll('[role="dialog"] [data-testid="attachments"] img')].map(async i=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',await(await fetch(i.src)).arrayBuffer()))].map(b=>b.toString(16).padStart(2,'0')).join(''))))()`);
  const capture = async (suffix: string) => {
    const shot = await cdp.send<{ data: string }>('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, { sessionId });
    fs.writeFileSync(`${stateFile}.${suffix}.png`, Buffer.from(shot.data, 'base64'), { mode: 0o600 });
  };
  return {
    async compose(resume, beforeMutation) {
      // Persist the tab before waiting, so a login interruption resumes the same composer.
      save();
      let s = await snapshot();
      if (/login|onboarding|\/flow\//.test(s.url)) throw Error('Login required in the dedicated Chrome window. Complete login, then rerun the same command and receipt.');
      s = await poll(snapshot, s => s.editor || /login|onboarding|\/flow\//.test(s.url));
      if (!s.editor) throw Error('Login required in the dedicated Chrome window. Rerun with the same receipt after login.');
      if (s.account?.toLowerCase() !== `/${CN_ACCOUNT.toLowerCase()}`) throw Error(`Expected @${CN_ACCOUNT}; account mismatch.`);
      if (!resume) {
        if (s.text.trim() || s.count) throw Error('Existing draft found. Preserve it; do not overwrite or append.');
        beforeMutation();
        await evaluate(`document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]').focus()`);
        if (text) await cdp.send('Input.insertText', { text }, { sessionId });
        if (receipt.manifest.images.length) {
          const { root } = await cdp.send<{ root: { nodeId: number } }>('DOM.getDocument', {}, { sessionId });
          const { nodeId } = await cdp.send<{ nodeId: number }>('DOM.querySelector', { nodeId: root.nodeId, selector: '[role="dialog"] input[data-testid="fileInput"]' }, { sessionId });
          if (!nodeId) throw Error('File input unavailable. No clipboard fallback or silent image skipping.');
          await cdp.send('DOM.setFileInputFiles', { nodeId, files: receipt.manifest.images.map(i => i.file) }, { sessionId });
        }
      }
      s = await poll(snapshot, s => s.count === receipt.manifest.images.length && s.loaded && s.enabled);
      assertComposer(s);
      const hashes = await previewHashes();
      if (receipt.previewHashes && JSON.stringify(hashes) !== JSON.stringify(receipt.previewHashes)) throw Error('Preview images changed or reordered; inspect before publication.');
      receipt.previewHashes = hashes;
      await evaluate(`document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]').scrollIntoView({block:'start'})`);
      await sleep(250); await capture('text');
      if (s.count) {
        await evaluate(`document.querySelector('[role="dialog"] [data-testid="attachments"]').scrollIntoView({block:'center'})`);
        await sleep(250); await capture('media');
      }
    },
    async submit(beforeClick) {
      assertComposer(await snapshot());
      if (JSON.stringify(await previewHashes()) !== JSON.stringify(receipt.previewHashes)) throw Error('Preview media changed before submission.');
      beforeClick();
      await evaluate(`(()=>{const b=document.querySelector('[role="dialog"] [data-testid="tweetButton"]');if(!b||b.disabled)throw Error('Post unavailable');b.click()})()`);
      const url = await poll(
        () => evaluate<string | undefined>(`[...document.querySelectorAll('[data-testid="toast"] a')].map(a=>a.href).find(u=>new RegExp(${JSON.stringify('^https://x[.]com/' + CN_ACCOUNT + '/status/[0-9]+$')}).test(u))`),
        u => !!u,
      );
      return canonicalPostUrl(url!);
    },
    async verify(url) {
      const canonical = canonicalPostUrl(url), stem = new URL(canonical).pathname;
      await cdp.send('Page.navigate', { url: canonical }, { sessionId });
      const read = () => evaluate<PublishedSnapshot>(`(()=>{
        const a=[...document.querySelectorAll('article')].find(a=>a.querySelector('a[href=${JSON.stringify(stem)}] time'));
        const photos=a?[...a.querySelectorAll('a[href^=${JSON.stringify(stem + '/photo/')} ]')]:[];
        return {url:location.href,author:a?.querySelector('[data-testid="User-Name"] a[href="/${CN_ACCOUNT}"]')?'${CN_ACCOUNT}':'',text:(${readPostText.toString()})(a?.querySelector('[data-testid="tweetText"]'),${JSON.stringify(receipt.manifest.links||[])}),photos:photos.map(p=>p.getAttribute('href')),loaded:!!a&&photos.every(p=>p.querySelector('img')?.complete&&p.querySelector('img')?.naturalWidth>0)};
      })()`);
      const result = await poll(read, p => p.author === CN_ACCOUNT && sha256(p.text) === receipt.manifest.textSha256 && p.photos.length === receipt.manifest.images.length && p.loaded);
      await capture('published');
      // X may display four attachments in a horizontal carousel; capture every position.
      for (let i = 0; i < result.photos.length; i++) {
        await evaluate(`document.querySelector('a[href=${JSON.stringify(stem + '/photo/' + (i + 1))}]')?.scrollIntoView({block:'center',inline:'center'})`);
        await sleep(250); await capture(`published-media-${i + 1}`);
      }
      return result;
    },
  };
}

function usage() {
  console.log(`Publish one approved Chinese X post (including long posts), with up to four ordered images.
Default: stable Google Chrome, dedicated x-browser-profile-cn, account @${CN_ACCOUNT}.

bun x-browser.ts --text-file <approved.txt> [--image <local-file> ...] [options]
  --prepared <prepared.json>  Use the checked output from publishing/prepare-x.ts
  --state-file <private.json>  Durable receipt; reuse on login/recovery (default: input hash)
  --source <x-note.md>         Backfill verified URL into X note
  --related-source <note.md>   Also backfill an explicitly selected source note (repeatable)
  --submit                    Publish a prepared receipt after checks (requires --state-file)
  --verify-only               Read official post and recover/backfill; never click Post
  --published-url <url>       With --verify-only, inspect an uncertain/manual publication
  --profile <dir>             Explicit profile override; account check still applies
  --chrome <executable>       Explicit executable override; no silent browser fallback
  --help                      Show help
Missing files, account mismatch, partial text/media, or uncertain submission stop the run.
Preview screenshots are private receipt sidecars. Review them before the --submit run.`);
}
async function main() {
  const options: XBrowserOptions = { images: [], sources: [] };
  const words: string[] = [];
  let textFile: string | undefined;
  let preparedFile: string | undefined;
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]!;
    if (arg === '--help' || arg === '-h') { usage(); return; }
    if (['--submit','--verify-only'].includes(arg)) { if(arg==='--submit')options.submit=true;else options.verifyOnly=true;continue; }
    if (['--image','--state-file','--source','--related-source','--profile','--chrome','--published-url','--text-file','--prepared'].includes(arg)) {
      const value = args[++i]; if (!value || value.startsWith('--')) throw Error(`Missing value for ${arg}`);
      if(arg==='--image') options.images!.push(value);
      else if(arg==='--source') { if(options.sources!.length)throw Error('--source must precede --related-source');options.sources!.push(value); }
      else if(arg==='--related-source') { if(!options.sources!.length)throw Error('--related-source requires --source');options.sources!.push(value); }
      else if(arg==='--prepared') preparedFile=value;
      else if(arg==='--text-file') textFile=value;
      else if(arg==='--state-file') options.stateFile=value;
      else if(arg==='--profile') options.profileDir=value;
      else if(arg==='--chrome') options.chromePath=value;
      else options.publishedUrl=value;
    } else if(arg.startsWith('-')) throw Error(`Unknown option: ${arg}`);
    else words.push(arg);
  }
  if (preparedFile) {
    if(textFile||words.length||options.images!.length||options.sources!.length||options.verifyOnly)throw Error('--prepared cannot mix with raw content inputs or --verify-only.');
    const prepared=loadPrepared(preparedFile);options.text=prepared.text;options.images=prepared.images;options.sources=prepared.sources;
  }
  if (textFile && words.length) throw Error('Use either positional text or --text-file.');
  if (textFile) options.text=fs.readFileSync(textFile,'utf8');
  else if(words.length) options.text=words.join(' ');
  await postToX(options);
}
if (import.meta.main) main().catch(error => { console.error(`Error: ${error.message}`); process.exitCode=1; });

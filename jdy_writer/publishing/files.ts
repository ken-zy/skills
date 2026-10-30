import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
export const sha = (input: string | Buffer) => createHash('sha256').update(input).digest('hex');
function actualPath(file:string):string {
  let parent=path.resolve(file);const missing:string[]=[];
  while(!fs.existsSync(parent)){missing.unshift(path.basename(parent));const next=path.dirname(parent);if(next===parent)break;parent=next;}
  return path.join(fs.realpathSync(parent),...missing);
}
export function privateLocation(file: string) {
  for(let dir=path.dirname(actualPath(file));path.dirname(dir)!==dir;dir=path.dirname(dir)) {
    if(fs.existsSync(path.join(dir,'.obsidian'))||fs.existsSync(path.join(dir,'60_Output')))throw Error('Private receipts and artifacts must remain outside the vault.');
  }
}
export function savePrivate(file: string, value: unknown) {
  privateLocation(file);
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
  fs.renameSync(temp, file); fs.chmodSync(file, 0o600);
}
export function outsideNotes(output: string, source: string) {
  let vault = path.dirname(actualPath(source));
  for (let dir = vault; path.dirname(dir) !== dir; dir = path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, '.obsidian')) || fs.existsSync(path.join(dir, '60_Output'))) { vault = dir; break; }
  }
  const relative = path.relative(vault, actualPath(output));
  if (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative)) throw Error('Private outputs must be outside the source vault/notes directory.');
}
export function addVerifiedLink(source: string, expectedHash: string, url: string) {
  const text = fs.readFileSync(source, 'utf8'), line = `> 发布链接：${url}`;
  if (text.split(/\r?\n/).includes(line)) return;
  if (sha(text) !== expectedHash) throw Error('Source changed: merge the verified link manually; no source body was overwritten.');
  fs.appendFileSync(source, `${text.endsWith('\n') ? '\n' : '\n\n'}${line}\n`);
}
export async function publicBytes(url: string, hosts: string[], maxBytes: number): Promise<Buffer> {
  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' || !hosts.includes(parsed.hostname) || parsed.username || parsed.password || parsed.port) throw Error('Unsupported public source URL.');
  const response = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(30000), headers: { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-CN,zh;q=0.9' } });
  if(response.status>=300&&response.status<400)throw Error('Public source redirected (login/captcha may be required); inspect the official page. No redirect or browser bypass was attempted.');
  if (!response.ok || !response.body) throw Error(`Public source HTTP ${response.status}.`);
  const chunks: Buffer[] = []; let size = 0;
  const reader = response.body.getReader();
  try { for (;;) { const {done,value}=await reader.read(); if(done)break;size+=value.length;if(size>maxBytes)throw Error('Public source exceeds size limit.');chunks.push(Buffer.from(value)); } }
  finally { await reader.cancel(); }
  return Buffer.concat(chunks);
}
export function args(values: string[], flags: string[], switches: string[] = []) {
  const result: Record<string,string|boolean> = {};
  for(let i=0;i<values.length;i++) {
    const key=values[i]!;
    if (switches.includes(key)) { result[key]=true;continue; }
    if (!flags.includes(key) || !values[i+1] || values[i+1]!.startsWith('--') || result[key] !== undefined) throw Error(`Invalid or duplicate argument: ${key}`);
    result[key]=values[++i]!;
  }
  return result;
}

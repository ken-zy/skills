// Local installer: prepare stages private candidates; apply requires review first.
// Never print configuration contents, controller responses, or core diagnostics.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { isDeepStrictEqual } from "node:util";
import { type Entry, sha, fileSha, save, replaceFileBatch } from "./wechat-install-files.ts";

const appDir = path.join(os.homedir(), "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev");
const installedSkill = path.join(os.homedir(), "Documents/skills/jdy_writer");
const stateRoot = path.join(os.homedir(), ".local/state/jdy-writer/fixed-egress");
const socket = "/tmp/verge/verge-mihomo.sock";
let phase = "start";
const listener = { name: "wechat-publisher", type: "http", listen: "127.0.0.1", port: 17993, proxy: "固定美国" };
type Manifest = { entries: Entry[]; profileUid: string; profileIndexSha: string; selector: string; runtime: string; baseline: unknown; applied?: boolean };

async function controller(endpoint: string, body?: unknown) {
  const response = await fetch(`http://localhost${endpoint}`, {
    unix: socket, method: body === undefined ? "GET" : "PUT",
    headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error("Local controller operation failed");
  return response.status === 204 ? null : response.json();
}

function relevantState(config: any) {
  return Object.fromEntries(["mode", "port", "socks-port", "redir-port", "tproxy-port", "mixed-port", "allow-lan", "bind-address", "ipv6", "tun", "interface-name"].map(k => [k, config[k]]));
}

function candidateConfig(raw: string) {
  const before = Bun.YAML.parse(raw) as any;
  if (!before.proxies?.some((x: any) => x.name === listener.proxy)) throw new Error("Required fixed node is missing");
  if (!Array.isArray(before.listeners) || before.listeners.some((x: any) => x.name === listener.name || x.port === listener.port)) throw new Error("Listener name or port conflicts");
  let candidate: string;
  if (raw.trimStart().startsWith("{")) {
    // Clash local profiles may be JSON, which is also valid YAML. Insert only
    // the new array member; retain every pre-existing byte and private field.
    const match = /"listeners"\s*:\s*\[/.exec(raw);
    if (!match) throw new Error("Unsupported listeners representation");
    const at = match.index + match[0].length;
    candidate = raw.slice(0, at) + "\n    " + JSON.stringify(listener) + "," + raw.slice(at);
  } else {
    const lines = raw.split("\n");
    const index = lines.findIndex(x => /^(?:"listeners"|'listeners'|listeners):[ \t]*(?:#.*)?\r?$/.test(x));
    if (index < 0) throw new Error("Unsupported listeners representation");
    const nextKey = lines.findIndex((x, i) => i > index && /^[A-Za-z_][\w-]*:/.test(x));
    const end = nextKey < 0 ? lines.length : nextKey;
    const item = lines.slice(index + 1, end).find(x => /^\s*-\s/.test(x));
    if (!item) throw new Error("Cannot locate existing listener indentation");
    const indent = item.match(/^(\s*)-/)![1];
    const additions = [`${indent}- name: ${listener.name}`, `${indent}  type: http`, `${indent}  listen: 127.0.0.1`, `${indent}  port: 17993`, `${indent}  proxy: 固定美国`];
    lines.splice(index + 1, 0, ...additions);
    candidate = lines.join("\n");
  }
  const after = Bun.YAML.parse(candidate) as any;
  if (!isDeepStrictEqual(after.listeners[0], listener)) throw new Error("Listener candidate differs");
  after.listeners.shift();
  if (!isDeepStrictEqual(before, after)) throw new Error("Candidate changes unrelated configuration");
  return candidate;
}

function ensureFreePort() {
  const server = Bun.serve({ hostname: "127.0.0.1", port: listener.port, fetch: () => new Response() });
  server.stop(true);
}

async function prepare() {
  phase = "check-port";
  ensureFreePort();
  const indexFile = path.join(appDir, "profiles.yaml");
  const indexRaw = fs.readFileSync(indexFile, "utf8");
  const index = Bun.YAML.parse(indexRaw) as any;
  const current = index.items?.find((x: any) => x.uid === index.current && x.type === "local");
  if (!current || path.basename(current.file) !== current.file) throw new Error("Active local profile unavailable");
  const dir = fs.mkdtempSync(path.join((fs.mkdirSync(stateRoot, { recursive: true, mode: 0o700 }), stateRoot), "install-"));
  fs.chmodSync(dir, 0o700);
  const entries: Entry[] = [];
  function stage(target: string, data: string | Buffer, source?: string) {
    const n = entries.length;
    const existed = fs.existsSync(target);
    const previous = existed ? fs.readFileSync(target) : null;
    const candidate = path.join(dir, `${n}.candidate`), backup = path.join(dir, `${n}.backup`);
    save(candidate, data);
    if (previous) save(backup, previous);
    entries.push({ target, source, existed, before: previous ? sha(previous) : null, after: sha(data), candidate, backup,
      mode: existed ? fs.statSync(target).mode & 0o777 : 0o600 });
  }
  const profile = path.join(appDir, "profiles", current.file);
  const runtime = path.join(appDir, "clash-verge.yaml");
  phase = "stage-profile";
  stage(profile, candidateConfig(fs.readFileSync(profile, "utf8")));
  phase = "stage-runtime";
  stage(runtime, candidateConfig(fs.readFileSync(runtime, "utf8")));
  phase = "validate-core";
  const check = Bun.spawnSync(["/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo", "-t", "-d", appDir, "-f", entries[1]!.candidate]);
  save(path.join(dir, "core-check.log"), Buffer.concat([check.stdout, check.stderr]));
  if (check.exitCode !== 0) throw new Error("Core candidate validation failed; private diagnostic retained");
  phase = "stage-publisher";
  for (const name of ["wechat-network.ts", "wechat-proxy-worker.ts", "wechat-api.ts"]) {
    const source = path.join(import.meta.dir, name);
    stage(path.join(installedSkill, "wechat-publisher", name), fs.readFileSync(source), source);
  }
  const sourceDoc = path.resolve(import.meta.dir, "../references/workflow-wechat.md");
  stage(path.join(installedSkill, "references/workflow-wechat.md"), fs.readFileSync(sourceDoc), sourceDoc);
  stage(path.join(os.homedir(), ".config/jdy-writer/wechat-network.json"), JSON.stringify({ proxy: "http://127.0.0.1:17993", expectedEgressIp: "95.169.12.176" }, null, 2) + "\n");
  phase = "snapshot-controller";
  const selected = await controller(`/proxies/${encodeURIComponent("节点选择")}`);
  const manifest: Manifest = { entries, profileUid: index.current, profileIndexSha: sha(indexRaw), selector: selected.now,
    runtime, baseline: relevantState(await controller("/configs")) };
  save(path.join(dir, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(JSON.stringify({ prepared: true, stateDir: dir, newListener: listener, originalSelector: selected.now,
    coreConfigValid: true, unrelatedConfigChanged: false, installFiles: entries.length }));
}

async function checkContext(manifest: Manifest) {
  if (fileSha(path.join(appDir, "profiles.yaml")) !== manifest.profileIndexSha) throw new Error("Profile metadata changed; operation stopped");
  const selected = await controller(`/proxies/${encodeURIComponent("节点选择")}`);
  const live = relevantState(await controller("/configs"));
  // Do not force a user's subsequent selection/profile/mode back to our snapshot.
  if (selected.now !== manifest.selector || !isDeepStrictEqual(live, manifest.baseline)) throw new Error("Live state changed; operation stopped");
  // Check disk identity again after both controller awaits.
  if (fileSha(path.join(appDir, "profiles.yaml")) !== manifest.profileIndexSha) throw new Error("Profile metadata changed during check");
}

async function rollback(dir: string, manifest: Manifest, entries = manifest.entries, reload = true) {
  phase = "rollback-check-and-restore";
  await replaceFileBatch([...entries].reverse(), "rollback", () => checkContext(manifest));
  if (reload) await controller("/configs?force=true", { path: manifest.runtime });
  await checkContext(manifest);
  manifest.applied = false;
  save(path.join(dir, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log("Rollback verified");
}

async function apply(dir: string, manifest: Manifest) {
  if (manifest.applied) throw new Error("This installation is already applied");
  if (fileSha(path.join(appDir, "profiles.yaml")) !== manifest.profileIndexSha) throw new Error("Active profile metadata changed; prepare again");
  ensureFreePort();
  const written: Entry[] = [];
  let reloadAttempted = false;
  try {
    phase = "apply-check-and-write";
    await replaceFileBatch(manifest.entries, "apply", () => checkContext(manifest), written);
    await checkContext(manifest);
    phase = "reload-and-verify";
    reloadAttempted = true;
    await controller("/configs?force=true", { path: manifest.runtime });
    await checkContext(manifest);
    const network = await import(path.join(installedSkill, "wechat-publisher/wechat-network.ts"));
    const ip = await network.verifyWechatEgress(network.loadWechatNetworkConfig());
    manifest.applied = true;
    save(path.join(dir, "manifest.json"), JSON.stringify(manifest, null, 2));
    console.log(JSON.stringify({ applied: true, verifiedEgress: ip, selector: manifest.selector, unrelatedConfigChanged: false }));
  } catch {
    if (written.length) await rollback(dir, manifest, written, reloadAttempted);
    throw new Error("Activation failed; installation rolled back");
  }
}

try {
  const [action, dir] = process.argv.slice(2);
  if (action === "prepare") await prepare();
  else if ((action === "apply" || action === "rollback") && dir && path.dirname(dir) === stateRoot) {
    const manifest = JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8")) as Manifest;
    if (action === "apply") await apply(dir, manifest); else await rollback(dir, manifest);
  } else throw new Error("Usage: wechat-egress-setup.ts prepare | apply STATE_DIR | rollback STATE_DIR");
} catch (error) {
  fs.mkdirSync(stateRoot, { recursive: true, mode: 0o700 });
  save(path.join(stateRoot, "last-error.log"), String(error));
  console.error(`Fixed-egress setup failed at ${phase}; private diagnostics retained, configuration contents withheld`);
  process.exitCode = 1;
}

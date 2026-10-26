import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

export type Entry = { target: string; source?: string; existed: boolean; before: string | null; after: string; candidate: string; backup: string; mode: number };
export const sha = (bytes: string | Buffer) => createHash("sha256").update(bytes).digest("hex");
export const fileSha = (file: string) => fs.existsSync(file) ? sha(fs.readFileSync(file)) : null;

export function save(file: string, data: string | Buffer, mode = 0o600) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, data, { mode });
  fs.chmodSync(tmp, mode);
  fs.renameSync(tmp, file);
}

// The final context await happens BEFORE the whole-batch filesystem preflight.
// No awaits occur between that preflight and the synchronous replacements.
export async function replaceFileBatch(entries: Entry[], direction: "apply" | "rollback", checkContext: () => Promise<void>, written: Entry[] = []) {
  await checkContext();
  const current = new Map<string, string | null>();
  for (const entry of entries) {
    const digest = fileSha(entry.target);
    current.set(entry.target, digest);
    if (direction === "apply") {
      if (digest !== entry.before || fileSha(entry.candidate) !== entry.after ||
          (entry.source && fileSha(entry.source) !== entry.after)) throw new Error("Concurrent file change; prepare again");
    } else {
      if (digest !== entry.before && digest !== entry.after) throw new Error("Concurrent change; rollback stopped before modifying files");
      if (entry.existed && fileSha(entry.backup) !== entry.before) throw new Error("Backup checksum mismatch");
    }
  }
  for (const entry of entries) {
    if (fileSha(entry.target) !== current.get(entry.target)) throw new Error("Concurrent change at replacement");
    if (direction === "rollback" && current.get(entry.target) === entry.before) continue;
    const input = direction === "apply" ? entry.candidate : entry.backup;
    const expected = direction === "apply" ? entry.after : entry.before;
    if (direction === "rollback" && !entry.existed) fs.unlinkSync(entry.target);
    else {
      const bytes = fs.readFileSync(input);
      if (sha(bytes) !== expected) throw new Error("Replacement content changed");
      save(entry.target, bytes, entry.mode);
    }
    written.push(entry);
  }
}


// Keep installation and startup verification tied to the CLI's runtime closure.
export const PUBLISHER_INSTALL_FILES = ["wechat-network.ts", "wechat-proxy-worker.ts", "wechat-draft.ts", "wechat-api.ts"] as const;

export function verifyInstalledPublisher(directory: string) {
  const result = Bun.spawnSync([process.execPath, path.join(directory, "wechat-api.ts"), "--help"], {
    cwd: directory, stdin: "ignore", stdout: "pipe", stderr: "pipe", timeout: 15_000,
  });
  // --help loads the runtime modules but returns before configuration or credentials.
  // Avoid forwarding startup diagnostics: an installation path may be private.
  if (result.exitCode !== 0) throw new Error("Installed publisher startup check failed");
}

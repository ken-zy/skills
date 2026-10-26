import { test, expect } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { sha, replaceFileBatch, PUBLISHER_INSTALL_FILES, verifyInstalledPublisher, type Entry } from "./wechat-install-files.ts";

function fixture() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-install-test-"));
  const entries: Entry[] = [0, 1].map(i => {
    const target = path.join(dir, `target-${i}`), candidate = path.join(dir, `candidate-${i}`), backup = path.join(dir, `backup-${i}`);
    fs.writeFileSync(target, `before-${i}`); fs.writeFileSync(backup, `before-${i}`); fs.writeFileSync(candidate, `after-${i}`);
    return { target, candidate, backup, existed: true, before: sha(`before-${i}`), after: sha(`after-${i}`), mode: 0o600 };
  });
  return { dir, entries, cleanup: () => fs.rmSync(dir, { recursive: true }) };
}

test("apply rechecks files after the asynchronous controller check and writes nothing on conflict", async () => {
  const f = fixture(), written: Entry[] = [];
  try {
    await expect(replaceFileBatch(f.entries, "apply", async () => {
      await Promise.resolve();
      fs.writeFileSync(f.entries[1]!.target, "other task saved during controller request");
    }, written)).rejects.toThrow("Concurrent file change");
    expect(written).toHaveLength(0);
    expect(fs.readFileSync(f.entries[0]!.target, "utf8")).toBe("before-0");
    expect(fs.readFileSync(f.entries[1]!.target, "utf8")).toContain("other task");
  } finally { f.cleanup(); }
});

test("rollback scans the whole batch before restoring any earlier file", async () => {
  const f = fixture();
  try {
    await replaceFileBatch(f.entries, "apply", async () => {});
    fs.writeFileSync(f.entries[1]!.target, "other task saved after install");
    await expect(replaceFileBatch(f.entries, "rollback", async () => {})).rejects.toThrow("rollback stopped before modifying files");
    expect(fs.readFileSync(f.entries[0]!.target, "utf8")).toBe("after-0");
    expect(fs.readFileSync(f.entries[1]!.target, "utf8")).toBe("other task saved after install");
  } finally { f.cleanup(); }
});

test("changed selector or profile rejects rollback before file restoration", async () => {
  const f = fixture();
  try {
    await replaceFileBatch(f.entries, "apply", async () => {});
    for (const state of ["selector changed", "profile changed"]) {
      const written: Entry[] = [];
      await expect(replaceFileBatch(f.entries, "rollback", async () => { throw new Error(state); }, written)).rejects.toThrow(state);
      expect(written).toHaveLength(0);
      expect(fs.readFileSync(f.entries[0]!.target, "utf8")).toBe("after-0");
    }
  } finally { f.cleanup(); }
});

test("backup integrity is checked for the entire rollback batch first", async () => {
  const f = fixture();
  try {
    await replaceFileBatch(f.entries, "apply", async () => {});
    fs.writeFileSync(f.entries[1]!.backup, "bad backup");
    await expect(replaceFileBatch(f.entries, "rollback", async () => {})).rejects.toThrow("Backup checksum mismatch");
    expect(fs.readFileSync(f.entries[0]!.target, "utf8")).toBe("after-0");
  } finally { f.cleanup(); }
});

test("round trip restores existing content and removes only a matching newly installed file", async () => {
  const f = fixture();
  try {
    fs.unlinkSync(f.entries[1]!.target);
    f.entries[1]!.before = null; f.entries[1]!.existed = false;
    const written: Entry[] = [];
    await replaceFileBatch(f.entries, "apply", async () => {}, written);
    expect(written).toHaveLength(2);
    await replaceFileBatch(f.entries, "rollback", async () => {});
    expect(fs.readFileSync(f.entries[0]!.target, "utf8")).toBe("before-0");
    expect(fs.existsSync(f.entries[1]!.target)).toBe(false);
  } finally { f.cleanup(); }
});

function publisherInstallFixture() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-publisher-install-"));
  const installed = path.join(dir, "installed");
  fs.mkdirSync(installed);
  // Existing publisher support files and dependencies; the runtime bundle must
  // supply every new module itself, as when upgrading an older installation.
  const bundled = new Set<string>(PUBLISHER_INSTALL_FILES);
  for (const name of fs.readdirSync(import.meta.dir)) {
    if (name.endsWith(".ts") && !bundled.has(name)) fs.copyFileSync(path.join(import.meta.dir, name), path.join(installed, name));
  }
  fs.symlinkSync(fs.realpathSync(path.join(import.meta.dir, "node_modules")), path.join(installed, "node_modules"), "dir");
  const legacy = 'console.log("Legacy publisher help");\n';
  fs.writeFileSync(path.join(installed, "wechat-api.ts"), legacy);
  const entries: Entry[] = PUBLISHER_INSTALL_FILES.map((name, index) => {
    const target = path.join(installed, name);
    const source = path.join(import.meta.dir, name);
    const candidate = path.join(dir, `${index}.candidate`);
    const backup = path.join(dir, `${index}.backup`);
    const existed = fs.existsSync(target);
    const previous = existed ? fs.readFileSync(target) : null;
    fs.copyFileSync(source, candidate);
    if (previous) fs.writeFileSync(backup, previous);
    return { target, source, candidate, backup, existed, before: previous ? sha(previous) : null, after: sha(fs.readFileSync(source)), mode: 0o600 };
  });
  return { dir, installed, entries, legacy, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

test("real installed CLI starts after bundle upgrade; rollback restores old CLI and removes new modules", async () => {
  const f = publisherInstallFixture();
  try {
    expect(() => verifyInstalledPublisher(f.installed)).not.toThrow();
    await replaceFileBatch(f.entries, "apply", async () => {});
    expect(() => verifyInstalledPublisher(f.installed)).not.toThrow();
    const help = Bun.spawnSync([process.execPath, path.join(f.installed, "wechat-api.ts"), "--help"]);
    expect(help.exitCode).toBe(0);
    expect(help.stdout.toString()).toContain("--source-url");
    expect(fs.existsSync(path.join(f.installed, "wechat-draft.ts"))).toBe(true);
    await replaceFileBatch([...f.entries].reverse(), "rollback", async () => {});
    expect(fs.readFileSync(path.join(f.installed, "wechat-api.ts"), "utf8")).toBe(f.legacy);
    expect(fs.existsSync(path.join(f.installed, "wechat-draft.ts"))).toBe(false);
    expect(() => verifyInstalledPublisher(f.installed)).not.toThrow();
  } finally { f.cleanup(); }
});

test("startup check detects omitted runtime module; failed installation can roll back before reload", async () => {
  const f = publisherInstallFixture();
  const incomplete = f.entries.filter(entry => path.basename(entry.target) !== "wechat-draft.ts");
  try {
    await replaceFileBatch(incomplete, "apply", async () => {});
    expect(() => verifyInstalledPublisher(f.installed)).toThrow("startup check failed");
    await replaceFileBatch([...incomplete].reverse(), "rollback", async () => {});
    expect(fs.readFileSync(path.join(f.installed, "wechat-api.ts"), "utf8")).toBe(f.legacy);
    expect(() => verifyInstalledPublisher(f.installed)).not.toThrow();
  } finally { f.cleanup(); }
});

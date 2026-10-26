import { test, expect } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { sha, replaceFileBatch, type Entry } from "./wechat-install-files.ts";

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

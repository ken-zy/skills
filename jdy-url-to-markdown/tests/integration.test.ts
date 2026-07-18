import { describe, expect, test, afterAll } from "bun:test";
import { existsSync, readFileSync, unlinkSync, rmdirSync } from "fs";

const OUTPUT_PATH = "/tmp/jdy-url-to-markdown-test/test-output.md";
const PROJECT_DIR = import.meta.dir.replace("/tests", "");

describe("end-to-end Level 1 fetch", () => {
  test("fetches Wikipedia article via Level 1", async () => {
    try { unlinkSync(OUTPUT_PATH); } catch {}

    const proc = Bun.spawn(
      ["bun", "run", "scripts/main.ts", "https://en.wikipedia.org/wiki/Markdown", "-o", OUTPUT_PATH],
      { cwd: PROJECT_DIR, stdout: "pipe", stderr: "pipe" },
    );

    const exitCode = await proc.exited;
    const stderr = await new Response(proc.stderr).text();

    if (exitCode !== 0) {
      console.error("Integration test stderr:", stderr);
    }

    expect(exitCode).toBe(0);
    expect(existsSync(OUTPUT_PATH)).toBe(true);

    const content = readFileSync(OUTPUT_PATH, "utf-8");
    expect(content).toStartWith("---\n");
    expect(content).toContain("fetch_level: 1");
    expect(content).toContain("Markdown");
    expect(content.length).toBeGreaterThan(500);
  }, 30000);

  afterAll(() => {
    try { unlinkSync(OUTPUT_PATH); } catch {}
    try { rmdirSync("/tmp/jdy-url-to-markdown-test"); } catch {}
  });
});

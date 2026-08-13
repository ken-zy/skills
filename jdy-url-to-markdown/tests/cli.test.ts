import { describe, expect, test } from "bun:test";

const PROJECT_DIR = import.meta.dir.replace("/tests", "");

describe("CLI", () => {
  test("--help describes --wait as waiting for valid content", async () => {
    const proc = Bun.spawn(
      ["bun", "run", "scripts/main.ts", "--help"],
      { cwd: PROJECT_DIR, stdout: "pipe", stderr: "pipe" },
    );
    const exitCode = await proc.exited;
    const stderr = await new Response(proc.stderr).text();

    expect({ exitCode, stderr }).toEqual({
      exitCode: 0,
      stderr: expect.stringContaining("Wait for valid content"),
    });
    expect(stderr).toContain("--images <mode>");
  });
});

import { afterEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  buildR2ArticleKeyPrefix,
  uploadWithR2Script,
} from "../scripts/media/r2-script";

const tempDirectories: string[] = [];

function tempDirectory(): string {
  const directory = mkdtempSync(join(tmpdir(), "r2-script-test-"));
  tempDirectories.push(directory);
  return directory;
}

afterEach(() => {
  for (const directory of tempDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("R2 script integration", () => {
  test("builds a stable classified prefix from the canonical URL", () => {
    const first = buildR2ArticleKeyPrefix(
      "https://example.com/story?b=2&a=1#section",
    );
    const second = buildR2ArticleKeyPrefix(
      "https://example.com/story?a=1&b=2",
    );

    expect(first).toBe(second);
    expect(first).toMatch(/^web-articles\/example\.com\/story-[a-f0-9]{12}$/);
  });

  test("runs the uploader and accepts only the expected object URL", async () => {
    const directory = tempDirectory();
    const scriptPath = join(directory, "upload.sh");
    const inputPath = join(directory, "input.png");
    writeFileSync(scriptPath, "#!/usr/bin/env bash\necho \"https://img.jdy.systems/$2.webp\"\n");
    writeFileSync(inputPath, "image");

    await expect(uploadWithR2Script(
      inputPath,
      "web-articles/example/img-001",
      { scriptPath, cwd: directory },
    )).resolves.toBe("https://img.jdy.systems/web-articles/example/img-001.webp");
  });

  test("surfaces uploader failures without claiming a URL", async () => {
    const directory = tempDirectory();
    const scriptPath = join(directory, "upload.sh");
    const inputPath = join(directory, "input.png");
    writeFileSync(scriptPath, "#!/usr/bin/env bash\necho 'upload denied' >&2\nexit 7\n");
    writeFileSync(inputPath, "image");

    await expect(uploadWithR2Script(
      inputPath,
      "web-articles/example/img-001",
      { scriptPath, cwd: directory },
    )).rejects.toThrow("upload denied");
  });
});

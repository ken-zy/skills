import { afterEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { uploadToPicList, verifyPersistentImage } from "../scripts/media/piclist";

const tempDirectories: string[] = [];

function fixtureFile(): string {
  const directory = mkdtempSync(join(tmpdir(), "piclist-test-"));
  tempDirectories.push(directory);
  const path = join(directory, "image.png");
  writeFileSync(path, "not-empty");
  return path;
}

afterEach(() => {
  for (const directory of tempDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("uploadToPicList", () => {
  test("uploads one file and returns only the public WebP URL", async () => {
    let requestBody: BodyInit | null | undefined;
    const url = await uploadToPicList(fixtureFile(), {
      endpoint: "http://127.0.0.1:36677/upload",
      fetchImpl: async (_input, init) => {
        requestBody = init?.body;
        return Response.json({
          success: true,
          result: ["https://img.jdy.systems/manual/test.webp"],
          fullResult: [{ secretInternalMetadata: "ignored" }],
        });
      },
    });

    expect(requestBody).toBeInstanceOf(FormData);
    expect(url).toBe("https://img.jdy.systems/manual/test.webp");
  });

  test("retries a transient local connection failure", async () => {
    let attempts = 0;
    const url = await uploadToPicList(fixtureFile(), {
      endpoint: "http://127.0.0.1:36677/upload",
      retryDelayMs: 0,
      sleep: async () => {},
      fetchImpl: async () => {
        attempts += 1;
        if (attempts === 1) throw new Error("connection refused");
        return Response.json({
          success: true,
          result: ["https://img.jdy.systems/manual/retried.webp"],
        });
      },
    });

    expect(attempts).toBe(2);
    expect(url).toEndWith("retried.webp");
  });

  test("rejects non-local endpoints", async () => {
    await expect(uploadToPicList(fixtureFile(), {
      endpoint: "https://example.com/upload",
    })).rejects.toThrow("must use local HTTP");
  });

  test("does not retry an ambiguous response-shape failure", async () => {
    let attempts = 0;
    await expect(uploadToPicList(fixtureFile(), {
      endpoint: "http://127.0.0.1:36677/upload",
      retryDelayMs: 0,
      sleep: async () => {},
      fetchImpl: async () => {
        attempts += 1;
        return Response.json({ success: true, result: [] });
      },
    })).rejects.toThrow("exactly one result URL");
    expect(attempts).toBe(1);
  });
});

describe("verifyPersistentImage", () => {
  test("requires a reachable WebP response", async () => {
    await expect(verifyPersistentImage(
      "https://img.jdy.systems/manual/test.webp",
      async () => new Response(null, {
        status: 200,
        headers: { "content-type": "image/webp" },
      }),
    )).resolves.toBeUndefined();

    await expect(verifyPersistentImage(
      "https://img.jdy.systems/manual/test.webp",
      async () => new Response(null, {
        status: 404,
        headers: { "content-type": "text/html" },
      }),
    )).rejects.toThrow("verification failed");
  });
});

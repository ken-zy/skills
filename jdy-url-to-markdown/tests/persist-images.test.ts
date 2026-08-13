import { afterEach, describe, expect, test } from "bun:test";
import { existsSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  ImagePersistenceError,
  persistMarkdownImages,
} from "../scripts/media/persist-images";

const tempRoots: string[] = [];

function tempRoot(): string {
  const root = mkdtempSync(join(tmpdir(), "persist-images-test-"));
  tempRoots.push(root);
  return root;
}

afterEach(() => {
  for (const root of tempRoots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function imageResponse(): Response {
  return new Response(new Uint8Array([1, 2, 3]), {
    status: 200,
    headers: { "content-type": "image/png" },
  });
}

describe("persistMarkdownImages", () => {
  test("leaves remote mode unchanged without network calls", async () => {
    const markdown = "before\n\n![one](https://source.example/one.png)\n\nafter";
    const result = await persistMarkdownImages(markdown, {
      mode: "remote",
      sourceUrl: "https://source.example/article",
      fetchImpl: async () => { throw new Error("must not fetch"); },
    });
    expect(result).toBe(markdown);
  });

  test("removes images in none mode and compacts blank lines", async () => {
    const result = await persistMarkdownImages(
      "before\n\n![one](https://source.example/one.png)\n\nafter",
      { mode: "none", sourceUrl: "https://source.example/article" },
    );
    expect(result).toBe("before\n\nafter");
  });

  test("uploads duplicate source URLs once and preserves occurrence order", async () => {
    const uploads: string[] = [];
    const markdown = [
      "![first](https://source.example/a.png)",
      "![second](https://source.example/b.png)",
      "![again](https://source.example/a.png)",
      "![existing](https://img.jdy.systems/manual/existing.webp)",
    ].join("\n\n");

    const result = await persistMarkdownImages(markdown, {
      mode: "piclist",
      sourceUrl: "https://source.example/article",
      tempRoot: tempRoot(),
      fetchImpl: async (input, init) => {
        const url = String(input);
        if (init?.method === "HEAD") {
          return new Response(null, { status: 200, headers: { "content-type": "image/webp" } });
        }
        return imageResponse();
      },
      piclistFetch: async (_input, init) => {
        expect(init?.body).toBeInstanceOf(FormData);
        const url = `https://img.jdy.systems/manual/${uploads.length + 1}.webp`;
        uploads.push(url);
        return Response.json({ success: true, result: [url] });
      },
    });

    expect(uploads).toHaveLength(2);
    expect(result).toContain("![first](https://img.jdy.systems/manual/1.webp)");
    expect(result).toContain("![second](https://img.jdy.systems/manual/2.webp)");
    expect(result).toContain("![again](https://img.jdy.systems/manual/1.webp)");
    expect(result).toContain("![existing](https://img.jdy.systems/manual/existing.webp)");
  });

  test("rejects on upload failure and retains temporary images", async () => {
    const root = tempRoot();
    let errorMessage = "";
    try {
      await persistMarkdownImages("![one](https://source.example/one.png)", {
        mode: "piclist",
        sourceUrl: "https://source.example/article",
        tempRoot: root,
        fetchImpl: async () => imageResponse(),
        piclistFetch: async () => new Response("failed", { status: 500 }),
      });
    } catch (error) {
      errorMessage = (error as Error).message;
    }

    expect(errorMessage).toContain("Temporary images retained at");
    const retainedPath = errorMessage.split("Temporary images retained at ")[1];
    expect(existsSync(retainedPath)).toBe(true);
  });

  test("downloads every source image before the first PicList write", async () => {
    let uploads = 0;
    await expect(persistMarkdownImages([
      "![one](https://source.example/one.png)",
      "![two](https://source.example/two.png)",
    ].join("\n"), {
      mode: "piclist",
      sourceUrl: "https://source.example/article",
      tempRoot: tempRoot(),
      fetchImpl: async (input) => {
        if (String(input).endsWith("two.png")) {
          return new Response("missing", { status: 404 });
        }
        return imageResponse();
      },
      piclistFetch: async () => {
        uploads += 1;
        return Response.json({
          success: true,
          result: ["https://img.jdy.systems/manual/unexpected.webp"],
        });
      },
    })).rejects.toBeInstanceOf(ImagePersistenceError);
    expect(uploads).toBe(0);
  });
});

import { test, expect, beforeAll, afterAll, mock } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Jimp, JimpMime } from "jimp";
import encodeWebp, { init as initWebpEncode } from "@jsquash/webp/encode.js";
import { fileURLToPath } from "node:url";
import { uploadImage } from "./wechat-api.ts";

let tmpDir: string;
let webpPath: string;

beforeAll(async () => {
  // Initialize the WASM-based WebP encoder. Mirror the loader pattern used in
  // wechat-image-processor.ts for the decoder.
  const here = path.dirname(fileURLToPath(import.meta.url));
  const wasmPath = path.resolve(here, "node_modules/@jsquash/webp/codec/enc/webp_enc.wasm");
  const wasmBuffer = await fs.promises.readFile(wasmPath);
  // @ts-expect-error — init() accepts a WebAssembly.Module or a buffer
  await initWebpEncode(await WebAssembly.compile(wasmBuffer));

  // Build a small 64x64 red image as PNG via Jimp, then re-encode to WebP.
  const img = new Jimp({ width: 64, height: 64, color: 0xff0000ff });
  const rgba = img.bitmap;
  const imageData = {
    data: new Uint8ClampedArray(rgba.data),
    width: rgba.width,
    height: rgba.height,
    colorSpace: "srgb" as const,
  };
  const webpArrayBuffer = await encodeWebp(imageData, { quality: 75 });
  const webpBuffer = Buffer.from(webpArrayBuffer);

  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-api-test-"));
  webpPath = path.join(tmpDir, "fixture.webp");
  fs.writeFileSync(webpPath, webpBuffer);

  // Sanity: magic bytes must be RIFF....WEBP
  expect(webpBuffer.subarray(0, 4).toString("ascii")).toBe("RIFF");
  expect(webpBuffer.subarray(8, 12).toString("ascii")).toBe("WEBP");
});

afterAll(() => {
  if (tmpDir && fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("uploadImage(material) converts WebP to a WeChat-accepted format before POSTing", async () => {
  let capturedBody: Buffer | undefined;
  let capturedUrl: string | undefined;

  const originalFetch = globalThis.fetch;
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    capturedUrl = typeof input === "string" ? input : input.toString();
    if (init?.body && Buffer.isBuffer(init.body)) {
      capturedBody = init.body;
    } else if (init?.body instanceof Uint8Array) {
      capturedBody = Buffer.from(init.body);
    }
    return new Response(
      JSON.stringify({ media_id: "fake-media-id", url: "https://mmbiz.qpic.cn/fake" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }) as typeof fetch;

  try {
    const resp = await uploadImage(webpPath, "fake-token", undefined, "material");
    expect(resp.media_id).toBe("fake-media-id");
    expect(capturedUrl).toContain("material/add_material");
    expect(capturedBody).toBeDefined();

    const bodyText = capturedBody!.toString("latin1");
    // The bug: material path passed WebP raw, so body would contain `Content-Type: image/webp`.
    // After the fix, prep re-encodes to JPEG or PNG.
    expect(bodyText).not.toContain("Content-Type: image/webp");
    expect(
      bodyText.includes("Content-Type: image/jpeg") ||
        bodyText.includes("Content-Type: image/png"),
    ).toBe(true);
    // Filename must no longer end in .webp
    expect(bodyText).not.toMatch(/filename="[^"]+\.webp"/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("remote JPEG URL ending /0 gets a .jpg filename even with the correct MIME type; repeated upload is cached", async () => {
  const { DraftSession } = await import("./wechat-draft.ts");
  const { createWechatApiClient } = await import("./wechat-network.ts");
  const jpeg = await new Jimp({ width: 16, height: 16, color: 0xff0000ff }).getBuffer(JimpMime.jpeg);
  const original = globalThis.fetch;
  const bodies: string[] = [];
  globalThis.fetch = (async () => new Response(jpeg, { headers: { "Content-Type": "image/jpeg" } })) as typeof fetch;
  const client = createWechatApiClient(null, async (_url, init) => {
    bodies.push(Buffer.from(init!.body as Uint8Array).toString("latin1"));
    return Response.json({ media_id: "permanent-cover", url: "https://mmbiz.qpic.cn/0" });
  });
  const session = DraftSession.open(path.join(tmpDir, "cover-cache.json"), "/fixture.md", "fake");
  try {
    await uploadImage("https://mmbiz.qpic.cn/0", "fake", undefined, "material", client, session);
    await uploadImage("https://mmbiz.qpic.cn/0", "fake", undefined, "material", client, session);
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toContain('filename="0.jpg"');
    expect(bodies[0]).toContain("Content-Type: image/jpeg");
  } finally { session.close(); globalThis.fetch = original; }
});

test("direct draft helper supports read-original and refuses native video", async () => {
  const { publishToDraft } = await import("./wechat-api.ts");
  const { createWechatApiClient } = await import("./wechat-network.ts");
  const requests: any[] = [];
  const client = createWechatApiClient(null, async (_url, init) => { requests.push(JSON.parse(String(init!.body))); return Response.json({ media_id: "draft" }); });
  const options = { title: "Title", content: "<p>ref</p>", thumbMediaId: "cover", articleType: "news" as const, sourceUrl: "https://example.com/video.mp4" };
  await publishToDraft(options, "fake", client);
  expect(requests[0].articles[0].content_source_url).toBe(options.sourceUrl);
  await expect(publishToDraft({ ...options, content: '<iframe data-mpvid="apiv_1"></iframe>' }, "fake", client)).rejects.toThrow("unverified");
  expect(requests).toHaveLength(1);
});

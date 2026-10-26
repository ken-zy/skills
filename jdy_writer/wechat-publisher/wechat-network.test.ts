import { test, expect } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createWechatApiClient, loadWechatNetworkConfig, validateNetworkConfig, verifyWechatEgress, type NetworkFetch } from "./wechat-network.ts";
import { fetchAccessToken, publishToDraft, uploadImage } from "./wechat-api.ts";

const config = { proxy: "http://127.0.0.1:17993", expectedEgressIp: "95.169.12.176" };
const secret = "TEST_SECRET_DO_NOT_LOG";
const token = "TEST_TOKEN_DO_NOT_LOG";

test("missing config keeps compatibility; malformed config fails without echoing values", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-config-"));
  try {
    const file = path.join(dir, "network.json");
    expect(loadWechatNetworkConfig(file)).toBeNull();
    fs.writeFileSync(file, `{${secret}`);
    expect(() => loadWechatNetworkConfig(file)).toThrow("Invalid WeChat network configuration");
    for (const proxy of ["socks5://127.0.0.1:17993", "http://remote.example:17993", `http://${secret}@127.0.0.1:17993`, "http://127.0.0.1:17993/path"]) {
      expect(() => validateNetworkConfig({ ...config, proxy })).toThrow("Invalid WeChat network configuration");
    }
    expect(() => validateNetworkConfig({ ...config, expectedEgressIp: "999.1.1.1" })).toThrow();
  } finally { fs.rmSync(dir, { recursive: true }); }
});

test("all four WeChat endpoints share one frozen explicit proxy; source download remains ordinary fetch", async () => {
  const calls: Array<{ url: string; init?: Parameters<NetworkFetch>[1] }> = [];
  const mutable = { ...config };
  const client = createWechatApiClient(mutable, async (url, init) => {
    calls.push({ url, init });
    const result = url.includes("/token?") ? { access_token: token }
      : url.includes("/uploadimg?") ? { url: "https://mmbiz.qpic.cn/body.png" }
      : { media_id: "test-media-id", url: "https://mmbiz.qpic.cn/image.png" };
    return Response.json(result);
  });
  mutable.proxy = "http://127.0.0.1:1";
  const original = globalThis.fetch;
  let sourceOptions: unknown = "not called";
  globalThis.fetch = (async (_url, init) => {
    sourceOptions = init;
    return new Response(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6X1sAAAAASUVORK5CYII=", "base64"));
  }) as typeof fetch;
  try {
    await fetchAccessToken("test-app", secret, client);
    await uploadImage("https://img.example/image.png", token, undefined, "body", client);
    await uploadImage("https://img.example/image.png", token, undefined, "material", client);
    await publishToDraft({ title: "test", content: "test", thumbMediaId: "thumb", articleType: "news" }, token, client);
  } finally { globalThis.fetch = original; }
  expect(calls.map(x => new URL(x.url).pathname)).toEqual(["/cgi-bin/token", "/cgi-bin/media/uploadimg", "/cgi-bin/material/add_material", "/cgi-bin/draft/add"]);
  for (const call of calls) {
    expect(call.init?.proxy).toEqual({ url: config.proxy, respectNoProxy: false });
    expect(call.init?.redirect).toBe("error");
    expect(call.init?.signal).toBeInstanceOf(AbortSignal);
  }
  expect(sourceOptions).toBeUndefined();
});

test("unconfigured API does not introduce a proxy", async () => {
  const client = createWechatApiClient(null, async (_url, init) => {
    expect(init?.proxy).toBeUndefined();
    return Response.json({ access_token: token });
  });
  expect(await fetchAccessToken("app", secret, client)).toBe(token);
});

test("exceptions and server errors never echo fake credentials or raw URLs", async () => {
  const url = `https://api.weixin.qq.com/cgi-bin/token?secret=${secret}&access_token=${token}`;
  const modes = [
    async () => { throw new Error(`Failed request ${url}`); },
    async () => Response.json({ errcode: 40164, errmsg: `invalid ip 120.225.251.146 ${url}` }),
    async () => Response.json({ errcode: 40001, errmsg: url }),
    async () => new Response(url, { status: 502 }),
    async () => new Response(`invalid JSON ${url}`),
  ];
  for (const fetchImpl of modes) {
    let message = "";
    try { await createWechatApiClient(config, fetchImpl).json("token", url); }
    catch (error) { message = `Error: ${(error as Error).message}`; }
    expect(message).not.toBe("");
    expect(message).not.toContain(secret);
    expect(message).not.toContain(token);
    expect(message).not.toContain("https://");
  }
});

test("preflight requires BOTH expected IPs; mismatch and failure never retry directly", async () => {
  let calls = 0;
  await verifyWechatEgress(config, async (_url, init) => {
    calls++;
    expect(init?.proxy?.respectNoProxy).toBe(false);
    return new Response(config.expectedEgressIp);
  });
  expect(calls).toBe(2);
  calls = 0;
  await expect(verifyWechatEgress(config, async () => {
    calls++;
    throw new Error(secret);
  })).rejects.toThrow("no direct fallback");
  expect(calls).toBe(1);
  await expect(verifyWechatEgress(config, async () => new Response("120.225.251.146"))).rejects.toThrow("IP mismatch");
});

test("caller signal cannot remove the API deadline; redirects are forbidden", async () => {
  const signal = new AbortController().signal;
  const client = createWechatApiClient(config, async (_url, init) => {
    expect(init?.signal).not.toBe(signal);
    expect(init?.redirect).toBe("error");
    return Response.json({ access_token: token });
  });
  await client.json("token", "https://api.weixin.qq.com/cgi-bin/token", { signal, redirect: "follow" });
});

test("missing draft media_id cannot be reported as success", async () => {
  const client = createWechatApiClient(config, async () => Response.json({ errcode: 0 }));
  await expect(publishToDraft({ title: "test", content: "test", thumbMediaId: "thumb", articleType: "news" }, token, client)).rejects.toThrow("missing media_id");
});

test("dry-run renders without fixed-egress preflight or credential loading", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-dry-run-"));
  try {
    const article = path.join(dir, "article.md");
    fs.writeFileSync(article, "# Test\n\nDry run only.\n");
    const result = Bun.spawnSync([process.execPath, path.join(import.meta.dir, "wechat-api.ts"), article, "--dry-run"], { cwd: dir });
    const output = result.stdout.toString() + result.stderr.toString();
    expect(result.exitCode).toBe(0);
    expect(output).not.toContain("Credentials source");
    expect(output).not.toContain("Fixed egress");
    expect(output).not.toContain("Fetching access token");
  } finally { fs.rmSync(dir, { recursive: true }); }
});

test("installed Bun fails closed with a dead explicit proxy even when NO_PROXY allows direct access", async () => {
  const server = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response() });
  const port = server.port;
  await server.stop(true);
  const script = `import {verifyWechatEgress} from ${JSON.stringify(path.join(import.meta.dir, "wechat-network.ts"))};
    try { await verifyWechatEgress({proxy:"http://127.0.0.1:${port}",expectedEgressIp:"95.169.12.176"}); process.exit(2); }
    catch(e) { if(!e.message.includes("preflight failed; no direct fallback")) process.exit(3); console.log("closed-proxy-failed-safely"); }`;
  const result = Bun.spawnSync([process.execPath, "-e", script], {
    env: { ...process.env, NO_PROXY: "*", no_proxy: "*" }, timeout: 20_000,
  });
  expect(result.exitCode).toBe(0);
  expect(result.stdout.toString()).toContain("closed-proxy-failed-safely");
});

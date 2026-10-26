import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { isIP } from "node:net";

export interface WechatNetworkConfig {
  readonly proxy: string;
  readonly expectedEgressIp: string;
}

export type NetworkFetch = (url: string, init?: RequestInit & {
  proxy?: { url: string; respectNoProxy: false };
}) => Promise<Response>;

export class WechatNetworkError extends Error {
  constructor(message: string) { super(message); this.name = "WechatNetworkError"; }
}

// An authenticated API JSON response explicitly rejected the request. Transport,
// HTTP and malformed-response errors do not establish the write outcome.
export class WechatApiRejectedError extends WechatNetworkError {
  constructor(message: string, readonly code: number) { super(message); this.name = "WechatApiRejectedError"; }
}

export function validateNetworkConfig(value: unknown): Readonly<WechatNetworkConfig> {
  const fail = () => { throw new WechatNetworkError("Invalid WeChat network configuration"); };
  if (!value || typeof value !== "object" || Array.isArray(value)) return fail();
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some(key => !["proxy", "expectedEgressIp"].includes(key))) return fail();
  if (typeof record.proxy !== "string" || typeof record.expectedEgressIp !== "string") return fail();
  let proxy: URL;
  try { proxy = new URL(record.proxy); } catch { return fail(); }
  if (proxy.protocol !== "http:" || proxy.hostname !== "127.0.0.1" || !proxy.port ||
      proxy.username || proxy.password || proxy.pathname !== "/" || proxy.search || proxy.hash ||
      isIP(record.expectedEgressIp) !== 4) return fail();
  return Object.freeze({ proxy: proxy.origin, expectedEgressIp: record.expectedEgressIp });
}

export function loadWechatNetworkConfig(file = path.join(os.homedir(), ".config/jdy-writer/wechat-network.json")) {
  let raw: string;
  try { raw = fs.readFileSync(file, "utf8"); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw new WechatNetworkError("Cannot read WeChat network configuration");
  }
  let value: unknown;
  try { value = JSON.parse(raw); }
  catch { throw new WechatNetworkError("Invalid WeChat network configuration"); }
  return validateNetworkConfig(value);
}

const nativeFetch: NetworkFetch = (url, init) => globalThis.fetch(url, init);

// Bun 1.3.11 still honors NO_PROXY for an explicit proxy. Isolate only these
// network requests in a child with a clean proxy environment; never mutate the
// publisher's environment (which also handles ordinary source-image downloads).
const isolatedProxyFetch: NetworkFetch = async (url, init = {}) => {
  if (!init.proxy) throw new Error("Missing fixed proxy");
  const env = { ...process.env };
  for (const key of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"]) delete env[key];
  const body = init.body;
  if (body !== undefined && body !== null && typeof body !== "string" && !(body instanceof Uint8Array)) throw new Error("Unsupported proxy request body");
  const request = JSON.stringify({ url, proxy: init.proxy.url, method: init.method,
    headers: [...new Headers(init.headers)],
    body: body === undefined || body === null ? undefined : Buffer.from(body).toString("base64") });
  if (init.signal?.aborted) throw new Error("Proxy request aborted");
  const child = Bun.spawn([process.execPath, path.join(import.meta.dir, "wechat-proxy-worker.ts")], {
    env, stdin: "pipe", stdout: "pipe", stderr: "pipe",
  });
  const abort = () => child.kill();
  init.signal?.addEventListener("abort", abort, { once: true });
  try {
    const outputPromise = new Response(child.stdout).text();
    const stderrPromise = new Response(child.stderr).text();
    await child.stdin.write(request);
    child.stdin.end();
    const [output, , code] = await Promise.all([outputPromise, stderrPromise, child.exited]);
    if (code !== 0 || init.signal?.aborted) throw new Error("Fixed proxy request failed");
    const result = JSON.parse(output);
    if (result.error) throw new Error("Fixed proxy request failed");
    const data = [204, 205, 304].includes(result.status) ? null : Buffer.from(result.body, "base64");
    return new Response(data, { status: result.status, headers: result.headers });
  } finally {
    init.signal?.removeEventListener("abort", abort);
    child.kill();
  }
};

function requestOptions(config: WechatNetworkConfig | null, init: RequestInit = {}, timeoutMs = 60_000) {
  return {
    ...init,
    redirect: "error" as const,
    signal: init.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
    ...(config ? { proxy: { url: config.proxy, respectNoProxy: false as const } } : {}),
  };
}

export async function verifyWechatEgress(config: WechatNetworkConfig, fetchImpl: NetworkFetch = isolatedProxyFetch) {
  const frozen = validateNetworkConfig(config);
  const probes = ["https://myip.ipip.net", "https://api.ipify.org"];
  for (const url of probes) {
    let text: string;
    try {
      const response = await fetchImpl(url, requestOptions(frozen, {}, 15_000));
      if (!response.ok) throw new Error();
      text = await response.text();
    } catch { throw new WechatNetworkError("WeChat fixed-egress preflight failed; no direct fallback"); }
    const ip = text.match(/\b(?:\d{1,3}\.){3}\d{1,3}\b/)?.[0];
    if (!ip || isIP(ip) !== 4 || ip !== frozen.expectedEgressIp) {
      throw new WechatNetworkError("WeChat fixed-egress IP mismatch; publishing stopped");
    }
  }
  return frozen.expectedEgressIp;
}

export function createWechatApiClient(config: WechatNetworkConfig | null = null, fetchImpl?: NetworkFetch) {
  const frozen = config ? validateNetworkConfig(config) : null;
  const request = fetchImpl ?? (frozen ? isolatedProxyFetch : nativeFetch);
  return Object.freeze({
    async json<T>(stage: "token" | "uploadimg" | "material" | "draft", url: string, init: RequestInit = {}): Promise<T> {
      let parsed: URL;
      try { parsed = new URL(url); } catch { throw new WechatNetworkError(`WeChat ${stage}: invalid endpoint`); }
      if (parsed.protocol !== "https:" || parsed.hostname !== "api.weixin.qq.com" || parsed.port || parsed.username || parsed.password) {
        throw new WechatNetworkError(`WeChat ${stage}: invalid endpoint`);
      }
      let response: Response;
      let data: Record<string, unknown>;
      try {
        response = await request(url, requestOptions(frozen, init));
        if (!response.ok) throw new WechatNetworkError(`WeChat ${stage}: HTTP ${response.status}`);
        data = await response.json() as Record<string, unknown>;
      } catch (error) {
        if (error instanceof WechatNetworkError) throw error;
        throw new WechatNetworkError(`WeChat ${stage}: network or response failure; no direct fallback`);
      }
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new WechatNetworkError(`WeChat ${stage}: invalid response`);
      if (data.errcode !== undefined && data.errcode !== 0) {
        const code = typeof data.errcode === "number" && Number.isSafeInteger(data.errcode) ? data.errcode : "invalid";
        const candidate = code === 40164 && typeof data.errmsg === "string"
          ? data.errmsg.match(/invalid ip\s+((?:\d{1,3}\.){3}\d{1,3})\b/)?.[1] : undefined;
        const ip = candidate && isIP(candidate) === 4 ? `; whitelist IP ${candidate}` : "";
        const message = `WeChat ${stage}: error ${code}${ip}`;
        if (typeof code === "number") throw new WechatApiRejectedError(message, code);
        throw new WechatNetworkError(message);
      }
      return data as T;
    },
  });
}

export type WechatApiClient = ReturnType<typeof createWechatApiClient>;

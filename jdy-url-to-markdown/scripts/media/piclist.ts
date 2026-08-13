import { basename } from "path";

export type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export interface PicListOptions {
  endpoint: string;
  fetchImpl?: FetchLike;
  retries?: number;
  retryDelayMs?: number;
  sleep?: (milliseconds: number) => Promise<void>;
}

function assertLocalEndpoint(endpoint: string): void {
  const parsed = new URL(endpoint);
  if (parsed.protocol !== "http:"
    || (parsed.hostname !== "127.0.0.1" && parsed.hostname !== "localhost")) {
    throw new Error(`PicList endpoint must use local HTTP: ${endpoint}`);
  }
}

function parsePicListUrl(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    throw new Error("PicList returned an invalid response");
  }
  const data = payload as { success?: unknown; result?: unknown };
  if (data.success !== true || !Array.isArray(data.result) || data.result.length !== 1) {
    throw new Error("PicList upload did not return exactly one result URL");
  }
  const url = data.result[0];
  if (typeof url !== "string") throw new Error("PicList result URL is invalid");
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" || !parsed.pathname.endsWith(".webp")) {
    throw new Error(`PicList result must be an HTTPS WebP URL: ${url}`);
  }
  return url;
}

export async function uploadToPicList(
  filePath: string,
  options: PicListOptions,
): Promise<string> {
  assertLocalEndpoint(options.endpoint);
  const fetchImpl = options.fetchImpl ?? fetch;
  const retries = options.retries ?? 3;
  const delay = options.retryDelayMs ?? 250;
  const sleep = options.sleep ?? ((milliseconds) => Bun.sleep(milliseconds));
  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= retries; attempt += 1) {
    let response: Response;
    try {
      const form = new FormData();
      form.append("list", Bun.file(filePath), basename(filePath));
      response = await fetchImpl(options.endpoint, { method: "POST", body: form });
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      if (attempt < retries) await sleep(delay);
      continue;
    }

    // A response means PicList received the request. Do not retry ambiguous
    // HTTP or response-shape failures because the object may already exist.
    if (!response.ok) throw new Error(`PicList HTTP ${response.status}`);
    return parsePicListUrl(await response.json());
  }

  throw new Error(`PicList upload failed after ${retries} attempts: ${lastError?.message}`);
}

export async function verifyPersistentImage(
  url: string,
  fetchImpl: FetchLike = fetch,
): Promise<void> {
  const response = await fetchImpl(url, { method: "HEAD" });
  const contentType = response.headers.get("content-type")?.split(";", 1)[0].toLowerCase();
  if (!response.ok || contentType !== "image/webp") {
    throw new Error(
      `Persistent image verification failed: HTTP ${response.status}, ${contentType || "unknown type"}`,
    );
  }
}

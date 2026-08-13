import { mkdtemp, rm, writeFile } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { uploadToPicList, verifyPersistentImage } from "./piclist";
import type { FetchLike } from "./piclist";

export type ImageMode = "remote" | "piclist" | "none";

export class ImagePersistenceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ImagePersistenceError";
  }
}

export interface PersistImagesOptions {
  mode: ImageMode;
  sourceUrl: string;
  piclistEndpoint?: string;
  persistentHosts?: string[];
  fetchImpl?: FetchLike;
  piclistFetch?: FetchLike;
  tempRoot?: string;
}

const MARKDOWN_IMAGE = /!\[[^\]]*\]\(\s*(https?:\/\/[^\s)]+)([^)]*)\)/g;
const CONTENT_TYPE_EXTENSIONS: Record<string, string> = {
  "image/gif": "gif",
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

function collectImageUrls(markdown: string): string[] {
  const urls: string[] = [];
  for (const match of markdown.matchAll(MARKDOWN_IMAGE)) urls.push(match[1]);
  return urls;
}

function removeImages(markdown: string): string {
  return markdown
    .replace(MARKDOWN_IMAGE, "")
    .replace(/^[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function replaceImageUrls(markdown: string, replacements: Map<string, string>): string {
  return markdown.replace(MARKDOWN_IMAGE, (full, url: string) => {
    const replacement = replacements.get(url);
    return replacement ? full.replace(url, replacement) : full;
  });
}

function isPersistent(url: string, hosts: string[]): boolean {
  try {
    return hosts.includes(new URL(url).hostname.toLowerCase());
  } catch {
    return false;
  }
}

async function downloadImage(
  url: string,
  fileNumber: number,
  directory: string,
  sourceUrl: string,
  fetchImpl: FetchLike,
): Promise<string> {
  const response = await fetchImpl(url, {
    headers: {
      referer: sourceUrl,
      "user-agent": "Mozilla/5.0 jdy-url-to-markdown",
    },
  });
  if (!response.ok) throw new Error(`Image download failed: HTTP ${response.status} for ${url}`);

  const contentType = response.headers.get("content-type")?.split(";", 1)[0].toLowerCase() || "";
  const extension = CONTENT_TYPE_EXTENSIONS[contentType];
  if (!extension) throw new Error(`Unsupported image content type ${contentType || "unknown"}: ${url}`);

  const bytes = await response.arrayBuffer();
  if (bytes.byteLength === 0) throw new Error(`Downloaded image is empty: ${url}`);
  const filePath = join(directory, `${String(fileNumber).padStart(3, "0")}.${extension}`);
  await writeFile(filePath, Buffer.from(bytes));
  return filePath;
}

export async function persistMarkdownImages(
  markdown: string,
  options: PersistImagesOptions,
): Promise<string> {
  if (options.mode === "remote") return markdown;
  if (options.mode === "none") return removeImages(markdown);

  const endpoint = options.piclistEndpoint ?? "http://127.0.0.1:36677/upload";
  const persistentHosts = (options.persistentHosts ?? ["img.jdy.systems"])
    .map((host) => host.toLowerCase());
  const uniqueUrls = [...new Set(collectImageUrls(markdown))]
    .filter((url) => !isPersistent(url, persistentHosts));
  if (uniqueUrls.length === 0) return markdown;

  const fetchImpl = options.fetchImpl ?? fetch;
  const piclistFetch = options.piclistFetch ?? fetch;
  const tempDirectory = await mkdtemp(join(options.tempRoot ?? tmpdir(), "jdy-url-images-"));
  const replacements = new Map<string, string>();

  try {
    const downloaded: Array<{ imageUrl: string; filePath: string }> = [];
    for (const [index, imageUrl] of uniqueUrls.entries()) {
      const filePath = await downloadImage(
        imageUrl,
        index + 1,
        tempDirectory,
        options.sourceUrl,
        fetchImpl,
      );
      downloaded.push({ imageUrl, filePath });
    }

    // Finish all source downloads before the first external write. This avoids
    // partial R2 uploads when a later source image is missing or invalid.
    for (const { imageUrl, filePath } of downloaded) {
      const persistedUrl = await uploadToPicList(filePath, {
        endpoint,
        fetchImpl: piclistFetch,
      });
      await verifyPersistentImage(persistedUrl, fetchImpl);
      replacements.set(imageUrl, persistedUrl);
    }

    const result = replaceImageUrls(markdown, replacements);
    await rm(tempDirectory, { recursive: true, force: true });
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new ImagePersistenceError(
      `${message}. Temporary images retained at ${tempDirectory}`,
    );
  }
}

import { mkdtemp, rm, stat, writeFile } from "fs/promises";
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
  gifConverter?: (sourcePath: string, targetPath: string) => Promise<void>;
}

const MARKDOWN_IMAGE = /!\[[^\]]*\]\(\s*([^\s)]+)([^)]*)\)/g;
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

function resolveImageUrl(imageUrl: string, sourceUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(imageUrl, sourceUrl);
  } catch {
    throw new Error(`Invalid image URL: ${imageUrl}`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`Unsupported image URL protocol: ${imageUrl}`);
  }
  return parsed.toString();
}

async function convertGifToWebp(sourcePath: string, targetPath: string): Promise<void> {
  let child: ReturnType<typeof Bun.spawn>;
  try {
    child = Bun.spawn(
      ["gif2webp", "-q", "90", sourcePath, "-o", targetPath],
      { stdout: "ignore", stderr: "pipe" },
    );
  } catch (error) {
    throw new Error(`GIF conversion requires gif2webp on PATH: ${(error as Error).message}`);
  }
  const exitCode = await child.exited;
  if (exitCode !== 0) {
    const stderr = await new Response(child.stderr).text();
    throw new Error(`gif2webp failed with exit ${exitCode}: ${stderr.trim()}`);
  }
}

async function prepareUploadFile(
  filePath: string,
  gifConverter: (sourcePath: string, targetPath: string) => Promise<void>,
): Promise<string> {
  if (!filePath.toLowerCase().endsWith(".gif")) return filePath;
  const targetPath = `${filePath.slice(0, -4)}.webp`;
  await gifConverter(filePath, targetPath);
  if ((await stat(targetPath)).size === 0) {
    throw new Error(`gif2webp produced an empty file: ${targetPath}`);
  }
  return targetPath;
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
  const replacements = new Map<string, string>();
  const sourceUrlsByResolvedUrl = new Map<string, string[]>();
  for (const sourceImageUrl of new Set(collectImageUrls(markdown))) {
    const resolvedUrl = resolveImageUrl(sourceImageUrl, options.sourceUrl);
    if (isPersistent(resolvedUrl, persistentHosts)) {
      if (sourceImageUrl !== resolvedUrl) replacements.set(sourceImageUrl, resolvedUrl);
      continue;
    }
    const sourceUrls = sourceUrlsByResolvedUrl.get(resolvedUrl) ?? [];
    sourceUrls.push(sourceImageUrl);
    sourceUrlsByResolvedUrl.set(resolvedUrl, sourceUrls);
  }
  if (sourceUrlsByResolvedUrl.size === 0) {
    return replaceImageUrls(markdown, replacements);
  }

  const fetchImpl = options.fetchImpl ?? fetch;
  const piclistFetch = options.piclistFetch ?? fetch;
  const tempDirectory = await mkdtemp(join(options.tempRoot ?? tmpdir(), "jdy-url-images-"));

  try {
    const downloaded: Array<{
      sourceUrls: string[];
      filePath: string;
    }> = [];
    for (const [index, [resolvedUrl, sourceUrls]] of [
      ...sourceUrlsByResolvedUrl.entries(),
    ].entries()) {
      const filePath = await downloadImage(
        resolvedUrl,
        index + 1,
        tempDirectory,
        options.sourceUrl,
        fetchImpl,
      );
      downloaded.push({ sourceUrls, filePath });
    }

    // Finish every download and local conversion before the first external write.
    // This avoids partial R2 uploads when a later source image is missing or invalid.
    const prepared: typeof downloaded = [];
    for (const { sourceUrls, filePath } of downloaded) {
      prepared.push({
        sourceUrls,
        filePath: await prepareUploadFile(
          filePath,
          options.gifConverter ?? convertGifToWebp,
        ),
      });
    }

    for (const { sourceUrls, filePath } of prepared) {
      const persistedUrl = await uploadToPicList(filePath, {
        endpoint,
        fetchImpl: piclistFetch,
      });
      await verifyPersistentImage(persistedUrl, fetchImpl);
      for (const sourceUrl of sourceUrls) replacements.set(sourceUrl, persistedUrl);
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

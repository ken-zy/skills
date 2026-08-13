import { existsSync, readFileSync } from "fs";
import { join } from "path";
import type { ImageMode } from "./media/persist-images";

export interface Preferences {
  defaultOutputDir: string;
  defaultTimeout: number;
  defaultImageMode: ImageMode;
  piclistEndpoint: string;
  persistentImageHosts: string[];
}

export const DEFAULT_PREFERENCES: Preferences = {
  defaultOutputDir: "40_Reference/Articles",
  defaultTimeout: 30000,
  defaultImageMode: "remote",
  piclistEndpoint: "http://127.0.0.1:36677/upload",
  persistentImageHosts: ["img.jdy.systems"],
};

function unquote(value: string): string {
  const trimmed = value.trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"'))
    || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

export function parseExtend(content: string): Partial<Preferences> {
  const values = new Map<string, string>();
  for (const line of content.split(/\r?\n/)) {
    const match = line.match(/^\s*([a-z_]+)\s*:\s*(.*?)\s*$/);
    if (match) values.set(match[1], unquote(match[2]));
  }

  const preferences: Partial<Preferences> = {};
  const outputDir = values.get("default_output_dir");
  if (outputDir) preferences.defaultOutputDir = outputDir;

  const timeout = values.get("default_timeout");
  if (timeout) {
    const parsed = Number.parseInt(timeout, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      throw new Error(`Invalid default_timeout in EXTEND.md: ${timeout}`);
    }
    preferences.defaultTimeout = parsed;
  }

  const imageMode = values.get("default_image_mode");
  if (imageMode) {
    if (!isImageMode(imageMode)) {
      throw new Error(`Invalid default_image_mode in EXTEND.md: ${imageMode}`);
    }
    preferences.defaultImageMode = imageMode;
  }

  const endpoint = values.get("piclist_endpoint");
  if (endpoint) preferences.piclistEndpoint = endpoint;

  const hosts = values.get("persistent_image_hosts");
  if (hosts) {
    preferences.persistentImageHosts = hosts
      .split(",")
      .map((host) => host.trim().toLowerCase())
      .filter(Boolean);
  }

  return preferences;
}

export function isImageMode(value: string): value is ImageMode {
  return value === "remote" || value === "piclist" || value === "none";
}

export function findExtendPath(
  cwd = process.cwd(),
  env: Record<string, string | undefined> = process.env,
): string | undefined {
  const candidates = [
    join(cwd, ".jdy-url-to-markdown", "EXTEND.md"),
    env.XDG_CONFIG_HOME
      ? join(env.XDG_CONFIG_HOME, "jdy-url-to-markdown", "EXTEND.md")
      : undefined,
    env.HOME ? join(env.HOME, ".jdy-url-to-markdown", "EXTEND.md") : undefined,
  ].filter((candidate): candidate is string => Boolean(candidate));

  return candidates.find((candidate) => existsSync(candidate));
}

export function loadPreferences(
  cwd = process.cwd(),
  env: Record<string, string | undefined> = process.env,
): Preferences {
  const extendPath = findExtendPath(cwd, env);
  if (!extendPath) return { ...DEFAULT_PREFERENCES };
  return {
    ...DEFAULT_PREFERENCES,
    ...parseExtend(readFileSync(extendPath, "utf-8")),
  };
}

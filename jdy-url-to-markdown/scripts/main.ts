import { matchSiteRule, getDefaultRule } from "./router";
import { fetchAndParse } from "./fetcher";
import { parse } from "./parser";
import { qualityCheck } from "./quality";
import { getCleaners } from "./rules/cleaners";
import { buildOutputPath, writeMarkdown } from "./writer";
import { ensureDaemon, sendDaemonRequest } from "./cdp/daemon";
import { waitForValidContent } from "./wait";
import { isImageMode, loadPreferences } from "./config";
import { ImagePersistenceError, persistMarkdownImages } from "./media/persist-images";
import type { ImageMode } from "./media/persist-images";
import type { ParseResult, SiteRule } from "./types";

interface CliArgs {
  url: string;
  cdp: boolean;
  wait: boolean;
  timeout: number;
  imageMode: ImageMode;
  output?: string;
}

function printUsage(): void {
  console.error(`Usage: bun run scripts/main.ts <url> [options]
Options:
  --cdp           Force CDP (skip Level 1)
  --wait          Wait for valid content in CDP
  --timeout <ms>  Page load timeout (default: 30000)
  --images <mode> Image handling: remote, piclist, or none (default: remote)
  -o <path>       Output file path`);
}

function parseArgs(
  args: string[],
  defaults: { timeout: number; imageMode: ImageMode },
): CliArgs {
  const positional: string[] = [];
  let cdp = false;
  let wait = false;
  let timeout = defaults.timeout;
  let imageMode = defaults.imageMode;
  let output: string | undefined;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--cdp": cdp = true; break;
      case "--wait": wait = true; break;
      case "--timeout": {
        const value = args[++i];
        timeout = Number.parseInt(value, 10);
        if (!Number.isFinite(timeout) || timeout <= 0) {
          console.error(`Invalid timeout: ${value}`);
          process.exit(1);
        }
        break;
      }
      case "--images": {
        const value = args[++i];
        if (!isImageMode(value)) {
          console.error(`Invalid image mode: ${value}`);
          process.exit(1);
        }
        imageMode = value;
        break;
      }
      case "-o": output = args[++i]; break;
      case "--help": case "-h": printUsage(); process.exit(0);
      default:
        if (args[i].startsWith("-")) {
          console.error(`Unknown option: ${args[i]}`);
          process.exit(1);
        }
        positional.push(args[i]);
    }
  }

  if (positional.length !== 1) {
    printUsage();
    process.exit(1);
  }

  return { url: positional[0], cdp, wait, timeout, imageMode, output };
}

async function persistAndWrite(
  result: ParseResult,
  fetchLevel: number,
  args: CliArgs,
  preferences: ReturnType<typeof loadPreferences>,
): Promise<string> {
  const markdown = await persistMarkdownImages(result.markdown, {
    mode: args.imageMode,
    sourceUrl: args.url,
    piclistEndpoint: preferences.piclistEndpoint,
    persistentHosts: preferences.persistentImageHosts,
  });
  const filePath = args.output
    || buildOutputPath(result.metadata.title, preferences.defaultOutputDir);
  return writeMarkdown(filePath, result.metadata, markdown, fetchLevel);
}

async function cdpFetch(
  url: string,
  rule: SiteRule,
  timeout: number,
  waitForContent = false,
): Promise<string> {
  const sock = await ensureDaemon();
  try {
    await sendDaemonRequest(sock, "navigate", { url, timeout });

    const getCurrentHTML = async (): Promise<string> => {
      const { html } = await sendDaemonRequest(sock, "getHTML", {});
      return html;
    };

    const runAction = async (action: string): Promise<void> => {
      if (action.startsWith("waitForSelector:")) {
        const selectorAndTimeout = action.slice("waitForSelector:".length);
        await sendDaemonRequest(sock, "getHTML", { waitForSelector: selectorAndTimeout });
      } else if (action.startsWith("removeOverlays:")) {
        const selectors = action.slice("removeOverlays:".length);
        await sendDaemonRequest(sock, "evaluate", {
          expression: `document.querySelectorAll('${selectors}').forEach(el => el.remove())`,
        });
      } else if (action === "autoScroll") {
        await sendDaemonRequest(sock, "evaluate", {
          expression: `(async () => {
            for (let i = 0; i < 5; i++) {
              window.scrollBy(0, window.innerHeight);
              await new Promise(r => setTimeout(r, 500));
            }
            window.scrollTo(0, 0);
          })()`,
        });
      } else if (action === "expandContent") {
        await sendDaemonRequest(sock, "evaluate", {
          expression: `document.querySelectorAll('[class*="expand"], [class*="more"]').forEach(el => el.click())`,
        });
      }
    };

    const actions = rule.cdpActions ?? [];
    if (waitForContent) {
      const cleaners = rule.cleaners ? getCleaners(rule.cleaners) : [];
      await waitForValidContent({
        read: getCurrentHTML,
        validate: (html) => {
          const result = parse(html, url, cleaners, rule.contentSelector);
          return qualityCheck(result.markdown, rule.quality);
        },
        timeoutMs: timeout,
      });

      for (const action of actions) {
        if (!action.startsWith("waitForSelector:")) await runAction(action);
      }
    } else {
      for (const action of actions) await runAction(action);
    }

    return await getCurrentHTML();
  } finally {
    sock.destroy();
  }
}

async function main(): Promise<void> {
  const preferences = loadPreferences();
  const args = parseArgs(process.argv.slice(2), {
    timeout: preferences.defaultTimeout,
    imageMode: preferences.defaultImageMode,
  });
  const { url, cdp: forceCdp, wait, timeout } = args;

  try {
    new URL(url);
  } catch {
    console.error(`Invalid URL: ${url}`);
    process.exit(1);
  }

  const rule = matchSiteRule(url) || getDefaultRule();

  // Adapter dispatch
  if (rule.adapter) {
    let result: ParseResult | undefined;
    try {
      const adapterModule = await import(`./adapters/${rule.adapter}.ts`);
      result = await adapterModule.extract(url, {
        timeout,
        quality: rule.quality,
        ensureDaemon,
        sendDaemonRequest,
      });
    } catch (e) {
      console.error(`[adapter:${rule.adapter}] Failed: ${(e as Error).message}`);
      console.error("Falling back to generic CDP extraction...");
    }

    if (result) {
      try {
        console.log(await persistAndWrite(result, 2, args, preferences));
        return;
      } catch (e) {
        console.error(`Error: ${(e as Error).message}`);
        process.exit(e instanceof ImagePersistenceError ? 4 : 1);
      }
    }
  }

  // Generic fetch
  try {
    const result = await fetchAndParse(url, {
      rule,
      timeout,
      forceCdp: forceCdp || wait,
      cdpFetch: (targetUrl, targetRule, targetTimeout) => (
        cdpFetch(targetUrl, targetRule, targetTimeout, wait)
      ),
    });

    console.log(await persistAndWrite(result, result.fetchLevel, args, preferences));
    return;
  } catch (e) {
    const err = e as Error;
    console.error(`Error: ${err.message}`);
    if (err instanceof ImagePersistenceError) process.exit(4);
    if (err.message.includes("Quality check failed")) process.exit(2);
    if (err.message.includes("CDP")) process.exit(3);
    process.exit(1);
  }
}

main();

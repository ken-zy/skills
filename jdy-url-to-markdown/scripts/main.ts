import { matchSiteRule, getDefaultRule } from "./router";
import { fetchAndParse } from "./fetcher";
import { buildOutputPath, writeMarkdown } from "./writer";
import { ensureDaemon, sendDaemonRequest } from "./cdp/daemon";
import type { SiteRule } from "./types";

function printUsage(): void {
  console.error(`Usage: bun run scripts/main.ts <url> [options]
Options:
  --cdp           Force CDP (skip Level 1)
  --wait          Force CDP (alias for --cdp, reserved for future login-wait)
  --timeout <ms>  Page load timeout (default: 30000)
  -o <path>       Output file path`);
}

function parseArgs(args: string[]): { url: string; cdp: boolean; wait: boolean; timeout: number; output?: string } {
  const positional: string[] = [];
  let cdp = false;
  let wait = false;
  let timeout = 30000;
  let output: string | undefined;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--cdp": cdp = true; break;
      case "--wait": wait = true; break;
      case "--timeout": timeout = parseInt(args[++i]); break;
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

  return { url: positional[0], cdp, wait, timeout, output };
}

async function cdpFetch(url: string, rule: SiteRule, timeout: number): Promise<string> {
  const sock = await ensureDaemon();
  try {
    await sendDaemonRequest(sock, "navigate", { url, timeout });

    if (rule.cdpActions) {
      for (const action of rule.cdpActions) {
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
      }
    }

    const { html } = await sendDaemonRequest(sock, "getHTML", {});
    return html;
  } finally {
    sock.destroy();
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const { url, cdp: forceCdp, wait, timeout, output } = args;

  try {
    new URL(url);
  } catch {
    console.error(`Invalid URL: ${url}`);
    process.exit(1);
  }

  const rule = matchSiteRule(url) || getDefaultRule();

  // Adapter dispatch
  if (rule.adapter) {
    try {
      const adapterModule = await import(`./adapters/${rule.adapter}.ts`);
      const result = await adapterModule.extract(url, { timeout, ensureDaemon, sendDaemonRequest });
      const filePath = output || buildOutputPath(result.metadata.title, "40_Reference/Articles");
      const written = writeMarkdown(filePath, result.metadata, result.markdown, 2);
      console.log(written);
      process.exit(0);
    } catch (e) {
      console.error(`[adapter:${rule.adapter}] Failed: ${(e as Error).message}`);
      console.error("Falling back to generic CDP extraction...");
    }
  }

  // Generic fetch
  try {
    const result = await fetchAndParse(url, {
      rule,
      timeout,
      forceCdp: forceCdp || wait,
      cdpFetch,
    });

    const filePath = output || buildOutputPath(result.metadata.title, "40_Reference/Articles");
    const written = writeMarkdown(filePath, result.metadata, result.markdown, result.fetchLevel);
    console.log(written);
    process.exit(0);
  } catch (e) {
    const err = e as Error;
    console.error(`Error: ${err.message}`);
    if (err.message.includes("Quality check failed")) process.exit(2);
    if (err.message.includes("CDP")) process.exit(3);
    process.exit(1);
  }
}

main();

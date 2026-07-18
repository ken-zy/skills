import { parse } from "./parser";
import { qualityCheck } from "./quality";
import { getCleaners } from "./rules/cleaners";
import type { ParseResult, SiteRule } from "./types";

const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface FetchOptions {
  rule: SiteRule;
  timeout?: number;
  forceCdp?: boolean;
  cdpFetch?: (url: string, rule: SiteRule, timeout: number) => Promise<string>;
}

export async function fetchAndParse(url: string, options: FetchOptions): Promise<ParseResult & { fetchLevel: number }> {
  const { rule, timeout = 30000, forceCdp = false, cdpFetch } = options;
  const startLevel = forceCdp ? 2 : (rule.startLevel || 1);
  const cleaners = rule.cleaners ? getCleaners(rule.cleaners) : [];

  // Level 1: local fetch
  if (startLevel <= 1) {
    try {
      const response = await fetch(url, {
        headers: {
          "User-Agent": USER_AGENT,
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        signal: AbortSignal.timeout(timeout),
      });

      if (response.ok) {
        const html = await response.text();
        const result = parse(html, url, cleaners);
        const qc = qualityCheck(result.markdown);

        if (qc.pass) {
          return { ...result, fetchLevel: 1 };
        }
        console.error(`[L1] Quality check failed: ${qc.reason}`);
      } else {
        console.error(`[L1] HTTP ${response.status}`);
      }
    } catch (err) {
      console.error(`[L1] Fetch error: ${(err as Error).message}`);
    }
  }

  // Level 2: CDP
  if (!cdpFetch) {
    throw new Error("CDP fetch not available. Install Chrome and ensure remote debugging is enabled.");
  }

  console.error("[L2] Falling through to CDP...");
  const html = await cdpFetch(url, rule, timeout);
  const result = parse(html, url, cleaners);
  const qc = qualityCheck(result.markdown);

  if (qc.pass) {
    return { ...result, fetchLevel: 2 };
  }

  throw new Error(`Quality check failed at Level 2: ${qc.reason} (${qc.stats?.charCount} chars, ${qc.stats?.usefulParagraphs} useful paragraphs)`);
}

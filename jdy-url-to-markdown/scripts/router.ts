import siteRulesJson from "./rules/site-rules.json";
import type { SiteRule, SiteRules } from "./types";

const siteRules: SiteRules = siteRulesJson as SiteRules;

const aliasMap = new Map<string, string>();
for (const [pattern, rule] of Object.entries(siteRules)) {
  if (rule.aliases) {
    for (const alias of rule.aliases) {
      aliasMap.set(alias.toLowerCase(), pattern);
    }
  }
}

function normalizeHost(host: string): string {
  let h = host.toLowerCase();
  if (h.startsWith("www.")) h = h.slice(4);
  return h;
}

export function matchSiteRule(url: string): SiteRule | null {
  const parsed = new URL(url);
  const host = normalizeHost(parsed.hostname);

  // 1. Exact match
  if (siteRules[host]) return siteRules[host];
  if (siteRules[parsed.hostname.toLowerCase()]) return siteRules[parsed.hostname.toLowerCase()];

  // 2. Suffix match: *.domain.com
  for (const [pattern, rule] of Object.entries(siteRules)) {
    if (!pattern.startsWith("*.")) continue;
    const suffix = pattern.slice(2);
    if (host === suffix || host.endsWith("." + suffix)) {
      return rule;
    }
  }

  // 3. Alias match
  const aliasKey = aliasMap.get(host) || aliasMap.get(parsed.hostname.toLowerCase());
  if (aliasKey) return siteRules[aliasKey];

  return null;
}

export function getDefaultRule(): SiteRule {
  return { startLevel: 1 };
}

import type { Cleaner } from "../types";

function wechat(markdown: string): string {
  let md = markdown;
  const previewIdx = md.indexOf("预览时标签不可点");
  if (previewIdx !== -1) md = md.slice(0, previewIdx).trimEnd();
  const rewardIdx = md.indexOf("微信扫一扫赞赏作者");
  if (rewardIdx !== -1) md = md.slice(0, rewardIdx).trimEnd();

  const lines = md.split("\n");
  if (lines[0]?.startsWith("# ")) {
    const headingText = lines[0].slice(2).trim();
    let nextIdx = 1;
    while (nextIdx < lines.length && !lines[nextIdx].trim()) nextIdx++;
    if (nextIdx < lines.length && lines[nextIdx].trim() === headingText) {
      lines.splice(nextIdx, 1);
      md = lines.join("\n");
    }
  }

  md = md.replace(/^原创\s+.+$/gm, "").replace(/^\n+/, "");
  return md.trimEnd();
}

function zhihu(markdown: string): string {
  let md = markdown;
  md = md.replace(/^.*登录后你可以.*$/gm, "");
  md = md.replace(/^.*推荐阅读.*$/gm, "");
  md = md.replace(/^.*(发布于|编辑于)\s+\d{4}-?\d{2}-?\d{2}.*$/gm, "");
  md = md.replace(/\n{3,}/g, "\n\n");
  return md.trim();
}

function xiaohongshu(markdown: string): string {
  let md = markdown;
  md = md.replace(/^.*打开APP.*$/gm, "");
  md = md.replace(/^.*下载小红书.*$/gm, "");
  md = md.replace(/^.*小红书App.*$/gm, "");
  md = md.replace(/\n{3,}/g, "\n\n");
  return md.trim();
}

const registry: Record<string, Cleaner> = { wechat, zhihu, xiaohongshu };

export function getCleaner(name: string): Cleaner | null {
  return registry[name] || null;
}

export function getCleaners(names: string[]): Cleaner[] {
  return names.map(n => getCleaner(n)).filter((c): c is Cleaner => c !== null);
}

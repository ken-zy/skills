export interface Metadata {
  url: string;
  title: string;
  author?: string;
  published?: string;
  site_name?: string;
  description?: string;
}

export interface ParseResult {
  markdown: string;
  metadata: Metadata;
}

export interface QualityResult {
  pass: boolean;
  reason?: string;
  stats?: {
    charCount: number;
    usefulParagraphs: number;
  };
}

export interface SiteRule {
  startLevel?: number;
  adapter?: string;
  aliases?: string[];
  cdpActions?: string[];
  cleaners?: string[];
}

export type SiteRules = Record<string, SiteRule>;

export type Cleaner = (markdown: string) => string;

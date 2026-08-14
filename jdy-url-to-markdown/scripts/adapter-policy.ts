import type { ImageMode } from "./media/persist-images";
import type { SiteRule } from "./types";

export function shouldFailClosedOnAdapterError(
  rule: SiteRule,
  imageMode: ImageMode,
): boolean {
  return imageMode === "piclist" && rule.requireAdapterForPicList === true;
}

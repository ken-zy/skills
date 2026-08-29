import type { ImageMode } from "./media/persist-images";
import type { SiteRule } from "./types";

export function shouldFailClosedOnAdapterError(
  rule: SiteRule,
  imageMode: ImageMode,
): boolean {
  return (imageMode === "piclist" || imageMode === "r2")
    && rule.requireAdapterForPicList === true;
}

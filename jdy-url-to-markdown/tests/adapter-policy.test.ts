import { describe, expect, test } from "bun:test";
import { shouldFailClosedOnAdapterError } from "../scripts/adapter-policy";

describe("shouldFailClosedOnAdapterError", () => {
  test("requires the configured adapter for PicList archives", () => {
    expect(shouldFailClosedOnAdapterError({
      adapter: "wechat",
      requireAdapterForPicList: true,
    }, "piclist")).toBe(true);
  });

  test("requires the configured adapter for R2 script archives", () => {
    expect(shouldFailClosedOnAdapterError({
      adapter: "wechat",
      requireAdapterForPicList: true,
    }, "r2")).toBe(true);
  });

  test("allows generic fallback outside PicList mode", () => {
    const rule = {
      adapter: "wechat",
      requireAdapterForPicList: true,
    };
    expect(shouldFailClosedOnAdapterError(rule, "remote")).toBe(false);
    expect(shouldFailClosedOnAdapterError(rule, "none")).toBe(false);
  });
});

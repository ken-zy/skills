import { describe, expect, test } from "bun:test";
import { DEFAULT_PREFERENCES, parseExtend } from "../scripts/config";

describe("parseExtend", () => {
  test("parses image persistence preferences", () => {
    expect(parseExtend(`
default_output_dir: 40_Reference/Articles
default_timeout: 45000
default_image_mode: piclist
piclist_endpoint: http://127.0.0.1:36677/upload
persistent_image_hosts: img.jdy.systems, cdn.example.com
`)).toEqual({
      defaultOutputDir: "40_Reference/Articles",
      defaultTimeout: 45000,
      defaultImageMode: "piclist",
      piclistEndpoint: "http://127.0.0.1:36677/upload",
      persistentImageHosts: ["img.jdy.systems", "cdn.example.com"],
    });
  });

  test("rejects an unknown image mode", () => {
    expect(() => parseExtend("default_image_mode: local"))
      .toThrow("Invalid default_image_mode");
  });

  test("keeps remote images by default", () => {
    expect(DEFAULT_PREFERENCES.defaultImageMode).toBe("remote");
  });
});

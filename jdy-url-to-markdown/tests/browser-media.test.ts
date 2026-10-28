import { expect, test } from "bun:test";
import { selectBrowserStream } from "../scripts/adapters/browser_media_select";

test("preserves an exposed audio track instead of choosing smaller silent HEVC", () => {
  const result = selectBrowserStream([
    { masterUrl: "http://sns-video-v3.xhscdn.com/silent", width: 720, height: 1280, size: 24, audioChannels: 0 },
    { masterUrl: "http://sns-video-v3.xhscdn.com/sound", width: 720, height: 1280, size: 35, audioChannels: 2 },
  ]);
  expect(result.expectsAudio).toBe(true);
  expect(result.stream.masterUrl).toBe("https://sns-video-v3.xhscdn.com/sound");
});

test("genuinely silent sources remain valid and unapproved hosts are rejected", () => {
  const result = selectBrowserStream([
    { masterUrl: "https://evil.test/a", audioChannels: 2 },
    { masterUrl: "https://xhscdn.com.evil.test/a", audioChannels: 2 },
    { masterUrl: "https://sns-video-v3.xhscdn.com/silent", width: 720, height: 1280, audioChannels: 0 },
  ]);
  expect(result.expectsAudio).toBe(false);
  expect(result.stream.masterUrl).toEndWith("/silent");
});

test("the browser expression embeds a callable selector with identical behavior", () => {
  const embedded = new Function(`return (${selectBrowserStream.toString()})`)();
  const result = embedded([{ masterUrl: "https://sns-video-v3.xhscdn.com/v", audioBitrate: 64000 }]);
  expect(result.expectsAudio).toBe(true);
});

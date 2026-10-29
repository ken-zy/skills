import { expect, test } from "bun:test";
import { selectBrowserStream, selectVimeoDownload } from "../scripts/adapters/browser_media_select";

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

test("Vimeo official downloads honor actual portrait height and video identity", () => {
  const rows = [
    { url: "https://player.vimeo.com/progressive_redirect/download/123/rendition/720p/file.mp4?sig=opaque", text: "720p\n15MB\n720 x 1280" },
    { url: "https://player.vimeo.com/progressive_redirect/download/123/rendition/360p/file.mp4?sig=opaque", text: "360p\n5MB\n360 x 640" },
    { url: "https://player.vimeo.com/progressive_redirect/download/999/rendition/480p/file.mp4", text: "480p\n5MB\n640 x 480" },
  ];
  const embedded = new Function(`return (${selectVimeoDownload.toString()})`)();
  expect(embedded(rows, "123", "720").height).toBe(640);
  expect(selectVimeoDownload(rows, "123", "best").height).toBe(1280);
  expect(selectVimeoDownload(rows, "123", "480")).toBeUndefined();
  expect(selectVimeoDownload([{ url: "https://evil.test/video.mp4", text: "640 x 480" }], "123", "720")).toBeUndefined();
});

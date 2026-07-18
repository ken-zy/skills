import { describe, expect, test } from "bun:test";
import { qualityCheck } from "../scripts/quality";

describe("qualityCheck", () => {
  test("passes for content with sufficient length and paragraphs", () => {
    const markdown = [
      "# Article Title",
      "",
      "This is the first paragraph with enough words to be considered useful content for the quality check.",
      "",
      "This is the second paragraph that also contains enough words to pass the useful paragraph threshold.",
      "",
      "And a third paragraph for good measure with plenty of words inside it to meet requirements.",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
    expect(result.stats!.usefulParagraphs).toBeGreaterThanOrEqual(2);
  });

  test("fails for content shorter than 120 chars", () => {
    const result = qualityCheck("Short text.");
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("too short");
  });

  test("fails for anti-scraping markers", () => {
    const markdown = "# Page\n\nAccess Denied\n\nYou do not have permission to access this resource. This page is protected and requires authentication to view its contents. Please try again later.";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("anti-scraping");
  });

  test("fails for login wall markers", () => {
    const markdown = "# Welcome\n\n请登录后查看完整内容。\n\n更多精彩内容等你来看。请登录以继续访问本站的全部文章和资源，注册会员可以享受更多权益。本平台提供海量优质内容，登录后即可无限浏览所有文章和视频资源。立即免费注册，开启阅读之旅，探索无限精彩内容吧。";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("login wall");
  });

  test("does not false-positive on Chinese articles mentioning login", () => {
    const markdown = [
      "# 企业 SSO 登录指南",
      "",
      "本文档介绍如何在企业系统中配置单点登录功能。管理员需要先在后台配置身份提供商的相关信息和参数。",
      "",
      "用户在首次使用时需要请登录企业门户网站，完成初始化设置。配置完成后即可使用统一身份认证访问所有内部系统。",
      "",
      "如遇到问题请联系系统管理员获取帮助，常见问题包括证书过期和域名配置错误。请确保使用最新版本的浏览器。",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
  });

  test("fails for content with only 1 useful paragraph", () => {
    const markdown = [
      "# Title",
      "",
      "This is the only real paragraph with enough words to be considered useful content by the quality checker.",
      "",
      "![image](https://example.com/img.png)",
      "",
      "## Another heading",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("paragraph");
  });

  test("counts Chinese characters correctly for useful paragraph", () => {
    const markdown = [
      "# 标题",
      "",
      "这是一段足够长的中文段落，包含了超过十五个中文字符，应该被认为是有用的段落内容。",
      "",
      "另一段中文内容，同样包含了足够多的中文字符，可以通过质量检查的标准，确保内容质量。",
      "",
      "第三段补充内容，进一步增加文章的字符总数，使其满足最低长度要求，达到一百二十个字符。",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
    expect(result.stats!.usefulParagraphs).toBeGreaterThanOrEqual(2);
  });

  test("rejects navigation fragments (link lists without prose)", () => {
    const markdown = [
      "# Site",
      "",
      "This is a paragraph with enough words to be considered potentially useful for content on this website.",
      "",
      "[Home](/) [About](/about) [Contact](/contact) [Blog](/blog)",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("paragraph");
  });

  test("detects Cloudflare challenge page", () => {
    const markdown = "# Checking your browser\n\nJust a moment...\n\nPlease wait while we verify your connection. This process is automatic and your browser will redirect you once completed successfully.";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("anti-scraping");
  });

  test("does not false-positive on articles mentioning 'log in' or 'subscribe'", () => {
    const markdown = [
      "# How to Log In to AWS Console",
      "",
      "This guide explains how to log in to your AWS account using the management console for the first time.",
      "",
      "First, navigate to the AWS sign-in page and enter your root account email address and password to proceed.",
      "",
      "Subscribe to our newsletter for weekly updates on cloud computing tips and best practices for developers.",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
  });

  test("detects actual login wall with action verbs", () => {
    const markdown = "# Article\n\nLog in to view this article and unlock full access to all premium content on our platform today.\n\nSubscribe to read the complete story and get unlimited access to all articles published on this website.";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("login wall");
  });
});

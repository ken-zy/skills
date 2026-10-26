import { test, expect } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { DraftSession, assertSupportedMedia, readOriginalMetadata, validateSourceUrl, type DraftArticle } from "./wechat-draft.ts";
import { createWechatApiClient } from "./wechat-network.ts";

const source = "/fixture/article.md";
const account = "fake-account";
const article: DraftArticle = { title: "215. Test", content: "<p>body</p>", thumb_media_id: "full-image", thumb_url: "https://mmbiz.qpic.cn/full", author: "Author", need_open_comment: 1, only_fans_can_comment: 0, cover_info: { crop_percent_list: [{ ratio: "1_1", x1: "0.2" }] }, content_source_url: "https://video.example/one.mp4" };
function fixture(initial?: DraftArticle) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wechat-receipt-test-"));
  const file = path.join(dir, "receipt.json");
  let live = initial && structuredClone(initial);
  const calls: { endpoint: string; body: any; proxy: unknown }[] = [];
  let beforeUpdate: (() => void) | undefined;
  let corruptWrite = false;
  let dropAfterCommit = false;
  let rejection: number | string | undefined;
  const client = createWechatApiClient({ proxy: "http://127.0.0.1:17993", expectedEgressIp: "95.169.12.176" }, async (url, init) => {
    const endpoint = new URL(url).pathname;
    const body = JSON.parse(String(init?.body));
    calls.push({ endpoint, body, proxy: init?.proxy });
    if (endpoint.endsWith("/get")) return Response.json({ news_item: [live] });
    if (rejection !== undefined) return Response.json({ errcode: rejection, errmsg: "fake rejected request" });
    beforeUpdate?.();
    if (endpoint.endsWith("/add")) { live = structuredClone(body.articles[0]); return Response.json({ media_id: "draft-1" }); }
    if (endpoint.endsWith("/update")) { live = { ...live, ...structuredClone(body.articles) }; if (corruptWrite) live.content = "Platform altered body"; if (dropAfterCommit) throw new Error("Connection dropped after commit"); return Response.json({ errcode: 0 }); }
    throw new Error("Unexpected test request");
  });
  return { file, client, calls, reject: (value?: number | string) => { rejection = value; }, corrupt: () => { corruptWrite = true; }, drop: () => { dropAfterCommit = true; }, open: () => DraftSession.open(file, source, account), mutate: (patch: Partial<DraftArticle>) => { live = { ...live!, ...patch }; }, failWrites: () => { beforeUpdate = () => { throw new Error("fake timeout with fake-token"); }; }, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

test("read-original metadata handles precedence inputs, conflict and unsafe schemes", () => {
  expect(readOriginalMetadata("<!-- 公众号阅读原文: https://v.example/v.mp4 -->")).toBe("https://v.example/v.mp4");
  expect(readOriginalMetadata("no metadata")).toBeUndefined();
  expect(() => readOriginalMetadata("<!-- 公众号阅读原文: https://a.test -->\n<!-- 公众号阅读原文: https://b.test -->")).toThrow("Conflicting");
  for (const value of ["javascript:alert(1)", "file:///tmp/video", "https://user:secret@example.com"]) expect(() => validateSourceUrl(value)).toThrow();
  expect(validateSourceUrl("")).toBe("");
});

test("reject unsupported native video before upload; ordinary references are allowed", () => {
  for (const html of ['<iframe src="wxv"></iframe>', '<video src="v.mp4">', '<mpvideo>', '<span data-mpvid="apiv_1">']) expect(() => assertSupportedMedia(html)).toThrow("unverified");
  expect(() => assertSupportedMedia('<a href="https://v.example/v.mp4">观看宣传片</a>')).not.toThrow();
});

test("create/readback then rerun reuses draft and emits honest status; receipt has private permissions", async () => {
  const f = fixture();
  try {
    let s = f.open();
    expect(await s.prepare("fake-token", f.client)).toBeUndefined();
    const first = await s.save(article, "fake-token", f.client);
    expect(first).toMatchObject({ operation: "created", status: "draft_verified", published: false });
    s.close();
    s = f.open();
    const live = await s.prepare("fake-token", f.client);
    expect((await s.save(live!, "fake-token", f.client)).operation).toBe("unchanged");
    s.close();
    expect(f.calls.filter(x => x.endpoint.endsWith("/add"))).toHaveLength(1);
    expect(fs.statSync(f.file).mode & 0o777).toBe(0o600);
    expect(fs.readFileSync(f.file, "utf8")).not.toContain("fake-token");
    for (const call of f.calls) expect(call.proxy).toEqual({ url: "http://127.0.0.1:17993", respectNoProxy: false });
  } finally { f.cleanup(); }
});

test("in-place update preserves cover crop, author, flags, source URL and draft ID", async () => {
  const f = fixture(article); const s = f.open();
  try {
    const live = await s.prepare("fake-token", f.client, "draft-1");
    const result = await s.save({ ...live!, content: "<p>new body</p>" }, "fake-token", f.client);
    expect(result).toMatchObject({ media_id: "draft-1", operation: "updated" });
    const write = f.calls.find(x => x.endpoint.endsWith("/update"))!;
    expect(write.body.index).toBe(0);
    const { thumb_url, ...expected } = article;
    expect(write.body.articles).toMatchObject({ ...expected, content: "<p>new body</p>" });
    expect(f.calls.some(x => x.endpoint.endsWith("/add"))).toBe(false);
    const again = await s.prepare("fake-token", f.client);
    await s.save({ ...again!, content_source_url: "" }, "fake-token", f.client);
    expect((await s.prepare("fake-token", f.client))!.content_source_url).toBe("");
  } finally { s.close(); f.cleanup(); }
});

test("remote manual edits block updates; explicit reconciliation retains current metadata and backup", async () => {
  const f = fixture(article); let s = f.open();
  try {
    await s.prepare("fake-token", f.client, "draft-1"); s.close();
    f.mutate({ author: "Mobile author", content: "Mobile body", only_fans_can_comment: 1 });
    s = f.open();
    await expect(s.prepare("fake-token", f.client)).rejects.toThrow("Draft changed");
    expect(f.calls.some(x => x.endpoint.endsWith("/update"))).toBe(false);
    const live = await s.prepare("fake-token", f.client, undefined, true);
    await s.save({ ...live!, content: "Merged local and mobile body" }, "fake-token", f.client);
    expect(f.calls.find(x => x.endpoint.endsWith("/update"))!.body.articles.author).toBe("Mobile author");
    expect(fs.readdirSync(path.dirname(f.file)).some(x => x.includes("before-adopt"))).toBe(true);
  } finally { s.close(); f.cleanup(); }
});

test("detect concurrent editor change after image preparation, before write", async () => {
  const f = fixture(article); const s = f.open();
  try {
    const live = await s.prepare("fake-token", f.client, "draft-1");
    f.mutate({ digest: "Changed during upload" });
    await expect(s.save({ ...live!, content: "new" }, "fake-token", f.client)).rejects.toThrow("while preparing");
    expect(f.calls.some(x => x.endpoint.endsWith("/update"))).toBe(false);
  } finally { s.close(); f.cleanup(); }
});

test("mobile missing cover ID can reuse known original only when image URL still matches", async () => {
  const f = fixture(article); let s = f.open();
  try {
    await s.prepare("fake-token", f.client, "draft-1"); s.close();
    f.mutate({ thumb_media_id: "" }); s = f.open();
    const live = await s.prepare("fake-token", f.client, undefined, true);
    expect(s.recoverCover(live!)).toBe("full-image");
    await s.save({ ...live!, thumb_media_id: s.recoverCover(live!), content: "new" }, "fake-token", f.client);
  } finally { s.close(); f.cleanup(); }
  const other = fixture({ ...article, thumb_media_id: "", thumb_url: "https://mmbiz.qpic.cn/different-crop" }); const t = other.open();
  try {
    const live = await t.prepare("fake-token", other.client, "draft-2");
    expect(t.recoverCover(live!)).toBe("");
    await expect(t.save({ ...live!, content: "new" }, "fake-token", other.client)).rejects.toThrow("Permanent article cover ID missing");
    expect(other.calls.some(x => x.endpoint.endsWith("/update"))).toBe(false);
  } finally { t.close(); other.cleanup(); }
});

test("uncertain creation is persisted and cannot create a duplicate on retry", async () => {
  const f = fixture(); let s = f.open();
  try {
    f.failWrites();
    await expect(s.save(article, "fake-token", f.client)).rejects.toThrow("network or response failure");
    s.close(); s = f.open();
    await expect(s.prepare("fake-token", f.client)).rejects.toThrow("outcome unknown");
    expect(f.calls.filter(x => x.endpoint.endsWith("/add"))).toHaveLength(1);
  } finally { s.close(); f.cleanup(); }
});

test("readback mismatch does not claim success or blindly overwrite on retry", async () => {
  const f = fixture(article); let s = f.open();
  try {
    const live = await s.prepare("fake-token", f.client, "draft-1");
    f.corrupt();
    await expect(s.save({ ...live!, content: "new" }, "fake-token", f.client)).rejects.toThrow("readback differs");
    s.close(); s = f.open();
    await expect(s.prepare("fake-token", f.client)).rejects.toThrow("outcome unresolved");
    expect(f.calls.filter(x => x.endpoint.endsWith("/update"))).toHaveLength(1);
  } finally { s.close(); f.cleanup(); }
});

test("connection drops after update commit: readback recovers without another update", async () => {
  const f = fixture(article); let s = f.open();
  try {
    const live = await s.prepare("fake-token", f.client, "draft-1");
    f.drop();
    await expect(s.save({ ...live!, content: "new" }, "fake-token", f.client)).rejects.toThrow("network or response failure");
    s.close(); s = f.open();
    const saved = await s.prepare("fake-token", f.client);
    expect(saved!.content).toBe("new");
    expect((await s.save(saved!, "fake-token", f.client)).operation).toBe("unchanged");
    expect(f.calls.filter(x => x.endpoint.endsWith("/update"))).toHaveLength(1);
  } finally { s.close(); f.cleanup(); }
});

test("receipt lock and account/source binding prevent concurrent or cross-article reuse", () => {
  const f = fixture(); const s = f.open();
  try {
    s.recordUpload("hash", { media_id: "image-1", url: "https://mmbiz.qpic.cn/image" });
    expect(() => f.open()).toThrow(); s.close();
    expect(() => DraftSession.open(f.file, source, "other-account")).toThrow("identity");
    expect(() => DraftSession.open(f.file, "/other.md", account)).toThrow("identity");
    const t = f.open(); expect(t.cachedUpload("hash")?.media_id).toBe("image-1"); t.close();
  } finally { s.close(); f.cleanup(); }
});


test("explicit API rejection clears pending for create and update, allowing corrected requests", async () => {
  for (const initial of [undefined, article]) {
    const f = fixture(initial); let s = f.open();
    try {
      const live = await s.prepare("fake-token", f.client, initial ? "draft-1" : undefined);
      f.reject(40007);
      await expect(s.save({ ...(live || article), content: "corrected body", thumb_media_id: "bad-cover" }, "fake-token", f.client)).rejects.toThrow("error 40007");
      expect(JSON.parse(fs.readFileSync(f.file, "utf8")).pending).toBeUndefined();
      s.close(); s = f.open();
      f.reject(undefined);
      const next = await s.prepare("fake-token", f.client);
      expect(next?.content).toBe(initial?.content);
      const saved = await s.save({ ...(next || article), content: "corrected body", thumb_media_id: "full-image" }, "fake-token", f.client);
      expect(saved.operation).toBe(initial ? "updated" : "created");
      expect(JSON.parse(fs.readFileSync(f.file, "utf8")).pending).toBeUndefined();
    } finally { s.close(); f.cleanup(); }
  }
});

test("malformed API rejection cannot clear a potentially unconfirmed write", async () => {
  const f = fixture(); let s = f.open();
  try {
    f.reject("40007");
    await expect(s.save(article, "fake-token", f.client)).rejects.toThrow("error invalid");
    expect(JSON.parse(fs.readFileSync(f.file, "utf8")).pending.operation).toBe("create");
    s.close(); s = f.open();
    await expect(s.prepare("fake-token", f.client)).rejects.toThrow("outcome unknown");
    expect(f.calls.filter(x => x.endpoint.endsWith("/add"))).toHaveLength(1);
  } finally { s.close(); f.cleanup(); }
});

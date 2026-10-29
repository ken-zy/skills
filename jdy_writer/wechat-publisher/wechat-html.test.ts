import { test, expect } from 'bun:test';
import { sameWechatHtml, normalizeWechatHtml } from './wechat-html.ts';
const image = 'https://mmbiz.qpic.cn/mmbiz_jpg/AbC123/0?from=appmsg';
const original = `<p><img src="${image}" alt="a > b" style="width:100%"><br>今天PF发布了代币经济学</p><table><tr><td style="text-align:left;">35%</td></tr></table><hr class="hr">`;
const platform = original.replace('src=', 'data-src=').replace('/0?', '/640?').replace('<br>', '<br></br>').replace('<hr class="hr">', '<hr class="hr"></hr>');
test('observed platform changes preserve body, image identity, attributes and tables', () => {
  expect(sameWechatHtml(original, platform)).toBe(true);
  expect(normalizeWechatHtml(platform)).toBe(original);
  expect(sameWechatHtml(original, original.replace('<br>', '<br  />').replace('<hr class="hr">', '<hr class="hr" />'))).toBe(true);
});
test('reject changes to number, body, cover-like image, query, host, table, style, links and whitespace', () => {
  for (const altered of [platform.replace('35%', '100%'), platform.replace('今天', '昨天'), platform.replace('AbC123','Another'), platform.replace('from=appmsg','from=other'), platform.replace('mmbiz.qpic.cn','mmbiz.qpic.cn.evil.test'), platform.replace('text-align:left','text-align:right'), platform.replace('<td ', '<th '), platform.replace('</p>', ' </p>'), platform + '<a href="https://evil.test">x</a>']) expect(sameWechatHtml(original, altered)).toBe(false);
  expect(sameWechatHtml('<a href="https://a.test">x</a>', '<a href="https://b.test">x</a>')).toBe(false);
});
test('do not normalize markup inside comments, raw text, escaped code, or image alt values', () => {
  for (const wrapper of [(s:string)=>`<!--${s}-->`, (s:string)=>`<script>${s}</script>`, (s:string)=>`<style>${s}</style>`, (s:string)=>`<textarea>${s}</textarea>`, (s:string)=>`<!--${s}`, (s:string)=>`<script>${s}`, (s:string)=>`<img src="${image}" alt='${s}'>`]) {
    expect(sameWechatHtml(wrapper('<br>'), wrapper('<br></br>'))).toBe(false);
  }
  expect(sameWechatHtml('&lt;br&gt;', '&lt;br&gt;&lt;/br&gt;')).toBe(false);
  expect(sameWechatHtml('<br>x', '<br>x</br>')).toBe(false);
});
test('unknown image forms and duplicate attributes stay strict', () => {
  for (const src of ['https://img.example/mmbiz_jpg/AbC123/0', 'http://mmbiz.qpic.cn/mmbiz_jpg/AbC123/0', 'https://mmbiz.qpic.cn:443/mmbiz_jpg/AbC123/0', 'https://mmbiz.qpic.cn/other/AbC123/0']) {
    expect(sameWechatHtml(`<img src="${src}">`, `<img data-src="${src.replace('/0','/640')}">`)).toBe(false);
  }
  expect(sameWechatHtml(`<img src="${image}" src="${image}">`, `<img data-src="${image}" src="${image}">`)).toBe(false);
});

// Observed on a real draft readback: WeChat also issues sz_mmbiz image paths.
test('sz_mmbiz platform formatting preserves the exact image identity', () => {
  const source = original.replace('/mmbiz_jpg/', '/sz_mmbiz_jpg/');
  const live = platform.replace('/mmbiz_jpg/', '/sz_mmbiz_jpg/');
  expect(sameWechatHtml(source, live)).toBe(true);
  for (const altered of [
    live.replace('AbC123', 'Another'),
    live.replace('from=appmsg', 'from=other'),
    live.replace('/sz_mmbiz_jpg/', '/mmbiz_jpg/'),
    live.replace('/sz_mmbiz_jpg/', '/other_mmbiz_jpg/'),
    live.replace('35%', '100%'),
    live.replace('text-align:left', 'text-align:right'),
    live.replace('mmbiz.qpic.cn', 'mmbiz.qpic.cn.evil.test'),
  ]) expect(sameWechatHtml(source, altered)).toBe(false);
});

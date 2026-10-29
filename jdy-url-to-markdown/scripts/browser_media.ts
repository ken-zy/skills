// Read one public platform video through an explicitly selected browser.
// No cookie/storage APIs, login automation, arbitrary expressions or remote imports.
import { selectBrowserStream, selectVimeoDownload } from "./adapters/browser_media_select.ts";
const [endpoint, source, quality = "best"] = Deno.args;
const base = new URL(endpoint);
const post = new URL(source);
if (base.protocol !== "http:" || base.hostname !== "127.0.0.1" || !base.port || base.username || base.password || base.pathname !== "/") {
  throw new Error("Expected an explicitly authorized loopback CDP endpoint");
}
const reddit = ["reddit.com", "www.reddit.com"].includes(post.hostname) && /\/comments\/[a-z0-9]+\//i.test(post.pathname);
const douyin = ["douyin.com", "www.douyin.com"].includes(post.hostname) && /^\/video\/\d+/.test(post.pathname);
const xhs = ["xiaohongshu.com", "www.xiaohongshu.com"].includes(post.hostname) && /^\/(explore|discovery\/item)\/[a-z0-9]+/i.test(post.pathname);
const vimeo = ["vimeo.com", "www.vimeo.com"].includes(post.hostname) && /^\/\d+\/?$/.test(post.pathname);
if (post.protocol !== "https:" || !(reddit || douyin || xhs || vimeo)) throw new Error("Expected one supported platform video URL");
const allowedHosts = reddit ? ["reddit.com", "www.reddit.com"] : douyin ? ["douyin.com", "www.douyin.com"] : vimeo ? ["vimeo.com", "www.vimeo.com"] : ["xiaohongshu.com", "www.xiaohongshu.com"];
const requestedId = post.pathname.split("/").filter(Boolean).at(-1);
const tabs = await (await fetch(new URL("/json/list", base))).json();
const tab = tabs.find((t: { type: string; url: string }) => {
  if (t.type !== "page") return false;
  const url = new URL(t.url);
  return allowedHosts.includes(url.hostname) && (reddit || url.pathname.split("/").filter(Boolean).at(-1) === requestedId);
});
if (!tab) throw new Error("No matching platform page in the selected browser; ask the user to open it there");
const target = new URL(tab.webSocketDebuggerUrl);
if (target.protocol !== "ws:" || target.hostname !== "127.0.0.1" || target.port !== base.port) throw new Error("Unexpected browser target");
if (reddit) {
  post.pathname = post.pathname.replace(/\/?$/, "/") + ".json";
  post.search = "?raw_json=1&limit=0";
  post.hash = "";
}
const expression = reddit ? `(async()=>{
  if(!['reddit.com','www.reddit.com'].includes(location.hostname))return {ok:false,code:'wrong_browser_page'};
  const response=await fetch(${JSON.stringify(post.href)},{credentials:'include'});
  if(!response.ok)return {ok:false,code:response.status===401?'login_required':'browser_access_denied',http_status:response.status};
  const data=await response.json();
  const p=data?.[0]?.data?.children?.[0]?.data;
  const video=p?.secure_media?.reddit_video||p?.media?.reddit_video;
  if(!video?.dash_url)return {ok:false,code:'no_reddit_video'};
  const audioStatus=video.has_audio===true?'present':video.has_audio===false||video.is_gif===true?'absent':'unknown';
  return {ok:true,id:p.id,title:p.title,duration:video.duration,dash_url:video.dash_url,source_audio_status:audioStatus,expects_audio:audioStatus==='present'};
})()` : vimeo ? `(async()=>{
  if(!${JSON.stringify(allowedHosts)}.includes(location.hostname)||location.pathname.split('/').filter(Boolean).join('/')!==${JSON.stringify(requestedId)})return {ok:false,code:'wrong_video_page'};
  const dialog=()=>[...document.querySelectorAll('[role=dialog]')].find(d=>d.innerText.startsWith('Download video'));
  if(!dialog()){
    const button=document.querySelector('button[aria-label="Download button"]');
    if(!button)return {ok:false,code:'download_not_enabled'};
    button.click();
    for(let i=0;i<20&&!dialog();i++)await new Promise(r=>setTimeout(r,250));
  }
  for(let i=0;i<20&&!dialog()?.querySelector('a[aria-label="Download"]');i++)await new Promise(r=>setTimeout(r,250));
  const rows=[...(dialog()?.querySelectorAll('a[aria-label="Download"]')||[])].map(a=>({url:a.href,text:a.parentElement.innerText}));
  const select=${selectVimeoDownload.toString()};
  const selected=select(rows,${JSON.stringify(requestedId)},${JSON.stringify(quality)});
  if(!selected)return {ok:false,code:rows.length?'quality_limit':'download_not_ready'};
  const duration=[...document.querySelectorAll('video')].map(v=>v.duration).find(Number.isFinite);
  return {ok:true,id:${JSON.stringify(requestedId)},title:document.title.slice(0,180),duration,...selected,user_agent:navigator.userAgent,official_download:true};
})()` : `(()=>{
  if(!${JSON.stringify(allowedHosts)}.includes(location.hostname))return {ok:false,code:'wrong_browser_page'};
  const path=location.pathname.split('/').filter(Boolean);
  if(path.at(-1)!==${JSON.stringify(requestedId)})return {ok:false,code:'wrong_video_page'};
  if(${JSON.stringify(xhs)}){
    const n=window.__INITIAL_STATE__?.note?.noteDetailMap?.[${JSON.stringify(requestedId)}]?.note;
    if(n?.noteId!==${JSON.stringify(requestedId)})return {ok:false,code:'wrong_video_page'};
    const select=${selectBrowserStream.toString()};
    const {stream:s,expectsAudio}=select(Object.values(n.video?.media?.stream||{}).flat());
    if(!s)return {ok:false,code:'browser_video_not_ready'};
    return {ok:true,id:n.noteId,title:n.title||document.title,duration:n.video?.capa?.duration,media_url:s.masterUrl,width:s.width,height:s.height,user_agent:navigator.userAgent,expects_audio:expectsAudio};
  }
  const candidates=[...document.querySelectorAll('video')].filter(v=>v.currentSrc.startsWith('https:')&&Number.isFinite(v.duration)&&v.duration>0);
  if(candidates.length!==1)return {ok:false,code:candidates.length?'ambiguous_video':'browser_video_not_ready'};
  const v=candidates[0];
  return {ok:true,id:${JSON.stringify(requestedId)},title:document.title.replace(/\\s+/g,' ').slice(0,180),duration:v.duration,media_url:v.currentSrc,width:v.videoWidth,height:v.videoHeight,user_agent:navigator.userAgent};
})()`;
const socket = new WebSocket(target.href);
const response = await new Promise<unknown>((resolve, reject) => {
  const timer = setTimeout(() => { socket.close(); reject(new Error("Browser request timed out")); }, 45000);
  socket.onopen = () => socket.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression, awaitPromise: true, returnByValue: true } }));
  socket.onerror = () => { clearTimeout(timer); reject(new Error("Browser connection failed")); };
  socket.onmessage = (event) => {
    const message = JSON.parse(String(event.data));
    if (message.id !== 1) return;
    clearTimeout(timer);
    socket.close();
    if (message.result?.exceptionDetails || message.error) return resolve({ ok: false, code: "browser_read_failed" });
    resolve(message.result?.result?.value || { ok: false, code: "browser_read_failed" });
  };
});
console.log(JSON.stringify(response));

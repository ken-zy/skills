# FRED：通过内置浏览器读取官网

FRED 数据使用当前宿主的内置浏览器访问 `https://fred.stlouisfed.org/series/{series_id}`。在 Codex 中使用 `mcp__cua_repl.js` 控制 `iab`；不启动外部 Chrome、不使用 chrome-cdp 脚本，也不直接调用 FRED API / WebFetch / curl 或以搜索摘要代替页面数值。此路径不需要填写 FRED API Key。

## 调用步骤

1. 优先复用已知的 FRED 内置浏览器标签页；首次使用浏览器工具时按工具要求初始化，阅读返回的文档和页面状态。若需要新标签页，可调用：
   ```javascript
   const fredTab = await cua.createBrowserTab("iab", "https://fred.stlouisfed.org/series/CPIAUCSL", { visible: false });
   ```
   这是工具支持的入口示例，变量名可按会话调整。仅为采集数据时保持后台，用户要求展示页面时再显示。
2. 从网页可见内容读取序列名称与 ID、观测日期、数值、Units、Frequency、季调状态、Updated、Source。先使用可访问性树；页面内容不完整时，根据实际可见控件展开 Observations / View as data table，或使用工具支持的 DOM 快照。操作后读取新状态，不能复用过期元素编号，也不能仅凭图形目测数值。
3. 需要前值、同比或环比时，通过网页数据表、日期控件或网页下载按钮获得对应期间的值；不绕到隐藏接口取数。缺少必要历史值时标记无法计算。保留页面的指标口径，区分指数水平与变化率、月均值与日值；不因改换访问工具而改变序列含义。
4. 日历任务从页面的 Next Release Date / Release Calendar 链接进入并核实具体日期；只在页面明确给出时间和时区时引用，未给出的不推测。观测日期、页面更新时间、未来发布日期分别记录。
5. 输出附官网链接、序列 ID、数据期间、单位/频率/季调状态和读取时间；页面有更新时间时一并列出。页面缺值不能记作 0；数据可能修订，不把读取时间当作统计期或首次发布时间。

## 失败处理

- 内置浏览器工具不可用、页面加载失败或关键字段不可读时，说明具体阻塞；加载异常可刷新一次，仍失败就将对应数据标记为未获取，不编造数值。
- 不自动切换外部浏览器、FRED API 或 Web Search 数值。需要改用其他访问方式或数据源时，再征求用户意见；其他已可读取的指标可以继续完成。
- 仅读取公开数据，不为本任务注册账户、填写 Key 或改变登录配置。

本规则只替换 FRED 的访问方式。CoinGecko / Binance 双源价差规则、DefiLlama 及其他来源的既有访问方式不受影响。

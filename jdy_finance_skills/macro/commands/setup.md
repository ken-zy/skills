---
description: 检查 macro 所需的 CoinGecko / Binance 插件连接
allowed-tools: mcp__codex_apps__coingecko_*, mcp__codex_apps__binance_get_spot_*
---

# Macro Plugin Setup

检查当前宿主的 CoinGecko、Binance 插件工具是否已加载，并按[双源行情规则](../skills/macro-dashboard/references/plugin-market-data.md)实际查询 BTC 和换汇数据，报告可用、失败或缺失状态。工具前缀以当前宿主实际发现结果为准。

仅有工具列表不算连接可用。缺少插件时提示用户在当前应用中连接；会话终止则提示重新连接后测试。若插件要求认证，由用户在插件设置中处理。

macro 不再依赖 crypto 插件的本地 npx MCP。不接收密钥参数，不读取或修改 crypto/.mcp.json 或 ~/.indie-finance/keys.json，不向用户索取或自动复制 Key。此命令只检查连接，不自动安装插件或修改认证。

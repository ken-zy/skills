---
name: new-platform
description: 创建新的预测市场平台适配器
---

参考 `backend/app/platforms/opinion/` 实现，创建新平台：

1. 创建 `backend/app/platforms/{platform}/`
2. 实现 PlatformAdapter 接口
3. 注册到 platform_manager.py

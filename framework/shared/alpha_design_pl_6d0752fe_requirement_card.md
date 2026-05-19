# 🐢 需求卡片优化 — 设计文档

**Pipeline**: pl_6d0752fe  
**需求ID**: 6d0752fe-ff05-4db3-9cbe-34564d080c3b  
**设计时间**: 2026-05-17  
**作者**: Alpha 🐢

## What

需求列表 Tab 中每个需求卡片的状态标签从列级展示名改为独立的内部阶段中文名。

**改动前**：
```
需求A
🔧 开发阶段  |  🐢 阿尔法
```

**改动后**：
```
需求A
编码中  |  🐢 阿尔法
```

## Why

看板卡片已经通过 `PHASE_TO_CHINESE` 显示了中文内部状态（如"审查中"、"编码中"），但需求列表 Tab 中的 `statusLabels` 还是列级名（如"🔧 开发阶段"），两处不一致。用户期望看到精确的内部阶段状态。

## Tradeoff

- **方案A（采用）**：只改前端 `statusLabels` 映射表 + CSS badge 样式 → 快速，零后端变动
- **方案B**：后端 API 新增 `status_cn` 字段 → 更干净但需改 API 端点 + 测试
- **决策**：方案A，与看板改动的 `PHASE_TO_CHINESE` 保持一致

## Op

| 优先级 | 改动 | 文件 |
|--------|------|------|
| P0 | `statusLabels` 映射改为中文 phase 名 | `dev_center.js` |
| P0 | 补充 phase 级 CSS badge 样式 | `dev_center.css` |

**共 2 处改动，零后端代码变动**

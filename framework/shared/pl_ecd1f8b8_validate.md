# Validate Report — pl_ecd1f8b8

**Task**: 成员管理界面各成员头像不正确  
**Requirement**: 21470d44-3b25-4d92-b9fd-f04867ef783d  
**Validator**: Alpha (🐢)  
**Date**: 2026-05-26  

---

## 可行性分析：✅ 可实现

该需求技术上完全可行。问题根因已定位。

### 根因

**Dashboard 中头像来源存在三重问题：**

#### 1. 静态 Avatar 文件分辨率错误

`dashboard/static/avatars/` 中活跃成员的 PNG 尺寸不正确：

| 文件 | 实际尺寸 | 应为尺寸 | 问题 |
|------|---------|---------|------|
| alpha.png | 1408×768 | 1024×1024 | ❌ 非正方形、压缩变形 |
| duci.png | 1408×768 | 1024×1024 | ❌ 同 alpha |
| panda.png | 512×512 | 1024×1024 | ⚠️ 正方形但分辨率偏低 |

真实源文件在 `agents/{member_id}/avatar.png` 中，全部为 1024×1024。

#### 2. 遗留成员头像未清理

| 文件 | 对应成员 | 状态 | 问题 |
|------|---------|------|------|
| gulu.png | 咕噜 | inactive | ❌ 已退出但仍存在于静态目录 |
| weaver.png | 织巢 | inactive | ❌ 已退出 |
| aeterna.png | 埃特娜 | inactive | ❌ 已退出 |
| stinger.png | — | ❌ 无此成员 | ❌ 完全错误的遗留 |

#### 3. `_serve_avatar()` 路径断裂

`/avatar/{member_id}` 路由按此顺序查找：
1. `AGENTS_DIR / member_id / "avatar.png"` → `PANDA_ROOT/agents/{member}/avatar.png`
   - `PANDA_ROOT = ~/workspace/members/panda`
   - `~/workspace/members/panda/agents/` **目录不存在**
   - → 恒走 fallback
2. `~/workspace/members/{member_id}/avatar.png`
   - alpha: ✅ 存在 (520KB)
   - duci: ✅ 存在 (172KB)
   - panda: ❌ 不存在 → 404

---

## 依赖项

| # | 依赖 | 状态 | 说明 |
|---|------|------|------|
| 1 | 活跃成员列表（前序 pl_2070b427 已修复） | ✅ 已就绪 | 仅需处理 panda/alpha/duci |
| 2 | agents/ 目录下源文件 | ✅ 存在 | 6 个成员均为 1024×1024 PNG |
| 3 | dashboard/static/avatars/ | ✅ 存在 | 需要替换 + 清理 |

---

## 风险点

| 风险 | 等级 | 说明 |
|------|------|------|
| 活跃成员头像替换后尺寸偏差 | 🟢 低 | 统一用 1024×1024 PNG，无需裁剪 |
| onerror fallback 未触发 | 🟢 低 | 《member-tab-card》使用 onerror → emoji，替换文件后正常加载 |
| /avatar/{member_id} 路径 | 🟡 中 | 被 stats tab 用，建议同步修复 |
| panda 无 avatar | 🟡 中 | `~/workspace/members/panda/` 下无 `avatar.png`，需从 `agents/panda/avatar.png` 补充 |

---

## 建议优先级：**P1**

**P1 理由：**
- ✅ 直接影响用户体验——成员管理 Tab 显示的头像变形/错误
- ✅ 修复量小（文件替换 + 路径修复），依赖已就绪
- ✅ 与已完成的 pl_2070b427（成员过滤）直接关联，过滤完成员后头像问题更明显
- ❌ 不影响 pipeline 调度和核心业务逻辑，不构成 P0

---

## 结论

**Pass** —— 需求清晰，根本原因明确为静态头像文件尺寸错误 + 路径断裂。建议同步清理遗留 inactive 成员的头像文件以防止未来混淆。

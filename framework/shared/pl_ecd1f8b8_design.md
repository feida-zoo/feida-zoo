# Design Report — pl_ecd1f8b8

**Task**: 成员管理界面各成员头像不正确  
**Requirement**: 21470d44-3b25-4d92-b9fd-f04867ef783d  
**Designer**: Alpha (🐢)  
**Date**: 2026-05-26  
**Input**: `pl_ecd1f8b8_validate.md`  

---

## What — 具体改动

### 问题三重性

| # | 问题 | 影响面 |
|---|------|--------|
| 1 | 静态头像文件尺寸错误 | 成员 Tab、看板——alpha 和 duci 头像变形 |
| 2 | `_serve_avatar()` 路径断裂 | 统计 Tab `/avatar/{id}` 返回 404（panda）或 fallback 路径不一致 |
| 3 | 遗留文件未清理 | stinger.png（无此成员）+ inactive 成员头像残留 |

### 改动方案

#### 改动 A：替换静态头像文件（零代码）

从 `agents/{id}/avatar.png`（1024×1024 正方形源文件）复制到 `dashboard/static/avatars/{id}.png`，覆盖现有错误文件。

| 操作 | 源文件 | 目标文件 |
|------|--------|---------|
| ✅ 替换 | `agents/alpha/avatar.png` | `dashboard/static/avatars/alpha.png` |
| ✅ 替换 | `agents/duci/avatar.png` | `dashboard/static/avatars/duci.png` |
| ✅ 替换 | `agents/panda/avatar.png` | `dashboard/static/avatars/panda.png` |

#### 改动 B：修复 `_serve_avatar()` 路径

当前 `AGENTS_DIR = PANDA_ROOT / "agents"` → `~/workspace/members/panda/agents/`（不存在）。

改为指向实际存在的 `agents/` 目录：

```python
# 定义常量前段加一行
PROJECT_AGENTS_DIR = PROJECT_ROOT / "agents"
```

```python
def _serve_avatar(self):
    member_id = ...
    # 优先从项目 agents/ 目录查找（统一权威源）
    avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"
    if avatar_path.exists():
        self._serve_file(avatar_path, 'image/png')
        return
    # fallback：成员自身目录
    fallback_path = Path("/Users/zoo/workspace/members") / member_id / "avatar.png"
    ...
```

#### 改动 C：清理遗留头像文件

| 删除文件 | 原因 |
|---------|------|
| `dashboard/static/avatars/stinger.png` | 无此成员 |
| `dashboard/static/avatars/gulu.png` | 成员 inactive |
| `dashboard/static/avatars/weaver.png` | 成员 inactive |
| `dashboard/static/avatars/aeterna.png` | 成员 inactive |

#### 改动 D：修复看板头像硬编码（可选）

前端 `dev_center.js` L743：

```js
// 当前：const avatarSrc = executor ? `/static/avatars/${executor === 'stinger' ? 'stinger' : executor}.png` : '';
// 改为：直接使用 executor id，统一走 /static/avatars/
const avatarSrc = executor ? `/static/avatars/${executor}.png` : '';
```

`stinger` 是历史内部名，对应现在的 `duci`。替换正确文件后不需要这个映射。

---

## Why — 背景与解决的问题

### 问题影响
- 成员管理 Tab 中 alpha、duci 头像显示为 1408×768 变形图像
- panda 头像 512×512 偏小，与其他成员（应为 1024×1024）不一致
- 统计 Tab 成员状态区头像路径走 `_serve_avatar()`，panda 返回 404
- 看板卡片的 assignee 头像硬编码 `stinger` 映射导致维护困扰
- 已退出成员的头像文件仍在目录中，产生数据不一致

### 根因
1. `dashboard/static/avatars/` 中的 PNG 文件来自早期阶段，使用了未裁剪的原始渲染图（1408×768）
2. `AGENTS_DIR` 路径写错——应指向 `/Users/zoo/workspace/code/feida_zoo/agents/`，而非 `/Users/zoo/workspace/members/panda/agents/`
3. 成员退出后未清理对应头像文件

---

## Tradeoff — 方案权衡

| 方案 | 描述 | 优点 | 缺点 | 决策 |
|------|------|------|------|------|
| **A（采纳）** | 替换文件 + 修路径 + 清理 | 零代码即可修复核心问题、路径修复防再生 | 改 A 需重启 dashboard | ✅ **最优**: 最小改动解决所有问题 |
| B | 全量走 `/avatar/` 动态路由 | 统一头像来源 | 需修改前端 3 处 img src、增加后端请求数 | ❌ 过度设计 |
| C | YAML 中配置 avatar 路径 | 灵活可配 | 所有成员需加字段，后端前端均需改 | ❌ 杀鸡用牛刀 |

---

## 接口定义

### 后端修改

#### `app_enhanced.py` — 新增常量 + 修改 _serve_avatar()

```python
# 在 PROJECT_ROOT 后、PANDA_ROOT 前，新增
PROJECT_AGENTS_DIR = PROJECT_ROOT / "agents"
```

```python
def _serve_avatar(self):
    member_id = ...
    # 优先从项目 agents/ 目录
    avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"
    if avatar_path.exists():
        self._serve_file(avatar_path, 'image/png')
        return
    # fallback
    fallback_path = Path("/Users/zoo/workspace/members") / member_id / "avatar.png"
    ...
```

### 前端修改

#### `dev_center.js` — 去除 stinger 硬编码（改动 D）

L743:
```js
// 改前
const avatarSrc = executor ? `/static/avatars/${executor === 'stinger' ? 'stinger' : executor}.png` : '';
// 改后
const avatarSrc = executor ? `/static/avatars/${executor}.png` : '';
```

### 文件替换（零代码操作）

```bash
cp agents/alpha/avatar.png dashboard/static/avatars/alpha.png
cp agents/duci/avatar.png  dashboard/static/avatars/duci.png
cp agents/panda/avatar.png dashboard/static/avatars/panda.png
rm dashboard/static/avatars/stinger.png
rm dashboard/static/avatars/gulu.png
rm dashboard/static/avatars/weaver.png
rm dashboard/static/avatars/aeterna.png
```

---

## 文件清单

### 文件替换

| 操作 | 文件 |
|------|------|
| 🔄 替换 | `dashboard/static/avatars/alpha.png` |
| 🔄 替换 | `dashboard/static/avatars/duci.png` |
| 🔄 替换 | `dashboard/static/avatars/panda.png` |
| 🗑 删除 | `dashboard/static/avatars/stinger.png` |
| 🗑 删除 | `dashboard/static/avatars/gulu.png` |
| 🗑 删除 | `dashboard/static/avatars/weaver.png` |
| 🗑 删除 | `dashboard/static/avatars/aeterna.png` |

### 代码修改

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `dashboard/app_enhanced.py` | +1 行常量 +3 行路径换 | `PROJECT_AGENTS_DIR` + `_serve_avatar()` |
| `dashboard/static/dev_center.js` | ~1 行 | 去除 stinger 硬编码 |

### 不变文件

| 文件 | 原因 |
|------|------|
| `framework/core/mesh/zoo_registry.py` | 无改动必要 |
| `framework/data/zoo_members.yaml` | 无改动必要 |
| `dashboard/templates/dev_center.html` | 无改动必要 |

---

## Open Questions

1. **`_get_member_data()` 中的 `avatar_exists` 检测是否仍有效？**  
   替换文件后，活跃成员的文件存在性检查仍然通过。删除 inactive 文件后，`avatar_exists` 对 inactive 成员返回 False，但因为 pl_2070b427 已过滤这些成员，不会进入返回值。✅

2. **看板头像尺寸自适应？**  
   当前 CSS 中 `.assignee-avatar-img` 限制为 20×20，新文件 1024×1024 会被 CSS 压缩，不会变形。✅

3. **重启 dashboard 时机？**  
   代码修改（改动 B/D）需要重启 dashboard 生效。文件替换（改动 A/C）重启后自动使用新文件。

---

## Next Action — 审计重点

请 **Duci** 重点审查以下三点：

1. **路径选择**：`PROJECT_AGENTS_DIR` 指向 `PROJECT_ROOT / "agents"`，确认该目录存在且包含所有活跃成员（检查通过）。

2. **fallback 保留**：`_serve_avatar()` 保留 `~/workspace/members/{id}/avatar.png` 作为 fallback，是否与 `agents/` 目录内容有冲突？建议保持 fallback（万一 agents/ 中文件缺失时还能显示用户个人目录的头像）。

3. **stinger 硬编码去除**：确认看板中 executor 字段返回的是 `duci` 而非 `stinger`，验证 Pipeline 任务数据中 assignee/executor 的 id 字段。

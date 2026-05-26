# UI Design：动物园成员信息配置化

**Pipeline ID:** pl_3833295c
**UI Design phase:** 2026-05-21
**Author:** Alpha (🐢)

---

## 前置声明

本任务为 **纯后端配置架构改造**，核心变动是将成员数据源从 5 个分散硬编码位置收敛到单一 `zoo_members.yaml`。Dashboard `/api/members` 接口的 JSON 响应格式 **保持不变**（见设计文档 §4.2），因此：

**前端零改动** —— 现有成员卡片网格直接适配新数据源。

以下 UI 设计仅记录为此确认过的事项，并无新的前端开发需求。

---

## 1. 页面布局（现状确认）

```
┌──────────────────────────────────────────────────────────┐
│  🐼 飝龘动物园 — 成员卡片网格                              │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  🐢 阿尔法 Alpha │  │  🦂 毒刺 Duci    │               │
│  │  状态: 🟢 活跃   │  │  状态: 🟡 空闲   │               │
│  │  种族: 玄龟      │  │  种族: 蝎子      │               │
│  │  角色: 首席架构师 │  │  角色: 无情审计师 │               │
│  │  模型: DeepSeek  │  │  模型: Minimax   │               │
│  └─────────────────┘  └─────────────────┘               │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  🐼 达达 Panda   │  │  ...            │               │
│  │  状态: 🟢 活跃   │  │                 │               │
│  │  种族: 熊猫      │  │                 │               │
│  │  角色: 中枢调度   │  │                 │               │
│  │  模型: Minimax   │  │                 │               │
│  │  (带"主用模型"    │  │                 │               │
│  │   ★ 标记)        │  │                 │               │
│  └─────────────────┘  └─────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

**卡片结构**（来自 `templates/index.html`，未改动）：

```
member-card (.status CSS class)
├── card-header
│   ├── avatar-container
│   │   ├── img.avatar-img     ← 静态图片 /static/avatars/{id}.png
│   │   └── div.avatar-fallback
│   │       └── span.avatar-emoji  ← 回退 Emoji
│   └── div.status-badge.{status}  ← 🟢活跃/🟡空闲/⚫离线
├── card-body
│   ├── h3.member-name         ← 展示名（name）
│   ├── p.member-code          ← 代号（code_name）
│   ├── div.info-row           ← 种族（species）
│   ├── div.info-row           ← 角色（role_display）
│   └── div.info-row           ← 模型（model）
│       └── span ★ 标记（仅主 Agent 显示）
└── card-footer
    └── p.description          ← 角色描述
```

**布局规则**：
- 网格布局 CSS Grid，自动换行
- 每行 3-4 张卡片，随视口宽度自适应
- 顶部加载中 spinner → 加载后显示网格

---

## 2. 交互逻辑（无变化）

所有交互保持现状：

| 操作 | 当前行为 | 改造后行为 |
|------|---------|-----------|
| 页面加载 | `GET /api/members` → 渲染成员卡 | 同上。数据源从 `MEMBERS_INFO` 改为 `zoo_members.yaml`，格式不变 |
| 状态更新 | 每 60s 后端 StatusManager 更新 → SSE 推送 `member_status` 事件 → 前端改状态点 | 同上。StatusManager 遍历来源从 `registry.json` 改为 `ZooRegistry.list_agents()` |
| 模型展示 | 显示 `member.model` 字符串 | 非主 Agent 同上；主 Agent 改为 `get_model_display()`（从 openclaw.json 解析 alias） |

---

## 3. 状态定义

### 3.1 卡片状态（status CSS class + badge text）

改造前后映射保持一致：

| ZooRegistry status | CSS class | Badge 文本 | 颜色 |
|-------------------|-----------|-----------|------|
| `online` | `active` | 🟢 活跃 | 绿色 |
| `idle` | `idle` | 🟡 空闲 | 黄色 |
| `busy` | `busy` | 🔴 忙碌 | 红色 |
| `dead` / `offline` / 其他 | `inactive` | ⚫ 离线 | 灰色 |

### 3.2 成员活跃状态（YAML → Dashboard 展示）

`zoo_members.yaml` 中 `metadata.status` 字段映射：

| YAML status | Dashboard 表现 |
|------------|---------------|
| `active` | 正常显示，状态跟随进程检活 |
| `inactive` | 正常显示（不隐藏），初始状态为 ⚫ 离线 |

> 设计决策：Weaver/Aeterna/Gulu 等 inactive 成员**不隐藏**，始终在看板中可见但标记为离线。隐藏会导致历史需求追踪困难。

### 3.3 模型展示状态

| 场景 | UI 表现 |
|------|--------|
| 非主 Agent，model 有 alias | 显示 alias（如 `DeepSeek`, `Minimax`） |
| 主 Agent（panda）| 显示 openclaw.json primary 的 alias + ★ 标记 |
| model 无 alias | 显示原始 model ID（如 `volcengine-plan/glm-5.1`） |
| openclaw.json 不可读 | 显示 `zoo_members.yaml` 中原始的 model ID |

---

## 4. 视觉说明

### 4.1 主 Agent 模型标记（★ 仅此处有前端改动）

在 panda 卡片「模型」行追加一个星标：

```diff
 <div class="info-row">
     <span class="info-label">模型</span>
-    <span class="info-value model">${member.model}</span>
+    <span class="info-value model">
+        ${member.model}
+        ${member.is_main_agent ? '<span class="primary-model-badge" title="主用模型">★ 主用模型</span>' : ''}
+    </span>
 </div>
```

对应的 CSS 追加：

```css
.primary-model-badge {
    display: inline-block;
    background: linear-gradient(135deg, #f6d365, #fda085);
    color: #333;
    font-size: 0.7em;
    padding: 2px 8px;
    border-radius: 10px;
    margin-left: 6px;
    font-weight: 600;
}
```

> 改动范围：`templates/index.html` 中 `renderMembers()` 函数 + `static/style.css`

### 4.2 风格说明

| 属性 | 值 |
|------|-----|
| UI 风格 | 极简卡片网格，暗色背景 |
| 主色 | `#1a1a2e`（背景）→ `#16213e`（卡片）渐变 |
| 强调色 | `#e94560`（活跃状态点）|
| 卡片圆角 | 16px |
| 字体 | 系统默认 sans-serif |
| 图标 | Emoji 原生（无图标库依赖）|

---

## 5. 文件清单（UI 相关）

| 文件 | 改动 |
|------|------|
| `dashboard/templates/index.html` | `renderMembers()` 中的模型行添加 `is_main_agent` 判断 + `★ 主用模型` 标记 |
| `dashboard/static/style.css` | 新增 `.primary-model-badge` CSS 类 |
| `dashboard/static/avatars/` | 新增 avatar 文件：`aeterna.png`, `gulu.png`, `weaver.png`（可选，不影响功能） |
| `dashboard/app_enhanced.py` | `/api/members` 响应新增 `is_main_agent` 字段 |

### 5.1 API 响应新增字段

```json
{
  "id": "panda",
  "name": "达达 Panda",
  "model": "Minimax",
  "is_main_agent": true,
  ...
}
```

此字段由 `ZooRegistry.get_full_info()` → `metadata.is_main_agent` 提供。

---

## 6. 交互流程（无变化）

```
[浏览器页面加载]
      │
      ▼
fetch('/api/members')
      │
      ▼
[后端] ZooRegistry → zoo_members.yaml → JSON 响应
      │
      ▼
[前端] renderMembers(members) → 生成卡片 HTML
      │
      ▼
[前端] SSE /events (member_status) → 定时状态更新
```

与改造前的唯一区别：**后端数据来源** 从 `MEMBERS_INFO` + `registry.json` 变为 `zoo_members.yaml`。前端无感知。

---

## 7. 结论

**UI 层面无结构性变化**。唯一的前端改动是 Panda 卡片的模型行添加 `★ 主用模型` 标记（约 3 行 template 代码 + 10 行 CSS），后端 API 响应追加一个 `is_main_agent` boolean 字段。

其余所有卡片字段（name, code_name, species, role_display, model, avatar_emoji, description, status）格式完全不变。

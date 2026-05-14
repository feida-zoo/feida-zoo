# Design Spec: 新增问题管理 Tab
**需求ID:** pl_b1a960ef | b1a960ef-1baa-477b-aef7-32434028130f  
**设计师:** Alpha (🐢 首席架构师)  
**状态:** 📋 待审核 (→ duci)

---

## 问题描述

需要一个独立的问题/Issue 管理 Tab，支持创建、查看和管理研发过程中遇到的问题。

## 设计方案

### 1. 前端 — 新增 Tab 按钮

**目标文件:** `dashboard/templates/dev_center.html`

在 tab-nav 中新增按钮：
```html
<button class="tab-btn" data-tab="issues" onclick="switchTab('issues')">
    🐛 <span>问题管理</span>
</button>
```

在 tab-content 区域新增：
```html
<div class="tab-content" id="tab-issues">
    <div class="issues-container">
        <div class="issues-header">
            <h2><i class="fas fa-bug"></i> 问题管理</h2>
            <button class="btn-create-issue" onclick="showCreateIssueForm()">
                <i class="fas fa-plus"></i> 新建问题
            </button>
        </div>
        <div class="issues-toolbar">
            <select id="issue-status-filter">
                <option value="all">全部状态</option>
                <option value="open">待处理</option>
                <option value="in_progress">处理中</option>
                <option value="resolved">已解决</option>
                <option value="closed">已关闭</option>
            </select>
            <select id="issue-priority-filter">
                <option value="all">全部优先级</option>
                <option value="P0">P0 紧急</option>
                <option value="P1">P1 高</option>
                <option value="P2">P2 中</option>
                <option value="P3">P3 低</option>
            </select>
            <input type="text" id="issue-search" placeholder="搜索问题..." />
        </div>
        <div class="issues-list" id="issues-list">
            <div class="loading"><div class="spinner"></div><p>加载中...</p></div>
        </div>
    </div>
</div>
```

### 2. 前端 — JS 逻辑

**目标文件:** `dashboard/static/dev_center.js`

新增函数：
- `switchTab('issues')` 分支：加载问题列表
- `loadIssues()` — GET `/api/issues` 渲染列表
- `showCreateIssueForm()` — 弹出新建表单的 modal
- `submitIssue()` — POST `/api/issues` 创建问题
- `updateIssueStatus(id, status)` — PUT `/api/issues/:id` 更新状态
- `deleteIssue(id)` — DELETE `/api/issues/:id` 删除

每个问题卡片展示：标题、描述、优先级 P0-P3（颜色标记）、状态（带颜色标签）、指派人、创建时间、操作按钮。

### 3. 后端 — API

**目标文件:** `dashboard/app_enhanced.py`

新增数据文件：`dashboard/data/issues.json`

API 路由：
- `GET /api/issues` — 返回所有问题（支持 status/priority 查询参数过滤）
- `POST /api/issues` — 创建新问题（title, description, priority, assignee）
- `PUT /api/issues/:id` — 更新问题状态/字段
- `DELETE /api/issues/:id` — 删除问题

Issue JSON 结构：
```json
{
    "id": "uuid",
    "title": "string",
    "description": "string",
    "priority": "P0|P1|P2|P3",
    "status": "open|in_progress|resolved|closed",
    "assignee": "string",
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime",
    "resolved_at": "ISO datetime|null",
    "source": "dashboard|pipeline"
}
```

### 4. 样式

**目标文件:** `dashboard/static/dev_center.css`

新增 `#tab-issues` 相关样式：
- issues-container 布局（flex column）
- issues-header 带标题和新建按钮
- issues-toolbar 筛选栏（水平排列）
- issues-list 列表（每个 issue 卡片带优先级色条）
- 优先级 P0(红)、P1(橙)、P2(黄)、P3(灰)
- 状态标签颜色：open(蓝)、in_progress(黄)、resolved(绿)、closed(灰)

## 影响范围
- `dashboard/templates/dev_center.html` — 新增 tab 按钮 + 内容区
- `dashboard/static/dev_center.js` — 新增 JS 函数
- `dashboard/static/dev_center.css` — 新增样式
- `dashboard/app_enhanced.py` — 新增 API 路由
- `dashboard/data/issues.json` — 新增数据文件（自动创建）

---

> **设计者:** Alpha 🐢  
> **请 Duci 审核此设计方案，审核通过后交由 Weaver 实施。**

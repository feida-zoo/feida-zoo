# 需求评审 + 架构设计文档
## pl_e024bd42 — 运行数据与代码数据隔离

---

## 1. 需求评审

### 1.1 问题描述

当前 Zoo Pipeline/Dashboard 的运行数据散落在多个目录，其中部分与代码工程混在一起：

| 当前路径 | 内容 | 问题 | 数据性质 |
|----------|------|------|----------|
| `feida_zoo/dashboard/data/issues.json` | issue 持久化数据 | ❌ 在代码工程内 | **运行数据** |
| `feida_zoo/dashboard/data/requirements.json` | requirement 持久化数据 | ❌ 在代码工程内 | **运行数据** |
| `feida_zoo/agents/*/avatar.png` | 成员头像 | ❌ 在代码工程内 | **配置数据**（运行时变更） |
| `feida_zoo/framework/shared/task_tracker.json` | Pipeline 任务跟踪 | ❌ 在代码工程内 | **运行数据** |
| `feida_zoo/framework/shared/pl_*.md` | Pipeline 阶段文档 | ❌ framework/shared 目录名不合适 | **项目文档** |
| `~panda/zoo_mesh/pipeline/pending.json` | Pipeline 待办队列 | ✅ 已隔离 | 运行数据 |
| `~panda/zoo_mesh/pipeline/state_*.json` | Pipeline 状态快照 | ✅ 已隔离 | 运行数据 |

### 1.2 依赖项

| 依赖 | 级别 | 说明 |
|------|------|------|
| `DATA_DIR` 硬编码在 `app_enhanced.py` | 中 | `PROJECT_ROOT / "dashboard" / "data"`，路径变需要改代码 |
| `PROJECT_AGENTS_DIR` 硬编码在 `app_enhanced.py` | 中 | `PROJECT_ROOT / "agents"` |
| `artifacts_dir` 配置在 `zoo_mesh_daemon.py` | 中 | `PROJECTS["feida_zoo"]["artifacts_dir"] = "framework/shared"` |
| `TRACKER_PATH` 硬编码在 `persistence.py` | 低 | 仅 `task_tracker.json` 用到 |
| 历史 `pl_*.md` 文件 155 个 | 低 | 只需移动，不修改内容 |

### 1.3 风险点

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|----------|
| 已运行的 Pipeline 找不到旧文档 | 🟡 P1 | `_get_artifact_paths` 按固定路径计算 | 向后兼容：旧路径存在时优先读取，新文件写入新路径 |
| Dashboard 重启后访问 `issues.json` 找不到 | 🟡 P1 | `DATA_DIR` 路径改变 | 迁移后需将旧文件复制到新位置 |
| `agents/avatar.png` 路径改变导致 404 | 🟡 P1 | `_serve_avatar` 硬编码 | 同时保留旧路径 symlink 或 fallback |
| Git 仓库出现大量文件移动历史 | 🟢 P2 | git mv 可能产生杂乱 diff | 分开 commit（路径配置变更 + 文件移动） |

### 1.4 优先级

| 优先级 | 项 | 理由 |
|--------|----|------|
| **P0** | Dashboard 运行数据（issues/requirements）移出代码目录 | 数据安全：不会被 git reset/clean 误删 |
| **P1** | `zoo_mesh_daemon.py` `artifacts_dir` 改为 `docs/pipeline/` | 目录名合理、跨项目通用 |
| **P1** | `agents/avatar.png` 迁出代码目录 | 运行时配置不应在代码工程 |
| **P2** | 旧文件迁移脚本 + 向后兼容 | 避免触发历史 Pipeline 时找不到旧文档 |
| **P2** | 其他项目模板化（artifacts_dir 可配置） | 通用性 |

---

## 2. 架构设计

### 2.1 What

将运行数据和代码数据彻底分离——运行数据（issues、requirements、avatars、task_tracker）移出 `feida_zoo` 代码目录，文档存入合理的 `docs/` 目录。

### 2.2 Why

1. **数据安全**：`git clean -df` 会删除未跟踪的运行数据，`git reset --hard` 会还原
2. **仓库干净**：代码仓库只包含代码，运行数据应该另存
3. **跨项目通用**：第二个项目使用 Pipeline 时，文档路径不应是 `framework/shared/`
4. **备份合理**：运行数据备份策略（增量、快照）与代码（git）完全不同

### 2.3 目标目录结构

```
# 📁 运行数据（按 openclaw 工作目录隔离）
~/.openclaw/sessions/panda/zoo_mesh/
├── dashboard/              ← 新的 Dashboard 运行数据目录
│   ├── issues.json
│   ├── requirements.json
│   └── task_tracker.json
├── agents/                 ← 新的成员配置目录
│   ├── alpha/
│   │   └── avatar.png
│   ├── duci/
│   │   └── avatar.png
│   └── ...
├── pipeline/               ← 已有（保持不变）
│   ├── pending.json
│   ├── state_*.json
│   └── audit_*.json
├── chat/                   ← 已有（保持不变）
├── events/                 ← 已有（保持不变）
├── inbound/                ← 已有（保持不变）
└── delivery/               ← 已有（保持不变）

# 📁 项目文档（按项目目录存放）
/Volumes/data/workspace/code/feida_zoo/
├── docs/                   ← 新的 Pipeline 文档目录
│   └── pipeline/           ← 替代 framework/shared/pl_*.md
│       ├── pl_a2dd7ccc_design.md
│       ├── pl_a2dd7ccc_review.md
│       └── ...
├── framework/              ← 代码（保持不变）
├── dashboard/              ← 代码（保持不变）
└── ...
```

### 2.4 关键决策

| 决策 | 选项 | 选择理由 |
|------|------|----------|
| 运行数据放哪里？ | A: `~/.openclaw/sessions/panda/zoo_mesh/dashboard/` | ✅ 与 Pipeline 运行数据同目录，统一管理 |
| 运行数据目录路径 | B: 环境变量 `ZOO_DATA_DIR` | ❌ 增加复杂度，不必要 |
| | C: 单独 `~/.zoo_data/` | ❌ 额外增加顶级目录 |
| 文档目录路径 | A: `docs/pipeline/` | ✅ 标准约定，跨项目通用 |
| | B: ` framework/docs/` | ❌ framework 非标准 docs 目录 |
| 向后兼容 | A: 读新位置，旧位置 fallback | ✅ 不破坏已运行的 Pipeline |
| avatar 迁移 | A: 拷贝到新位置，保留旧位置 symlink（可选） | ✅ 前端访问无感知 |
| Pipeline 模板文档 | `docs/pipeline/pl_{id}_{phase}.md` | ✅ 所有项目统一 |

### 2.5 文件清单

```
修改文件（路径配置）：

1. dashboard/app_enhanced.py
   - DATA_DIR 改为指向 ~/.openclaw/sessions/panda/zoo_mesh/dashboard/
   - PROJECT_AGENTS_DIR 改为指向 ~/.openclaw/sessions/panda/zoo_mesh/agents/
   - task_tracker 引用改为新路径

2. framework/core/mesh/zoo_mesh_daemon.py
   - PROJECTS["feida_zoo"]["artifacts_dir"]: "framework/shared" → "docs/pipeline"
   - _get_artifact_paths: 增加旧路径 fallback 读取

3. framework/core/mesh/persistence.py
   - TRACKER_PATH 改为相对 ~/.openclaw/sessions/panda/zoo_mesh/dashboard/

数据迁移（一次性）：

4. 执行迁移脚本将旧文件复制到新位置：
   - dashboard/data/issues.json → ~/.openclaw/sessions/panda/zoo_mesh/dashboard/issues.json
   - dashboard/data/requirements.json → .../requirements.json
   - framework/shared/task_tracker.json → .../task_tracker.json
   - agents/*/avatar.png → .../agents/{id}/avatar.png
   - framework/shared/pl_*.md → docs/pipeline/pl_*.md
   - framework/shared/archive/ → docs/pipeline/archive/
   - framework/shared 其他文档（alpha_*、weaver_* 等）→ docs/pipeline/ 或 docs/archive/
```

### 2.6 接口影响

| 接口 | 是否受影响 | 说明 |
|------|-----------|------|
| `/api/issues` (GET/POST/PUT/DELETE) | 内部路径变更 | 仅 `DATA_DIR` 指向变，接口行为不变 |
| `/api/requirements` (GET/POST/PUT) | 内部路径变更 | 同上 |
| `/api/members` | 不受影响 | members 数据来自 ZooRegistry（YAML） |
| `/avatar/:id` | 路径 fallback | 优先读新位置 agents/，旧位置 symlink 兜底 |
| Pipeline phase 文档路由 | 路径变更 + fallback | 新文档写入 `docs/pipeline/`，旧文档从 `framework/shared/` 读取 |
| 运行时未暴露 | 不受影响 | zoo_mesh 内部状态文件不变 |

### 2.7 迁移策略

**Phase 1 — 路径配置变更（当前 Pipeline）：**
- 改 `DATA_DIR`、`PROJECT_AGENTS_DIR`、`artifacts_dir`、`TRACKER_PATH`
- `_get_artifact_paths` 增加旧路径 fallback

**Phase 2 — 数据迁移（手动或脚本执行）：**
- 复制运行数据到新位置
- 复制 pl_* 文档到 `docs/pipeline/`
- 旧位置可删除（或保留 symlink）

**Phase 3 — 清理：**
- 删除旧路径代码中的 fallback
- 删除 `agents/` 旧文件
- 删除 `framework/shared/` 中已迁移的 pl_* 文件

---

## 3. 执行计划

### Phase: develop_code

| 步骤 | 改动 | 位置 | 工作量 |
|------|------|------|--------|
| 1 | DATA_DIR 改指向新路径 | app_enhanced.py DATA_DIR | ~5分钟 |
| 2 | PROJECT_AGENTS_DIR 改指向新路径 | app_enhanced.py PROJECT_AGENTS_DIR | ~3分钟 |
| 3 | artifacts_dir 改为 docs/pipeline | zoo_mesh_daemon.py PROJECTS | ~3分钟 |
| 4 | _get_artifact_paths 增加旧路径 fallback | zoo_mesh_daemon.py | ~10分钟 |
| 5 | TRACKER_PATH 改路径 | persistence.py | ~2分钟 |
| 6 | 写迁移脚本 | scripts/migrate-data.sh | ~15分钟 |
| 7 | 测试 | 全部 64 用例 + 手动验证 | ~10分钟 |
| **总计** | | | **~48分钟** |

---

*文档版本: v1.0 | 设计者: Alpha 🐢 | 日期: 2026-05-29*

# Review 审查报告
## pl_cfba310f — feida_zoo 仓库公开化 + 目录结构整理

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: e920d68

---

## 总体评定：⚠️ CONDITIONAL PASS

设计文档整体质量合格，架构方案选择合理，但存在 **5处遗漏 + 2处安全风险 + 1处逻辑缺陷**，需在 develop_code 阶段补充处理。

---

## 1. 架构合理性：✅ 通过

- **环境变量方案**与现有代码风格一致（spawner.py、permissions.py 已有先例）
- 零新增 API 接口、零运行时行为变更——符合最小改动原则
- 优先级划分合理（P0/P1/P2/P3 层次清晰）
- 执行计划 13 步估算可行

---

## 2. 安全风险：🔴 发现 2 处

### 2.1 QQ OpenID 明文仍在 gateway-start.ts 中

**现状**: `gateway-start.ts:74-77` 硬编码了三个 QQ OpenID：
```
alpha: "639C0438DCC3CCA674064F1AFFBAE57D"
duci: "9BF8D96BAAB8D6CAF91FA0B6118C42CB"
panda: "C0B6F9464E1C6191FDE7A35065CEA549"
```

**设计文档方案**: 改为环境变量 `QQ_OPENID_ALPHA/DUCI/PANDA`。

**问题**: 设计文档未提及 **Git 历史中这些 OpenID 已经入库**。仅改源码不够——`git filter-branch` 需同时处理 `.ts` 源码中的 OpenID 字符串，否则 `git log -p` 仍可追溯。

**要求**: Git 历史重写范围需扩展，除邮箱外还需处理 OpenID 明文。或在 `2.7 节` 明确声明"OpenID 明文仅存在于最近 commit，重写后安全"并给出验证方法。

### 2.2 `zoo_members.yaml` 脱敏不彻底

**现状**: 文件包含 `model`、`session.key`、`session.channel` 三个敏感字段。

**设计文档方案**: 移除 `model` 和 `session`（含 key + channel）。

**问题**: 设计文档未评估 **下游代码是否读取这些字段**。若 `ZooRegistry` 或 Dashboard 运行时依赖 `model` 字段做路由，移除后会破坏运行时。

**要求**: 在 develop_code 前确认 `zoo_members.yaml` 的消费者列表（至少 `gateway-start.ts:119` 读取此文件），验证移除后运行时不会崩溃。建议增加 `.env.example` 文件说明需要配置的字段。

---

## 3. 遗漏检查：🔴 发现 5 处

### 3.1 测试文件硬编码路径遗漏

**现状**: `framework/tests/` 下有 **6 个测试文件** 包含 `/Users/zoo/workspace/code/feida_zoo` 硬编码：

| 文件 | 硬编码数 |
|------|---------|
| `test_pipeline_done_syncs_issue_status.py` | 2 |
| `test_member_active_filter.py` | 2 |
| `test_avatar_file_correctness.py` | 3 |
| `test_hardcoded_paths.py` | 8（含 /home/afei 路径断言） |
| `test_zoo_mesh_daemon.py`（harness） | 1 |

**设计文档文件清单**: 未列出任何测试文件的改动。

**风险**: 公开仓库后，测试文件中的 `/Users/zoo` 路径同样暴露用户名。`test_hardcoded_paths.py` 的断言检查的是 `/home/afei/` 路径——若其他文件改为环境变量，测试断言需同步更新。

**要求**: 补充测试文件到文件清单，所有 `/Users/zoo` 替换为环境变量或 `FEIDA_ZOO_HOME`，并更新 `test_hardcoded_paths.py` 的断言逻辑。

### 3.2 `test.txt` 遗漏

**现状**: 根目录存在 `test.txt` 文件。

**设计文档**: 移动到 `scripts/test.txt`。

**问题**: `test.txt` 不属于脚本，也不属于测试，归入 `scripts/` 分类不当。应评估内容后决定归档或删除。

### 3.3 `artifacts/pl_3833295c_ui_design.md` 遗漏

**现状**: `artifacts/` 目录下有一个文件 `pl_3833295c_ui_design.md`（7.8KB）。

**设计文档方案**: "artifacts → 移入 framework/shared/archive/"。

**问题**: 该文件是否包含敏感信息（用户名、路径等）？需先检查再迁移，而非机械搬运。

### 3.4 `.gitignore` 补全不完整

**现状 .gitignore** 已有 `*.log` 和 `artifacts/` 规则。

**设计文档新增规则**: `.env`、`.env.local`、`.vscode/`、`.idea/`、`.DS_Store`、`dashboard/*.log`。

**遗漏**:
- `venv/` 未忽略——虚拟环境不应入库
- `__pycache__/` 虽有 `*.pyc`，但 `__pycache__/` 目录本身也应忽略
- `node_modules/` 未忽略（TypeScript 插件依赖）
- `dashboard/data/` 下的运行时数据（如 `issues.json`）是否应忽略？

**要求**: 补充 `venv/`、`node_modules/`、`__pycache__/` 规则。评估 `dashboard/data/*.json` 是否应入 `.gitignore`。

### 3.5 Git 历史重写后 `.gitignore` 追踪日志清理

**现状**: 11 个 `dashboard/*.log` 文件已入库（被 git 追踪）。

**设计文档**: "清理 dashboard/*.log"。

**问题**: 仅 `git rm --cached` 不够——Git 历史中仍保留日志内容。若日志中包含敏感信息（用户名路径等），需通过 `git filter-repo` 一并清除。

**要求**: 检查入库日志内容是否含敏感信息。若含，需纳入历史重写范围；若不含，`git rm --cached` + `.gitignore` 即可。

---

## 4. 逻辑缺陷：🟡 1 处

### 4.1 环境变量默认值策略矛盾

设计文档 `2.6 节` 决定默认值使用 `/home/afei/workspace/code/feida_zoo`——理由是"不在默认值中暴露真实用户名"。

**问题**: `afei` 本身也是一个用户标识。虽然不是当前机器的真实用户名（当前是 `zoo`），但公开仓库中出现 `afei` 作为默认路径，可能误导用户以为这是真实路径。

**建议**: 将默认值改为更通用的形式，如 `/opt/feida_zoo` 或直接无默认值（启动时检查环境变量是否存在，不存在则报错退出）。这是更安全的"fail-closed"策略。

---

## 5. 改进建议

| # | 建议 | 优先级 | 理由 |
|---|------|--------|------|
| 1 | Git 历史重写范围扩展：包含 OpenID 明文 | P0 | 公开后 `git log -p` 可见 |
| 2 | 补充测试文件到改动清单 | P0 | 测试文件含 16 处硬编码路径 |
| 3 | 验证 zoo_members.yaml 消费者兼容性 | P0 | 运行时可能崩溃 |
| 4 | 环境变量默认值改为 fail-closed | P1 | 当前默认值策略有泄露风险 |
| 5 | .gitignore 补充 venv/node_modules | P1 | 标准忽略项缺失 |
| 6 | 检查 artifacts 文件内容再迁移 | P2 | 避免敏感信息搬移 |
| 7 | 检查入库日志内容是否含敏感信息 | P1 | 决定是否需历史重写 |
| 8 | 增加 `.env.example` 文件 | P2 | 帮助新用户配置环境变量 |

---

## 6. 硬编码路径全量扫描

扫描结果：**29 处** `/Users/zoo` 硬编码。

设计文档文件清单覆盖了 **18 处**（app_enhanced.py ×4, develop_executor.py ×2, zoo_mesh_daemon.py ×4, gateway-start.ts ×5, inbound-claim.ts ×1, git_adapter.py ×3），**遗漏 11 处**（全在测试文件中）。

| 类别 | 已覆盖 | 遗漏 |
|------|--------|------|
| 业务代码 | 18/18 ✅ | 0 |
| 测试代码 | 0/11 ❌ | 11 |
| **合计** | **18/29** | **11** |

---

**结论**: 设计方案方向正确，但遗漏了测试文件中 11 处硬编码路径、Git 历史中 OpenID 明文残留、以及下游依赖兼容性验证。建议 develop_code 阶段逐一修复后可 PASS。

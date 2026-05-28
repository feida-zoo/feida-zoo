# 需求评审 + 架构设计文档
## pl_cfba310f — feida_zoo 仓库公开化 + 目录结构整理

---

## 1. 需求评审

### 1.1 总体可行性：✅ 通过

本需求涉及纯工程性修改，无第三方依赖变更，无架构范式转变，所有改动点均可在线性时间内完成。**可行。**

### 1.2 依赖项

| 依赖 | 级别 | 说明 |
|------|------|------|
| Git filter-branch / filter-repo | 本地工具 | Git 历史重写需 `git filter-branch` 或 `git-filter-repo`，macOS 自带 git 含 `filter-branch` |
| OpenClaw runtime | 不影响公开化 | 仓库公开后运行时仍通过环境变量配置，不需要修改 OpenClaw |
| FEIDA_ZOO_HOME 环境变量 | 运行时 | 需要在部署端 export，现有代码已有 fallback；无需第三方 |
| QQ OpenID 环境变量 | 运行时 | 需要添加 QQ_OPENID_ALPHA / QQ_OPENID_DUCI / QQ_OPENID_PANDA 环境变量注入 |

### 1.3 风险点

| 风险 | 等级 | 说明 | 缓解 |
|------|------|------|------|
| Git 历史重写破坏协作分支 | 🔴 P0 | 若仓库有其他协作者，重写历史会导致分支冲突 | 确认本仓库仅单用户/单机开发，无协作者 |
| 硬编码路径遗漏 | 🟡 P1 | 全局搜索可能有遗漏 | 扫描 + 测试双重校验 |
| gateway-start.ts 编译产物覆盖 | 🟡 P2 | 修改 .ts 源码后需重新编译，否则运行时仍用旧的 .js | 修改后 yarn build 验证 |
| zoo_members.yaml 脱敏后运行时读取 | 🟡 P1 | Pipeline 代码依赖 `model` 和 `session.key` 字段 | 确认代码是否必须读取这些字段 |

### 1.4 优先级

| 优先级 | 项 | 理由 |
|--------|----|------|
| **P0** | 硬编码绝对路径替换为 FEIDA_ZOO_HOME | 直接暴露用户名 |
| **P0** | QQ OpenID 改为环境变量 | 直接暴露密钥 |
| **P0** | Git 历史邮箱重写 | 邮箱地址泄露 |
| **P0** | zoo_members.yaml 脱敏（model + session.key） | Agent 配置泄露 |
| **P1** | .gitignore 补全 | 日志/产物入库 |
| **P1** | 根目录脚本移入 scripts/ | 目录整洁 |
| **P1** | start_dev_center.sh 日志路径改为 /tmp/dashboard.log | 日志不入库 |
| **P2** | docs/ 空目录删除 + artifacts 归档 | 整洁优化 |
| **P2** | 11个日志文件清理 | 已被 .gitignore 覆盖，但需确保已入库的 .gitignore 生效后不再追踪 |
| **P3** | 测试脚本根目录清理 | 与脚本迁移合并处理 |

---

## 2. 架构设计

### 2.1 What

将 feida_zoo 仓库从本地开发状态整理为可安全公开的技术仓库。不改变运行时行为，仅做安全加固和目录整理。

### 2.2 Why

- 公开仓库暴露了：用户名（绝对路径）、QQ OpenID 密钥、Git 邮箱地址、Agent 内网配置
- 目录杂乱：9个脚本散落根目录、11个日志已入库、docs/ 空目录、artifacts 未归档
- 安全扫描已发现上述问题，必须在公开前修复

### 2.3 Tradeoff

| 方案 | 优点 | 缺点 |
|------|------|------|
| **直接替换硬编码路径** | 最小改动，不改变架构 | 多文件逐一修改，需谨慎 |
| 引入统一 Config 中心 | 更优雅 | 改动量大，与本需求范围不符，可后续迭代 |
| **环境变量 + Path 计算** | 兼容现有部署方式 | 需确保所有启动入口注入环境变量 |

**结论**：采用环境变量方案——保持现有代码风格，将硬编码路径改为 `os.environ.get("FEIDA_ZOO_HOME", ...)` 或 `Path(env_var)` 模式。已有 `spawner.py` 和 `permissions.py` 作为先例，保持一致。

### 2.4 接口定义

**新增环境变量**（运行时注入）：

```
FEIDA_ZOO_HOME       → 🐢 (已有，部分文件已使用)
QQ_OPENID_ALPHA      → QQ OpenID for alpha agent
QQ_OPENID_DUCI       → QQ OpenID for duci agent
QQ_OPENID_PANDA      → QQ OpenID for panda agent
```

**零新增 API 接口**。运行时行为零变化。

### 2.5 文件清单与改动范围

```
改动文件清单：

1. ./dashboard/app_enhanced.py
   - 第 29 行: PROJECT_ROOT = Path(FEIDA_ZOO_HOME)
   - 第 39 行: PANDA_ROOT = Path(FEIDA_ZOO_HOME).parent / "panda"
   - 第 48 行: DATA_DIR = PROJECT_ROOT / "dashboard" / "data"
   - 第 1126 行: fallback_path 改为 Path(FEIDA_ZOO_HOME).parent / member_id / "avatar.png"

2. ./framework/core/harness/executors/develop_executor.py
   - 第 15 行: FEIDA_ZOO_ROOT = Path(os.getenv("FEIDA_ZOO_HOME", ...))
   - 第 33 行: mesh_dir = os.getenv("ZOO_MESH_DIR", ...)

3. ./framework/core/mesh/zoo_mesh_daemon.py
   - 第 15 行: FRAMEWORK_DIR 默认改为 FEIDA_ZOO_HOME + "/framework"
   - 第 16 行: MESH_DIR 默认保留环境变量
   - 第 307 行: PROJECTS["panda"]["path"] 改用 FEIDA_ZOO_HOME
   - 第 761 行: issues_path 改为 FEIDA_ZOO_HOME + "/dashboard/data/issues.json"

4. ./plugins/zoo-pipeline/src/hooks/gateway-start.ts
   - 第 31-38 行: 默认路径改为 FEIDA_ZOO_HOME 环境变量
   - 第 73-76 行: QQ_OPENID 硬编码映射 → 环境变量
   - 第 119 行: yamlPath 默认值改为 FEIDA_ZOO_HOME
   - 第 166 行: DASHBOARD_PATH 默认值改为 FEIDA_ZOO_HOME
   - 第 169 行: DASHBOARD_PYTHON 默认值改为 FEIDA_ZOO_HOME/venv/bin/python

5. ./plugins/zoo-pipeline/src/hooks/inbound-claim.ts
   - 第 82 行: meshDir 默认值改为 FEIDA_ZOO_HOME

6. ./framework/configs/system.yaml
   - 默认值中的 /home/afei/workspace/code/feida_zoo 不变（这是公开示例值，安全合理）
   - 路径已使用 ${FEIDA_ZOO_HOME:-...} 环境变量模式，无需改动

7. ./framework/core/spawner.py
   - 第 88 行: 已使用环境变量模式，无需改动

8. ./framework/core/permissions.py
   - 第 139 行: 已使用环境变量模式，无需改动

9. ./framework/data/zoo_members.yaml
   - 移除所有成员的 `model:` 及其值
   - 移除所有成员的 `session:` 及其子字段 `key:` 和 `channel:`

10. ./dashboard/git_adapter.py
    - 第 40/45/50 行: 硬编码路径改为 FEIDA_ZOO_HOME 动态计算

新增文件：
- ./scripts/ （目录不存在则创建）
- ./.gitignore 补全（已有，追加规则）

移动文件：
- ./run_existing_tests.py → ./scripts/run_existing_tests.py
- ./run_security_tests.py → ./scripts/run_security_tests.py
- ./test_concurrent.py → ./scripts/test_concurrent.py
- ./test_concurrent_json_simple.py → ./scripts/test_concurrent_json_simple.py
- ./test_deadlock_audit.py → ./scripts/test_deadlock_audit.py
- ./test_fix_verification.py → ./scripts/test_fix_verification.py
- ./test_path_traversal.py → ./scripts/test_path_traversal.py
- ./test_absolute_path.py → ./scripts/test_absolute_path.py
- ./test.txt → ./scripts/test.txt
- ./verify_git_pipeline.py → ./scripts/verify_git_pipeline.py
- ./zoo-phase-complete → ./scripts/zoo-phase-complete
- ./zoo-service-restart → ./scripts/zoo-service-restart

删除目录：
- ./docs/ （空目录）

归档：
- ./artifacts/ → 移入 ./framework/shared/archive/
- ./dashboard/*.log → 清理（git rm --cached 确保不再追踪）

修改：
- ./dashboard/start_dev_center.sh → 日志从 dashboard/server_enhanced.log 改为 /tmp/dashboard.log

测试文件映射（不改内容，仅确认运行时可用）：
- ./framework/tests/ut/test_hardcoded_paths.py（已有，应仍能通过）

不涉及的路径（已使用环境变量的）：
- spawner.py（OK）
- permissions.py（OK）
- system.yaml（OK）
```

### 2.6 环境变量默认值决策

对公开仓库而言，默认值不能是 `/Users/zoo/workspace/...`。现有 `spawner.py` 和 `permissions.py` 使用 `/home/afei/workspace/code/feida_zoo` 作为默认值——这是一个合理的假名默认值。

**决策**：保持现有模式，所有新增的环境变量默认值也使用 `/home/afei/workspace/code/feida_zoo`（对 `FEIDA_ZOO_HOME`）或以 `FEIDA_ZOO_HOME` 为根拼接。这样既不在默认值中暴露真实用户名，又提供了一个开箱即用的示例路径。

对 `ZOO_MESH_DIR`：默认值为 `${FEIDA_ZOO_HOME}/../panda/zoo_mesh`（相对路径），避免硬编码 `/Users/zoo/workspace/members/panda`。

对 `QQ_OPENID_*`：默认值为空字符串，需用户显式配置。配置方式示例：

```bash
export QQ_OPENID_ALPHA="REPLACE_WITH_YOUR_OPENID"
export QQ_OPENID_DUCI="REPLACE_WITH_YOUR_OPENID"
export QQ_OPENID_PANDA="REPLACE_WITH_YOUR_OPENID"
```

### 2.7 Git 历史邮箱重写方案

**方法**：`git filter-branch --env-filter`

```bash
git filter-branch --env-filter '
OLD_EMAIL1="feidada002@gmail.com"
OLD_EMAIL2="super_afei@qq.com"
CORRECT_NAME="feida-zoo"
CORRECT_EMAIL="feidada002@gmail.com"
if [ "$GIT_COMMITTER_EMAIL" = "$OLD_EMAIL1" ] || [ "$GIT_COMMITTER_EMAIL" = "$OLD_EMAIL2" ]; then
    export GIT_COMMITTER_NAME="$CORRECT_NAME"
    export GIT_COMMITTER_EMAIL="$CORRECT_EMAIL"
fi
if [ "$GIT_AUTHOR_EMAIL" = "$OLD_EMAIL1" ] || [ "$GIT_AUTHOR_EMAIL" = "$OLD_EMAIL2" ]; then
    export GIT_AUTHOR_NAME="$CORRECT_NAME"
    export GIT_AUTHOR_EMAIL="$CORRECT_EMAIL"
fi
' --tag-name-filter cat -- --branches --tags
```

注意：`super_afei@qq.com` 邮箱地址包含 `afei` 用户名不宜公开，统一改为 `feidada002@gmail.com`。

### 2.8 .gitignore 补全

当前 `.gitignore` 缺少：
```
# 日志
dashboard/*.log
*.log

# 发布产物
artifacts/

# 环境配置
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
```

---

## 3. UI 设计

### 3.1 需求性质判定

本次需求为 **基础设施/安全加固** 类型，**无前端 UI 变更**。涉及：
- Python 后端配置硬编码处理（无 UI）
- TypeScript 启动脚本配置硬编码处理（无 UI）
- YAML 成员配置脱敏（无 UI）
- Git 历史重写（无 UI）
- 目录整理（无 UI）

### 3.2 影响到的 Dashboard

Dashboard (`app_enhanced.py`) 的路径配置修改后，**行为不变**，启动流程不变。无需修改任何前端模板或 JS 文件。

### 3.3 影响到的 Pipeline

Pipeline 流程不受影响，因所有路径和环境变量在运行时动态解析。

---

## 4. 执行计划

### Phase: develop_code

| 步骤 | 改动文件 | 工作量估计 |
|------|----------|-----------|
| 1 | app_enhanced.py × 4处硬编码 | ~5分钟 |
| 2 | develop_executor.py × 2处硬编码 | ~3分钟 |
| 3 | zoo_mesh_daemon.py × 3处硬编码 | ~5分钟 |
| 4 | gateway-start.ts × 5处硬编码 + QQ_OPENID | ~8分钟 |
| 5 | inbound-claim.ts × 1处 | ~2分钟 |
| 6 | git_adapter.py × 3处 | ~3分钟 |
| 7 | zoo_members.yaml 脱敏 | ~2分钟 |
| 8 | 创建 scripts/ 目录，移动根脚本 | ~5分钟 |
| 9 | 更新 .gitignore | ~2分钟 |
| 10 | start_dev_center.sh 日志路径修改 | ~2分钟 |
| 11 | docs/ 删除 + artifacts 归档 | ~2分钟 |
| 12 | 清理 dashboard/*.log | ~1分钟 |
| 13 | Git 历史重写 | ~3分钟 |
| **总计** | **13项** | **~43分钟** |

### Phase: review / audit

- 确认所有硬编码路径扫描清单 0 遗漏
- 确认 .gitignore 生效后无日志/产物追踪
- 验证 git log 历史中无真实邮箱暴露
- 验证 zoo_members.yaml 无 model/session.key 字段

### Phase: deliver

- 创建公开 README（如果缺失）
- 确认 `git status` 干净
- 确认测试套件通过

---

*文档版本: v1.0 | 设计者: Alpha 🐢 | 日期: 2026-05-28*

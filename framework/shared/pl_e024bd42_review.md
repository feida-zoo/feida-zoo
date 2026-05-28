# Review 设计评审报告
## pl_e024bd42 — 运行数据与代码数据隔离

**审查人**: Duci 🦂 | **日期**: 2026-05-29 | **上游 commit**: e80c541

---

## 总体评定：✅ PASS（3 个必须修复项 + 2 个建议项，可在 develop_code 阶段修正）

设计方向正确，架构清晰，向后兼容策略合理。但存在 3 个必须修复的遗漏，2 个建议项。

---

## 1. 架构合理性

### 1.1 ✅ 运行数据路径选择正确

`~/.openclaw/sessions/panda/zoo_mesh/dashboard/` 与 Pipeline 运行数据同目录，统一管理。避免了额外顶级目录（`~/.zoo_data/`），复用已有的 `sessions/panda/zoo_mesh/` 结构。

### 1.2 ✅ 文档目录 `docs/pipeline/` 跨项目通用

Pipeline 阶段文档放在项目 `docs/pipeline/` 而非 `framework/shared/` 的设计正确。第二个项目使用 Pipeline 时，文档会生成在 `another-project/docs/pipeline/`，不污染 feida_zoo 目录。

### 1.3 ✅ 向后兼容策略合理

`_get_artifact_paths` 优先读新路径，旧路径 fallback 读取的设计避免了已运行的 Pipeline 找不到旧文档的问题。

---

## 2. 安全风险

### 2.1 🟡 P1：Avatar 路径遍历漏洞未处理

`app_enhanced.py:_serve_avatar`（第 1451 行）存在路径遍历风险：

```python
file_path = STATIC_DIR / urlparse(self.path).path.split('/static/')[-1]
```

当前设计只改了 `PROJECT_AGENTS_DIR` 指向新路径，但未处理路径遍历防护。若攻击者访问 `/static/../agents/alpha/avatar.png`，`urlparse` 后 `split('/static/')[-1]` 得 `../agents/alpha/avatar.png`，拼接后可能逃逸出 `STATIC_DIR`。

**修复建议**：在 `_serve_avatar` 中对 `file_path` 做 `resolve()` 后安全检查：
```python
file_path = STATIC_DIR / safe_name
file_path = file_path.resolve()
if not str(file_path).startswith(str(STATIC_DIR.resolve())):
    self.send_error(403)
    return
```

### 2.2 🟢 P3：Pipeline 阶段文档路径暴露风险

当前 `artifacts_dir` 配置为 `docs/pipeline/`，路径不涉及敏感信息。文档内容由各阶段 Agent 撰写，不含密钥。风险低。

---

## 3. 遗漏检查

### 3.1 🔴 P0：Avatar fallback 路径仍有硬编码

**当前 avatar 路径逻辑**（两处）：

1. 主路径（第 1451 行）：
   ```python
   avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"  # 将改为新路径 ✅
   ```

2. Fallback（第 1456 行）：
   ```python
   fallback_path = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")).parent / member_id / "avatar.png"
   # ⚠️ 未使用环境变量，硬编码 fallback 路径
   ```

Design §2.5 只覆盖了修改 `PROJECT_AGENTS_DIR`，未处理第 1456 行的 fallback 硬编码路径。迁移后旧 avatar 文件在 `FEIDA_ZOO_HOME.parent / member_id / avatar.png`，fallback 会继续读取，但 avatar 文件实际会在 `~/.openclaw/sessions/panda/zoo_mesh/agents/{id}/avatar.png`。

**修复**：将第 1456 行 fallback 改为使用 `openclaw_sessions_dir` 环境变量或计算值。

### 3.2 🟡 P1：`docs/pipeline/` 初始需 mkdir

`zoo_mesh_daemon.py` 的 `_get_artifact_paths` 在写入 `docs/pipeline/` 前需确保目录存在。当前代码无 mkdir 逻辑，若 `docs/` 为空目录（老项目可能），写入会失败。

**修复**：`base` 目录不存在时 `mkdir(parents=True, exist_ok=True)`。

### 3.3 🟡 P1：155 个历史 pl_*.md 迁移策略

Design §2.5 提到"复制 pl_*.md 到 docs/pipeline/"，但未说明：
- 是否所有 155 个历史文件都要迁移，还是只迁移当前活跃的？
- 迁移后 `framework/shared/` 中的旧文件是否从 git 删除？
- 已 commit 的历史文件移动会不会污染 git 历史？

**建议**：Phase 2 迁移脚本中明确：
```bash
# 迁移策略：只迁移当前活跃 Pipeline 的文档
# 已归档的 pl_* 文件仍留在 framework/shared/archive/
# 或 docs/pipeline/archive/
```

### 3.4 🟢 P2：Avatar symlink vs 拷贝

Design §2.4 提到"保留旧位置 symlink（可选）"。若选择 symlink，`/static/avatars/{id}.png` 的静态文件服务器需处理 symlink 指向的代码外路径，可能超出 serve 范围。建议用**拷贝**而非 symlink，降低风险。

---

## 4. 改进建议

| # | 优先级 | 问题 | 建议 |
|---|--------|------|------|
| 1 | 🔴 P0 | Avatar fallback 路径（第 1456 行）仍有硬编码 | 改为使用环境变量计算的新路径 |
| 2 | 🟡 P1 | `docs/pipeline/` 初始 mkdir | `_get_artifact_paths` 中 `mkdir` |
| 3 | 🟡 P1 | 155 个历史 pl_*.md 迁移策略不明 | 迁移脚本中明确：只迁活跃文件，旧文件移 archive |
| 4 | 🟢 P2 | Avatar symlink vs 拷贝选择 | 建议用拷贝，删除 symlink 方案 |

---

## 5. 文件清单验证

| Design §2.5 声称的改动 | 现状 | 差异 |
|-----------------------|------|------|
| `DATA_DIR` 改指向新路径 | ✅ 需修改（第 48 行） | 需 develop_code |
| `PROJECT_AGENTS_DIR` 改指向新路径 | ✅ 需修改（第 40 行） | 需 develop_code |
| `artifacts_dir` 改为 `docs/pipeline` | ✅ 需修改（zoo_mesh_daemon.py:306） | 需 develop_code |
| `_get_artifact_paths` 增加旧路径 fallback | ✅ 需修改（zoo_mesh_daemon.py:335） | 需 develop_code |
| `TRACKER_PATH` 改路径 | ✅ 需修改（persistence.py:17） | 需 develop_code |
| 迁移脚本 | ✅ 需 develop_code | 迁移策略需明确 |

---

## 6. 结论

设计方向正确，架构合理。3 个 P0/P1 遗漏（avatar fallback 硬编码、docs mkdir、历史文件迁移策略）需在 develop_code 阶段修复。P1 avatar 路径遍历防护也需同时处理。

**判定：PASS** 🦂（附修复清单）
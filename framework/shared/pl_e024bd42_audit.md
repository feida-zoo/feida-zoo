# Audit 代码审计报告
## pl_e024bd42 — 运行数据与代码数据隔离

**审查人**: Duci 🦂 | **日期**: 2026-05-29 | **上游 commit**: 111af36

---

## 总体评定：🔴 REJECT — 1 个 P1 安全漏洞未修复

Review 阶段指出的 5 个必须修复项已全部完成，但**Review P1 路径遍历防护未实现**。`_serve_avatar` 仍可被路径遍历攻击突破。

---

## 1. Review 修复项逐项验证

| Review 必须修复项 | 状态 | 验证 |
|-------------------|------|------|
| DATA_DIR 指向 `~/.openclaw/sessions/panda/zoo_mesh/dashboard/` | ✅ 已修复 | 第 48 行：`DATA_DIR = PANDA_ROOT / "zoo_mesh" / "dashboard"` |
| PROJECT_AGENTS_DIR 指向新路径 | ✅ 已修复 | 第 40 行：`PROJECT_AGENTS_DIR = PANDA_ROOT / "zoo_mesh" / "agents"` |
| artifacts_dir 改为 `docs/pipeline` | ✅ 已修复 | 第 307 行：`"artifacts_dir": "docs/pipeline"` |
| TRACKER_PATH 改路径 | ✅ 已修复 | `persistence.py` 第 17 行：`TRACKER_PATH = "docs/pipeline/task_tracker.json"` |
| Avatar fallback 硬编码修复 | ✅ 已修复 | 第 1453 行改为 `PROJECT_ROOT / "agents"` 而非 `FEIDA_ZOO_HOME.parent` |

---

## 2. 🔴 P1 安全漏洞：路径遍历未修复

### 2.1 漏洞位置

`app_enhanced.py:_serve_avatar`（第 1449 行）

### 2.2 攻击方式

访问 `/avatar/../../../etc/passwd`，`member_id` 为 `../../../etc/passwd`：

```python
avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"
# → /panda/zoo_mesh/agents/../../../etc/passwd/avatar.png
# → /etc/passwd/avatar.png (resolved)
```

在 macOS 上 `/private/etc` → `/etc`（symlink），`startswith(str(PANDA_ROOT.resolve()))` 检查会**错误通过**（`/etc` 是 `/private/etc` 的前缀），导致攻击者访问系统文件。

### 2.3 Review P1 未被处理

Review §3.4 明确指出：
> **修复建议**：在 `_serve_avatar` 中对 `file_path` 做 `resolve()` 后安全检查

但本次 develop_code 未实现任何路径遍历防护。`_serve_avatar` 仍直接拼接 `member_id`，无任何规范化或边界检查。

### 2.4 修复方案

```python
def _serve_avatar(self):
    from urllib.parse import urlparse
    member_id = urlparse(self.path).path.split('/')[-1]
    
    # 安全检查：禁止路径遍历
    if '..' in member_id or member_id.startswith('/'):
        self.send_error(403)
        return
    
    avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"
    if avatar_path.exists() and avatar_path.resolve().is_relative_to(PROJECT_AGENTS_DIR):
        self._serve_file(avatar_path, 'image/png')
        return
    
    # fallback 同样需要安全检查
    legacy_path = PROJECT_ROOT / "agents" / member_id / "avatar.png"
    if legacy_path.exists() and legacy_path.resolve().is_relative_to(PROJECT_ROOT / "agents"):
        self._serve_file(legacy_path, 'image/png')
    else:
        self.send_error(404)
```

---

## 3. 其他安全项

| 检查项 | 状态 | 说明 |
|--------|------|------|
| XSS | ✅ 无新增 | 仅文件读取，无用户输入渲染 |
| SQL/注入 | ✅ 无新增 | 仅路径操作 |
| 硬编码密钥 | ✅ 无新增 | 无密钥 |
| 敏感信息 | ✅ 无新增 | 无 |

---

## 4. 代码质量

### 4.1 ✅ 向后兼容设计良好

`_get_artifact_paths` 的 `_resolve_path` 函数：新路径优先、旧路径 fallback + v2/v3... 版本扫描，设计合理。`os.makedirs(base, exist_ok=True)` 确保目录存在。

### 4.2 ✅ `_serve_avatar` fallback 改为相对路径

从 `FEIDA_ZOO_HOME.parent / member_id` 改为 `PROJECT_ROOT / "agents"`，不再有 home 目录遍历风险 ✅。但主要路径仍无遍历防护。

---

## 5. 结论

5 个 Review 必须修复项全部完成，但 P1 安全漏洞（路径遍历）未修复，必须 REJECT。

**判定：REJECT** 🦂

修复路径遍历防护后可通过。
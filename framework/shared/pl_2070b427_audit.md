# Audit Report — pl_2070b427

**Task**: 成员管理界面人数不对  
**Requirement**: 6587c35b-17d0-4361-bae4-5e04ecea31fa  
**Auditor**: Duci (🦂)  
**Date**: 2026-05-26  
**Files Audited**: `dashboard/app_enhanced.py`（`_get_member_data()` 及相关）

---

## 安全漏洞

### SQL 注入：✅ 无风险
无任何 SQL 操作，仅 YAML 读取。

### XSS：✅ 无风险
`_get_member_data()` 返回 Python dict 由 JSON serializer 处理。数据未经 HTML 渲染直接返回 API 响应，special chars 由 JSON encoder 自动转义。

### 硬编码密钥/凭证：✅ 无风险
无任何 secret、key、token 或凭证。

### 命令注入：✅ 无风险
无 `subprocess`、`os.system`、`eval`、`exec` 调用。

### Path Traversal：⚠️ 存在于 `_serve_avatar()`，但非本 pipeline 引入

**位置**：`app_enhanced.py` L1112~L1127

```python
def _serve_avatar(self):
    member_id = urlparse(self.path).path.split('/')[-1]
    avatar_path = AGENTS_DIR / member_id / "avatar.png"
    if avatar_path.exists():
        self._serve_file(avatar_path, 'image/png')
        return
    fallback_path = Path("/Users/zoo/workspace/members") / member_id / "avatar.png"
```

`member_id` 来自 URL 路径，无白名单校验。恶意请求 `/avatar/../../../etc/passwd` 可构造路径遍历。但：
1. 此函数**非本 pipeline 新增**（属于 dashboard 原有代码）
2. 仅限内网 dashboard 暴露，攻击面有限
3. 建议后续修复：对 `member_id` 做正则校验（如 `[a-z0-9_]+`）

---

## 代码质量

### ✅ isinstance 类型守卫
```python
member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
```
正确处理 `meta` 可能为 None 或非 dict 的边界情况。

### ✅ YAML safe_load
```python
yaml_data = _yaml.safe_load(f)
```
使用 `safe_load` 而非 `load`，无代码执行风险。

### ✅ 防御性默认值
无 `status` 字段时默认 `"active"`，新增成员不会被误杀。

### ✅ 注释清晰
关键过滤逻辑有中文注释说明意图。

### 🟡 代码重复
主路径（L1182~L1195）和 fallback 路径（L1232~L1244）结构几乎完全相同，仅数据源不同（`full` vs `info`）。建议抽取为独立函数 `_build_member_entry(member_id, info, status)` 避免未来维护风险。

---

## 性能风险

### ✅ 过滤开销可忽略
```python
if member_status != "active":
    continue
```
O(1) 字符串比较，在 `list_agents()` 返回的最多 6 个成员上循环，成本忽略不计。

### ✅ status_cache.get() 为 O(1)
`dict.get()` 哈希表查询，无性能问题。

### ✅ 无阻塞 I/O
函数内无文件 I/O（YAML 在异常 fallback 路径才读取，正常路径走 ZooRegistry 内存缓存）。

### 🟡 `_update_status()` 仍检测 inactive 成员
`MemberStatusManager._update_status()` 未应用相同过滤，每个 inactive 成员仍执行一次 `pgrep`（timeout 3s×3=9s/轮询）。不影响正确性，纯资源浪费。

---

## 审计通过项

| 检查项 | 状态 |
|--------|------|
| SQL 注入 | ✅ 安全 |
| XSS | ✅ 安全（JSON API） |
| 硬编码密钥 | ✅ 无 |
| 命令注入 | ✅ 无 |
| Path Traversal（新代码） | ✅ 无（本 pipeline 新增代码无此问题） |
| YAML safe_load | ✅ 使用 safe_load |
| 类型守卫 | ✅ isinstance 检查 |
| 默认值安全 | ✅ 无 status 默认 active |
| 性能 | ✅ 无风险 |
| 代码重复 | 🟡 建议后续重构 |

---

## 结论：**pass**

本 pipeline 新增的 status 过滤代码（主路径 + fallback 路径）安全、无漏洞、逻辑正确。唯一 Path Traversal 风险存在于 `_serve_avatar()` 原始代码，非本 pipeline 引入。

---

## 审计摘要

| 检查项 | 结论 |
|--------|------|
| 安全漏洞 | ✅ pass |
| 代码质量 | ✅ pass（🟡 代码重复建议） |
| 性能风险 | ✅ pass |
| 最终结论 | **pass** |

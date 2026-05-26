# Design Report — pl_b5e6038b

**Task**: issue已经done了，但是问题管理界面。状态还是待处理  
**Requirement**: aba00359-1b1a-4742-bac5-45c31b8bd1e4  
**Designer**: Alpha (🐢)  
**Date**: 2026-05-26  
**Input**: `pl_b5e6038b_validate.md`  

---

## What — 具体改动

在 daemon 的 `_handle_phase_complete()` 函数 `next_phase == "done"` 分支中，增加 issue 状态回写逻辑：

```python
# Pipeline 完成 → 查找关联 issue 并标记 resolved
if next_phase == "done":
    cur_req["status"] = "done"
    ...
    # === 新增：同步更新 issues.json ===
    try:
        issues_path = Path("/Users/zoo/workspace/code/feida_zoo/dashboard/data/issues.json")
        if issues_path.exists():
            with open(issues_path, 'r', encoding='utf-8') as f:
                issues = json.load(f)
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
            updated = False
            for issue in issues:
                if issue.get("pipeline_id") == pipeline_id:
                    issue["status"] = "resolved"
                    issue["resolved_at"] = now_iso
                    issue["updated_at"] = now_iso
                    updated = True
                    logger.info(f"📝 Pipeline {pipeline_id} 完成，关联 issue {issue.get('id', '?')} 标记为 resolved")
                    break
            if updated:
                with open(issues_path, 'w', encoding='utf-8') as f:
                    json.dump(issues, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"⚠️ Pipeline {pipeline_id} 完成后同步 issue 状态失败（降级）: {e}")
```

---

## Why — 背景与解决的问题

### 当前行为

Pipeline 完成时，`_handle_phase_complete()` 更新了 `requirements.json`（status=done）和 state 文件（done），但**未触及 `issues.json`**。

用户从 dashboard 问题管理界面看到的 `status` 字段来自 `issues.json`，因此即使 pipeline 已 done，issue 仍显示 **待处理**。

### 影响面

- 所有由 dashboard 创建的 issue（`source: "dashboard"`）受此 bug 影响
- 当前 issues.json 中：
  - `4b17d3cf` (pipeline_status: done) → status=resolved ✅（可能是之前手动改的）
  - `6587c35b` (pipeline_status: pushed) → status=open ❌
  - `21470d44` (pipeline_status: pushed) → status=open ❌
  - `aba00359` (pipeline_status: pushed) → status=open ❌（本条 issue）

### 数据流

```
dashboard 创建 issue
  → issues.json [status=open, pipeline_id=pl_xxx]
  → daemon 创建 pipeline [phase=request]
  ... 各阶段推进 ...
  → daemon done 分支 [requirements.json status=done]
  → ❌ issues.json 未更新 [status 仍是 open]
```

修复后：

```
dashboard 创建 issue
  ... pipeline 推进 ...
  → daemon done 分支 [requirements.json status=done]
  → ✅ issues.json 同步更新 [status=resolved, resolved_at=now]
```

---

## Tradeoff — 方案权衡

| 方案 | 描述 | 优点 | 缺点 | 决策 |
|------|------|------|------|------|
| **A（采纳）** | daemon done 分支直接写 issues.json | 单点修复，无需改 dashboard 代码 | daemon 和 dashboard 可能并发写 issues.json | ✅ **最优**: 改动最小，数据一致性即时 |
| B | dashboard 定期轮询 requirements.json | 无并发写冲突 | 轮询延迟、实现复杂、增加网络请求 | ❌ 过度设计 |
| C | 删除 issues.json 独立状态，完全用 requirements.json | 单一数据源 | 需重构 dashboard 前端全部 issue API 调用 | ❌ 改动面太大 |

**并发风险缓解**: dashboard 前端通常只在用户操作时写 issues.json（创建/PUT/DELETE）。pipeline done 发生在后端异步推进，与用户操作时间窗口重叠概率极低。即便冲突，daemon 写入的是 `resolved_at` 和 `status`，dashboard 写入的是 `title/description/priority` 等字段，字段不重叠。

---

## 接口定义

无新增 API 或函数签名。在现有函数内部增加一段 try/except 块。

### 改动位置

**文件**: `framework/core/mesh/zoo_mesh_daemon.py`  
**函数**: `_handle_phase_complete()`  
**分支**: `if next_phase == "done":`（约 L870-940 区间）  
**插入点**: 在 `cur_req["status"] = "done"` 和 `_save_requirements(reqs)` 之后

---

## 文件清单

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `framework/core/mesh/zoo_mesh_daemon.py` | ~20 行 | `_handle_phase_complete()` done 分支增加 issue 回写 |

无新增文件，无前端改动，无 dashboard 改动。

---

## Open Questions

1. **并发写 issues.json 的锁机制？**  
   dashboard 有 `_issues_write_lock`（threading.RLock），daemon 没有。实践中 pipeline done 与用户操作同时发生的概率极低，且字段不重叠（daemon 改 status/resolved_at，dashboard 改 title/description/priority/assignee）。**建议暂不引入锁**，若后续出现并发问题再补。

2. **issue 找不到时如何处理？**  
   某些 pipeline 可能不是由 dashboard issue 触发的（如直接 API 调用）。此时 `pipeline_id` 在 issues.json 中无匹配， gracefully skip，仅 log warning。

3. **历史 issue 不回溯？**  
   当前 issues.json 中有多个已 done 但 status=open 的 issue。本次修复只影响**未来**完成的 pipeline。历史数据建议手动批量更新或忽略（用户可手动点「关闭问题」）。

4. **pipeline_status 字段是否需要同步更新？**  
   `pipeline_status` 在 issues.json 中初始为 `pushed`，在 `_handle_phase_complete` 推进各阶段时并未更新。本次修复 focus 在 `status`（用户可见），`pipeline_status` 可后续增强但不阻塞。

---

## Next Action — 审计重点

请 **Duci** 重点审查以下三点：

1. **异常降级**: try/except 块是否正确包裹了整个文件 I/O 流程，确保任何异常不会阻塞 pipeline 本身的完成流程？

2. **字段覆盖**: 确认 daemon 写入的字段（status, resolved_at, updated_at）与 dashboard 常规写入字段不重叠，避免静默覆盖用户修改。

3. **路径硬编码**: `issues_path` 使用绝对路径 `/Users/zoo/workspace/code/feida_zoo/dashboard/data/issues.json`。该路径与 dashboard 中 `_get_issues_path()` 一致，但未来若 dashboard 目录变动需同步修改。建议后续提取为共享常量。

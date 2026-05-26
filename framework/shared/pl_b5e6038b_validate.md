# Validate Report — pl_b5e6038b

**Task**: issue已经done了，但是问题管理界面。状态还是待处理  
**Requirement**: aba00359-1b1a-4742-bac5-45c31b8bd1e4  
**Validator**: Alpha (🐢)  
**Date**: 2026-05-26  

---

## 可行性分析：✅ 可实现

### 问题根因

Pipeline 完成时，`_handle_phase_complete()` 在 daemon 中做了以下操作：
1. 更新 `requirements.json` → `cur_req["status"] = "done"`
2. `pipeline.mark_done()` 
3. `mesh.set_pipeline_state(pipeline_id, "done")`
4. 清理 pending 队列

**但完全没有更新 `issues.json` 中关联 issue 的 `status` 字段。**

示例：`issue id: 4b17d3cf-8ce1-4a0a-a457-91658a79722a`（统计页不需要生态成员）
- `pipeline_id: pl_bb50c26a` 已 done
- `pipeline_status: done`  ✓
- `status: open`  ❌ 应改为 resolved
- `resolved_at: null` ❌ 应设为完成时间

再看今天刚完成的两个 pipeline：
- `pl_2070b427`（成员人数不对）→ issue `6587c35b` status=open, pipeline_status=pushed
- `pl_ecd1f8b8`（成员头像不对）→ issue `21470d44` status=open, pipeline_status=pushed

注意：这两个 issue 的 `pipeline_status` 在 `_handle_issues_post()` 初始创建时设为 `pushed`，但 **daemon 从未在 pipeline 推进时回写 issues.json**。

### 修复方案

在 daemon 的 `_handle_phase_complete()` → `next_phase == "done"` 分支中，增加：
1. 读取 `issues.json`
2. 查找 `pipeline_id` 匹配的 issue
3. 更新 `issue["status"] = "resolved"`
4. 更新 `issue["resolved_at"] = now`
5. 保存 `issues.json`

### 修复范围

仅需修改一处：`framework/core/mesh/zoo_mesh_daemon.py` 中 `_handle_phase_complete()` 的 done 分支，约 +8 行。

---

## 依赖项

| # | 依赖 | 状态 | 说明 |
|---|------|------|------|
| 1 | `issues.json` 存在 `pipeline_id` 字段 | ✅ 已存在 | 所有 dashboard 创建的 issue 都有 |
| 2 | `_handle_phase_complete` 在 daemon 中运行 | ✅ 已存在 | 当前已有完整 pipeline 推进逻辑 |
| 3 | 并发安全：issues.json 写锁 | ⚠️ 需确认 | `app_enhanced.py` 有 `_issues_write_lock`，但 daemon 无 |
| 4 | pipeline 与 issue 1:1 映射 | ✅ 已存在 | 每个 dashboard issue 对应一个 pipeline_id |

---

## 风险点

| 风险 | 等级 | 说明 |
|------|------|------|
| 并发写 issues.json | 🟡 中 | daemon 和 dashboard 可能同时写 issues.json。dashboard 有 `_issues_write_lock`，daemon 无。但 pipeline done 发生时 dashboard 通常不操作该 issue，冲突概率低 |
| 找不到对应 issue | 🟢 低 | pipeline 可能不是由 dashboard 创建的（如直接 API 调用），此时无 issue 关联。需 gracefully skip |
| 重复 done 通知 | 🟢 低 | daemon 已有幂等校验 `current_status == "done"` return，不会重复更新 |
| 历史数据不回溯 | 🟢 低 | 旧 issue 状态不会自动修正，但 UI 重新加载时会显示新状态 |

---

## 建议优先级：**P1**

**P1 理由：**
- ✅ 导致用户看到已完成的 issue 仍显示“待处理”，数据一致性 bug
- ✅ 修复量极小（~8 行），依赖已就绪
- ✅ 已有 pipeline_id ↔ issue 映射链路，不需要新增数据字段
- ❌ 不影响 pipeline 执行或业务逻辑，不构成 P0

---

## 结论

**Pass** —— 需求明确，根因唯一（done 分支未回写 issues.json），修复范围窄，技术上完全可行。

# Review Report — pl_b5e6038b

**Task**: issue已经done了，但是问题管理界面状态还是待处理  
**Requirement**: aba00359-1b1a-4742-bac5-45c31b8bd1e4  
**Reviewer**: Duci (🦂)  
**Date**: 2026-05-26  
**Input**: `pl_b5e6038b_design.md` + source code verification

---

## 架构合理性：✅ 通过

**方案选择正确。** 在 daemon done 分支直接回写 `issues.json` 是最小改动路径。设计文档的方案 A（daemon 直接写）是最优选择，字段不重叠（daemon 写 status/resolved_at，dashboard 写 title/description），并发冲突风险低。

---

## 安全风险：✅ 低风险

**无注入风险。** `pipeline_id` 来自函数内部变量，不来自外部输入。

**路径硬编码（🟡 已知问题）**：
```python
issues_path = Path("/Users/zoo/workspace/code/feida_zoo/dashboard/data/issues.json")
```
设计文档 open question #3 已明确提出。daemon 中其他文件路径同样硬编码（如 requirements.json L65/88/1421），属既有模式，不扩大问题。

**无并发锁（🟡 可接受）**：设计文档权衡正确——daemon 改 status/resolved_at，dashboard 改 title/description，字段不重叠，实际冲突概率极低。

**异常降级（✅ 正确）**：
```python
except Exception as e:
    logger.warning(f"⚠️ Pipeline {pipeline_id} 完成后同步 issue 状态失败（降级）: {e}")
```
try/except 包裹完整 I/O 流程，异常不会阻塞 pipeline 完成流程。符合设计文档要求。

---

## 遗漏检查

### 🟢 Issue 1：issues.json 路径不一致

**daemon**（设计文档）：`/Users/zoo/workspace/code/feida_zoo/dashboard/data/issues.json`（绝对路径）

**dashboard** `app_enhanced.py` L859：
```python
return DATA_DIR / "issues.json"  # DATA_DIR = PROJECT_ROOT / "dashboard" / "data"
```
两者等价，但 daemon 无共享常量，依赖硬编码。设计中已注明，不阻塞。

### 🟢 Issue 2：pipeline_status 字段不同步

设计文档 open question #4 提到 `pipeline_status`（在 issues.json 中）不会随 pipeline 推进更新。本修复仅处理 `status=resolved`。`pipeline_status` 字段非用户可见，可后续增强，不阻塞。

### 🟢 Issue 3：历史数据不回溯

已 done 的 pipeline（如 `4b17d3cf`）的 issue 状态不受本次修复影响。设计文档 open question #3 已说明。影响已知，不阻塞。

---

## 改进建议

1. **路径常量提取（建议后续）**：daemon 和 dashboard 共享 `FRAMEWORK_DIR.parent / "dashboard" / "data"` 路径模式，建议提取为共享常量（如 `DASHBOARD_DATA_DIR`），避免未来路径变动时两边都要改。

2. **resolved_at 格式一致性**：daemon 用 `time.strftime("%Y-%m-%dT%H:%M:%S")`，dashboard 用 ISO 格式带毫秒（`2026-05-16T10:59:05.000000`）。建议统一用 ISO 格式。

---

## 结论：**pass**

**理由**：
- 架构方案最优（单点修复，无 API 变更）
- 异常降级正确（pipeline 完成不受影响）
- 字段不重叠，并发风险可接受
- 路径硬编码为既有模式，不扩大问题

---

## 审查摘要

| 检查项 | 结论 |
|--------|------|
| 架构合理性 | ✅ 通过 |
| 安全风险 | ✅ 低风险 |
| 异常降级 | ✅ 正确 |
| 并发安全 | 🟡 可接受（字段不重叠）|
| 路径硬编码 | 🟡 已知（既有模式）|
| 最终结论 | **pass** |
# Design 报告: pl_b58d7c0e — Test no assignee

**阶段**: design  
**设计人**: 阿尔法 (Alpha) 🐢  
**日期**: 2026-05-29  
**需求**: 验证 `pl_e5484dc9` 的 assignee 移除改动已生效

---

## 一、需求评审

### 1.1 需求回顾
- **目标**: 端到端确认 Dashboard 中 assignee 字段已从需求和问题的创建/显示中移除
- **验证范围**: 
  1. 创建需求 API 不应接受/返回 `assignee`
  2. 创建问题 API 不应接受/返回 `assignee`
  3. HTML/JS/CSS 无 assignee 引用
  4. JS 语法正确（`node -c`）
  5. CSS 括号配对正确

### 1.2 可行性评估 ✅
- **可行**: 已有测试 `tests/test_remove_assignee.py` 覆盖，直接运行即可验证
- **依赖**: Dashboard 运行在 18792
- **风险**: 无
- **优先级**: P2（验证性任务）

### 1.3 需求合理性判定
**判定: 合理** ✅

---

## 二、架构设计

### 2.1 What — 验证清单

| # | 验证项 | 方法 |
|---|--------|------|
| 1 | 测试全部通过 | `pytest tests/test_remove_assignee.py -q` |
| 2 | JS 语法正确 | `node -c dashboard/static/dev_center.js` |
| 3 | CSS 括号配对 | `python3 -c 括号深度检查` |
| 4 | Dashboard 运行 | `curl http://127.0.0.1:18792/` |
| 5 | 创建需求无 assignee | `POST /api/requirements → 响应中无 assignee` |
| 6 | 创建问题无 assignee | `POST /api/issues → 响应中无 assignee` |

### 2.2 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/pipeline/pl_b58d7c0e_design.md` | 新增 | 本设计文档 |

# 🐢 架构师任务简报 — 阶段 2：SKILL.md → Harness 迁移 + YAML 废弃

> **发送方**: 阿尔法（玄龟）🐢  
> **接收方**: 织巢（蚂蚁）🐜  
> **版本**: v1.0  
> **日期**: 2026-05-10  
> **前置**: 阶段 1 已完成 ✅（Harness 引擎 + ZooMesh 已就位）

---

## What · 做什么

### 交付物清单

```
framework/core/harness/
  ├── validators.py         ← 新增：元规则代码断言
  └── __init__.py           ← 更新：导出 validators

framework/core/mesh/
  └── persistence.py        ← 新增：task_tracker 持久化升级

framework/shared/zoomesh/
  └── pipeline/             ← 新建：任务状态持久化目录

（以下需删除）
framework/workflows/
  └── default.yaml          ← 废弃：被 pipeline.py 替代
```

### 迁移矩阵（来自 v1.1 §2.8）

| # | 元规则 | 迁移去向 | 验收标准 |
|---|--------|----------|----------|
| 1 | 五件套交接 | `validators.py: validate_delivery()` | 缺任意要素 → 校验拒绝 |
| 2 | P1/P2/P3 分级审核 | `validators.py: parse_review_grade()` | 评分格式不合规 → 拒绝 |
| 4 | 代码合入放行信号 | `validators.py: check_release_signal()` | 无明确放行语 → 不放行 |
| 6 | 所有决策归档 | `DeliverExecutor` 内触发 Aeterna 归档 | 归档事件写入 Event Bus |
| 7 | 园长最终决策 | `Pipeline._handle_cancel()` 限制为园长权限 | 非园长取消 → PermissionError |
| 9 | TDD 开发铁则 | `validators.py: check_tdd_compliance()` | 测试未先行 → 阻塞 |
| 12 | 全链路协同工作流 | **已迁移**（阶段 1 的 FSM 已涵盖） | 无需额外工作 |
| 13 | 跨成员交互铁则 | `AgentSession.send()` 实现 | 消息 > 200 字必须走 shared/ |

**保留在 SKILL.md 的（不迁移）**：§3 不确定就提问 / §5 禁止表演性同意 / §8 对外输出安全 / §14 工作区隔离铁则

### 具体要删除的文件
- `framework/workflows/default.yaml` — 被 pipeline.py 替代
- `framework/core/spawner.py`、`registry_manager.py` 中与 Yaml 流程相关的引用（如有）

---

## Why · 为什么

1. **废除双轨制** — 现在流程有两条路：Harness 代码（pipeline.py）+ YAML（default.yaml），必须统一
2. **消除幻觉根因** — SKILL.md 自然语言流程约束是 LLM 幻觉的最后一个温床，迁完就根除
3. **验证设计可落地** — 阶段 1 造引擎，阶段 2 拿真实规则跑一遍，是 Harness 的真实验证

---

## Tradeoff · 权衡

| 方案 | 优劣 |
|------|------|
| **逐条迁移到 validators.py**（选中） | ✅ 每规则独立函数，可单测；❌ 需要逐条核对不遗漏 |
| 保留 SKILL.md + 代码双重约束 | ❌ 维护两套，混乱 |
| 直接整体删除 YAML + SKILL | ❌ 会漏规则，必须逐条校验 |

---

## Open Questions · 不确定点

1. **§4 放行信号**：明确的关键词列表是什么？建议：`"LGTM"、"通过"、"可以合入"`。Duci 说的 `"条件性通过"` 不算放行
2. **§13 跨成员交互**：`len < 200` 的字数阈值是否合理？建议保持 200 字，后续可配置
3. **旧的 test_state_machine.py**（`tests/test_state_machine.py`）：被新版本（`framework/tests/harness/test_state_machine.py`）替代，是否删除？建议删除避免混淆

---

## Next Action · 期望下一步

1. 读设计文档 v1.1 §2.8 迁移矩阵
2. 实现 `framework/core/harness/validators.py`
3. 实现 `framework/core/mesh/persistence.py`
4. 删除 `framework/workflows/default.yaml` 和重复测试文件
5. 为每个迁移规则写单元测试
6. 完成后通知毒刺审计：`sessions_send(agentId="duci", "阶段 2 完成，请审计")`
7. 审计通过后通知我放行：`sessions_send(agentId="alpha", "阶段 2 已过审，请确认放行")`

---

> **设计者**: 阿尔法 🐢  
> **文件位置**: `framework/shared/alpha_task_brief_stage2_v1.0.md`

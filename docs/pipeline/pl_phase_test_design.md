# Design 报告: pl_phase_test — phase agent 测试

**阶段**: design  
**设计人**: 阿尔法 (Alpha) 🐢  
**日期**: 2026-05-29  
**需求**: 验证 `_pick_phase_agent` 逻辑的正确性

---

## 一、需求评审

### 1.1 需求回顾
- **目标**: 验证 `_pick_phase_agent(phase)` 的 Agent 分配逻辑
- **核心机制**: 通过 `ZooRegistry.get_phase_agent(phase)` 从 `zoo_members.yaml` 的 `responsible_phases` 反向推导

### 1.2 现有逻辑梳理

```
get_phase_agent(phase) 流程：
1. 遍历所有 YAML 成员
2. 收集负责该 phase 且 metadata.is_main_agent != true 的 Agent → candidates
3. candidates 非空 → 返回第一个
4. candidates 为空 → fallback 到主 Agent（panda）也匹配
5. 主 Agent 也不匹配 → 返回 "panda"（硬编码 fallback）

当前 YAML 配置对照：
  design       → alpha            (responsible_phases: [design, develop_wt, develop_code, deliver])
  develop_wt   → alpha
  develop_code → alpha
  deliver      → alpha
  review       → duci             (responsible_phases: [review, verify, audit])
  verify       → duci
  audit        → duci
  requirement  → panda            (fallback: 无成员显式负责 requirement)
  test         → panda            (fallback)
```

### 1.3 可行性评估 ✅
- **可行**: 纯逻辑验证，可写单元测试
- **依赖**: `ZooRegistry` 初始化时需要 YAML 文件可读
- **风险**: 无
- **优先级**: P1（核心 Pipeline 派发机制的正确性保障）

### 1.4 需求合理性判定
**判定: 合理** ✅  
- `_pick_phase_agent` 是 Pipeline 派发的核心路由函数，直接影响 Agent 能否收到正确的阶段通知
- 当前无单元测试覆盖，存在无感知变动的风险

---

## 二、架构设计

### 2.1 What — 产出物

| 产出 | 路径 | 说明 |
|------|------|------|
| Design 文档 | `docs/pipeline/pl_phase_test_design.md` | 本设计文档 |
| 测试用例 | `framework/tests/mesh/test_pick_phase_agent.py` | 覆盖 `get_phase_agent` 全部边界 |

### 2.2 Why — 为什么要测试

- `_pick_phase_agent` 被 9 处代码引用（推进/派发/双通道检测），是 Pipeline 的路由中枢
- 当前逻辑包含三层 fallback（非主 Agent → 主 Agent → "panda"），每一层都有潜在 bug
- YAML 配置文件变动时（如成员状态变更、responsible_phases 调整），无测试保护

### 2.3 Tradeoff

| 选项 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 只手工审查 | 快速 | 不能自动化回归 | ❌ |
| 写单元测试 | 自动化回归、覆盖边界 | 需要 mock YAML 数据 | ✅ |
| 写集成测试 | 真实 YAML 文件 | 依赖文件系统，比单元测试慢 | ✅ 单元+集成 |

### 2.4 接口定义 — 验证清单

```python
# === 正常映射（非主 Agent）===
pick_phase_agent("design")       → "alpha"
pick_phase_agent("review")       → "duci"
pick_phase_agent("audit")        → "duci"

# === Fallback 到主 Agent ===
pick_phase_agent("requirement")  → "panda"  # 无成员负责，主 Agent fallback

# === 全局 fallback ===
pick_phase_agent("unknown_phase") → "panda"  # 谁也匹配不了

# === 边界：主 Agent 筛选 ===
# panda 的 responsible_phases=[] 且 is_main_agent=true
# 正常 phase → 由非主 Agent 处理
# 无匹配 phase → 主 Agent fallback

# === 边界：inactive 成员 ===
# weaver 的 status=inactive，responsible_phases=[]
# 不参与派发
```

### 2.5 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/pipeline/pl_phase_test_design.md` | 新增 | 本设计文档 |
| `framework/tests/mesh/test_pick_phase_agent.py` | 新增 | 单元测试 |

---

## 三、测试用例设计

| TC | 输入 phase | 预期输出 | 覆盖维度 |
|----|-----------|----------|----------|
| 1 | `"design"` | `"alpha"` | 正常非主 Agent 映射 |
| 2 | `"deliver"` | `"alpha"` | 同一 Agent 多 phase |
| 3 | `"review"` | `"duci"` | 不同 Agent 的 phase |
| 4 | `"audit"` | `"duci"` | 同一 Agent 多 phase |
| 5 | `"requirement"` | `"panda"` | 无负责者 → fallback 主 Agent |
| 6 | `"unknown_phase"` | `"panda"` | 全局 fallback |
| 7 | 空字符串 `""` | `"panda"` | 边界：空值 |
| 8 | `"develop_code"` | `"alpha"` | 完整 phase 名称 |

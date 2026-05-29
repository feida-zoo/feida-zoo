# Design 报告: pl_verify_fix — 验证双重修复

**阶段**: design  
**设计人**: 阿尔法 (Alpha) 🐢  
**日期**: 2026-05-29  
**需求**: 验证达达在`zoo_mesh_daemon.py`中的双重修复

---

## 一、需求评审

### 1.1 需求回顾
- **目标**: 验证 `zoo_mesh_daemon.py` 中的两个修复的正确性
- **改动 A**: 将 Agent 可用性检测（`_agent_available`）提前到 status 写入之前，避免"自己刚写完 status 就误判自己忙碌"的自引用问题
- **改动 B**: 在 status 检查中补充 `"cancelled"` 状态，避免已取消的 requirement 被计入忙碌

### 1.2 可行性评估 ✅
- **可行**: 纯逻辑验证，无外部依赖
- **依赖**: 需要了解 daemon 的运行上下文、_agent_available 调用链
- **风险**: 无
- **优先级**: P1（潜在时序 bug，但非阻塞性）

### 1.3 需求合理性判定
**判定: 合理** ✅  
- 两个修复都是真正的时序/边界 bug
- 改动 A 解决了 status 写入→检测的自引用循环
- 改动 B 补充了遗漏的状态枚举值

---

## 二、架构设计

### 2.1 What — 产出物

| 产出 | 路径 | 说明 |
|------|------|------|
| Design 文档 | `docs/pipeline/pl_verify_fix_design.md` | 方案设计 + 验证清单 |
| 验证代码 | `tests/test_verify_fix.py` | 两个修复的单元测试 |

### 2.2 Why — 为什么要这么改

**改动 A — 检测前置：**
```
原来的调用顺序：
  1. status="design" (写入 requirements.json)
  2. _pick_phase_agent("design") → 得出 phase_assignee
  3. _agent_available(phase_assignee) → 遍历所有 requirement，发现自己的 status="design"
  4. → 返回 False（误判）

修复后的顺序：
  1. _pick_phase_agent("design") → 得出 phase_assignee
  2. _agent_available(phase_assignee) → 此时当前 req 的 status 还是 "request"
  3. → 返回 True（正确）
  4. status="design" (写入)
```

**改动 B — cancelled 补全：**
- `_agent_available` 的 status 检查白名单是 `("done", "rejected", "request", "")`
- 缺少 `"cancelled"`，导致已取消的 requirement 让 Agent 被误判为忙碌

### 2.3 Tradeoff

| 选项 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 不修（维持现状） | 不改代码 | daemon 重启后首次推进可能触发误判 | ❌ |
| 只修 A | 解决时序问题 | cancelled 仍可能误判 | ❌ |
| 只修 B | 补全状态枚举 | 时序问题仍在 | ❌ |
| 两个都修 （✅） | 彻底解决 | 无显著缺点 | ✅ |

### 2.4 接口定义 — 验证方案

```python
def test_agent_available_no_self_reference():
    """TC-A: 当前 req 的 status 不应被计入 Agent 忙碌判断"""
    # 构造：1 个 requirement，status="request"，assignee="alpha"
    # 预期：_agent_available("alpha") → True

def test_agent_available_cancelled_not_busy():
    """TC-B: cancelled 状态的 req 不应让 Agent 被误判为忙碌"""
    # 构造：1 个 requirement，status="cancelled"，assignee="alpha"
    # 预期：_agent_available("alpha") → True
```

### 2.5 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/pipeline/pl_verify_fix_design.md` | 新增 | 本设计文档 |
| `tests/test_verify_fix.py` | 新增（可选） | 验证测试 |

---

## 三、验证清单

### 3.1 改动 A 验证维度

- [x] 代码顺序是否正确：检测在 status 写入之前
- [x] `_agent_available` 遍历时当前 req 的 status 仍是旧状态
- [x] 无其他位置存在同样问题

### 3.2 改动 B 验证维度

- [x] `"cancelled"` 加入白名单
- [x] `"cancelled"` 在所有 `_agent_available` 调用链中生效
- [x] 无其他遗漏状态（`"delivered"`, `"pending_review"` 等是否也在白名单？—— 不在，因为它们是 active 状态，Agent 应当忙碌）

### 3.3 单元测试

| TC | 描述 | 预期 |
|----|------|------|
| TC-A | 当前无 active 需求时，Agent 可用 | True |
| TC-B | 当前 req 即将推进（status 未写），Agent 可用 | True |
| TC-C | 其他 Agent 正在忙碌，当前 Agent 可用 | True |
| TC-D | cancelled 状态不阻塞 Agent | True |
| TC-E | active 状态（"design"/"review"/etc）正确阻塞 Agent | False |

# P2 技术设计方案：看板tab页数据不随工作流变化

## 问题
看板数据存在三个问题：
1. 历史内容残留（来自 task_tracker.json 的旧任务数据，如"Dashboard 动态监控增强"等）
2. 新增需求和问题未在看板呈现
3. 工作流推进时看板项目状态不更新

## 根因分析
经检查，`_get_kanban_data()` 从三个数据源合并：
- task_tracker.json（历史任务——问题1的根因）
- requirements.json（当前需求——问题2和3已由 ZooMesh Pipeline 自动更新）
- ZooMesh pipeline 状态文件

问题2和3：**当前 ZooMesh 运行后已自动修复。** 新增的 issue/requirement 会自动进入 Pipeline，Pipeline 状态变更后会写入 requirements.json，看板读取 requirements.json 时能正确映射状态。

问题1：task_tracker.json 中残留了大量旧阶段的历史任务（P1 架构阶段、P2 生态阶段的任务），这些不应该出现在看板上。

## 改动方案
仅修改 `app_enhanced.py` 的 `_get_kanban_data()`，**过滤掉 task_tracker.json 中非当前活跃 pipeline 的旧任务数据**。

具体：
- 保留 task_tracker.json 中 `is_current_phase: true` 的任务（当前阶段的里程碑）
- 过滤掉所有已完成的旧阶段任务（P1/P2 时代的历史注释）
- 看板数据以 requirements.json + ZooMesh pipeline 状态为主

## 受审项
- [ ] 方案是否正确
- [ ] 过滤条件是否合理（保留 is_current_phase）
- [ ] 是否有副作用

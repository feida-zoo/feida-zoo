# P0 技术设计方案：问题管理提交→ZooMesh联动

## 问题描述
在 Dashboard 的问题管理页面提交问题后，问题只写入 `issues.json`，没有推送到 ZooMesh 触发 Pipeline 工作流。导致问题提了没人处理。

## 方案

### 改动范围
仅修改 `dashboard/app_enhanced.py` 的 `_handle_issues_post()` 方法。

### 具体设计

在 `_handle_issues_post()` 保存 issue 到 `issues.json` **之后**，增加以下步骤：

1. 生成 pipeline_id（格式 `pl_<uuid[:8]>`）
2. 构造 pipeline_request payload 包含：
   - type: "pipeline_request"
   - task_id: 生成的 pipeline_id
   - requirement_id: issue 的 id
   - title: issue 标题
   - description: issue 描述
   - assignee: issue 的 assignee 或 fallback "alpha"
   - priority: issue 优先级
3. 通过 HTTP POST 发送到 ZooMesh Chat API：
   - URL: `http://127.0.0.1:18793/api/chat`
   - Body: `{"from": "dashboard", "content": "@panda 新Pipeline请求: <payload_json>"}`
4. 将 pipeline_id 写入 issue 对象（用于追踪）

### 约束
- 不会阻塞 issue 创建流程（失败不影响保存）
- 所有优先级（P0-P3）的问题都推送，由 Pipeline 的 PHASE_DEFAULT_AGENT 决定处理人
- 使用现有的 ZooMesh Chat API 通道，无需新增端点

### 失败处理
- try/except 包裹推送逻辑，失败仅打 log 不抛异常
- issue 本身已持久化到 issues.json，不会丢失

### 前提
ZooMesh daemon 必须运行在 127.0.0.1:18793（与 dashboard 的 ZOO_MESH_HTTP 配置一致）

## 待审事项
- [ ] 推送时机是否合适（issue 保存后立刻推送）
- [ ] payload 字段是否完整
- [ ] 失败处理是否合理
- [ ] 是否有安全风险

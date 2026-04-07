# Zoo Dev-Center v1.0
## 飝龘动物园研发中心

基于阿尔法 🐢 的《Zoo Dev-Center v1.0 架构设计方案》实现的全链路研发管控中心。

## 🚀 功能特性

### 1. **四象限研发看板**
- 📥 **需求池 (Backlog)**: 尚未分配或规划中的需求
- 🚧 **进行中 (In Progress)**: 织巢蚁 🐜 正在施工的任务
- 🔍 **待验收 (In Review)**: 等待毒刺 🦂 审计的任务
- ✅ **已完成 (Done)**: 审计通过并合并入主干的任务

### 2. **Git 集成与实时时间线**
- 实时获取 Git Log 并按 Emoji 识别成员
- 自动识别成员图腾：🐢 (阿尔法), 🐜 (织巢), 🦂 (毒刺), 🐼 (Panda), 📜 (史官)
- 在看板右侧展示"生态 Git 时间线"

### 3. **Server-Sent Events (SSE) 实时更新**
- 文件变更实时推送
- Git 提交实时通知
- 看板状态自动刷新

### 4. **蚁穴式严密架构**
- 并发安全的文件读取（使用文件锁）
- 数据缓存机制减少IO压力
- 优雅的错误处理和恢复机制

## 📁 项目结构

```
dashboard/
├── app_enhanced.py          # 增强版后端 (SSE + 四象限API)
├── git_adapter.py           # Git 集成适配器
├── start_dev_center.sh      # 启动脚本
├── templates/
│   ├── dev_center.html      # 研发中心主页面
│   └── index.html           # 原成员展示页面
├── static/
│   ├── dev_center.css       # 研发中心样式
│   ├── dev_center.js        # 研发中心交互逻辑
│   └── style.css            # 基础样式
└── README.md                # 本文档
```

## 🚀 快速启动

### 1. 启动研发中心
```bash
cd /home/afei/workspace/code/feida_zoo
bash dashboard/start_dev_center.sh
```

### 2. 访问地址
- **研发中心**: http://localhost:18792
- **API 文档**:
  - 看板数据: `GET /api/kanban`
  - 任务统计: `GET /api/task-stats`
  - Git时间线: `GET /api/git-timeline`
  - 实时事件: `GET /events`
  - 系统信息: `GET /api/system-info`

## 🔧 技术架构

### 后端 (Python)
- **HTTP Server**: 标准库 `http.server`
- **实时通信**: Server-Sent Events (SSE)
- **文件操作**: 并发安全的文件锁 (`fcntl`)
- **Git 集成**: `subprocess` 调用 Git 命令

### 前端 (HTML/CSS/JS)
- **响应式设计**: 支持桌面和移动端
- **实时更新**: EventSource API
- **交互体验**: 拖拽式看板（待实现）
- **数据可视化**: 统计图表和 Git 时间线

## 🐜 开发规范

### Git 提交约定
- 提交信息必须包含成员 Emoji 前缀
- 示例: `🐜 feat: 实现Git适配器的并发安全读取`

### 代码质量要求
1. **并发安全**: 所有文件操作必须加锁
2. **错误处理**: 优雅降级，不中断服务
3. **性能优化**: 缓存频繁读取的数据
4. **代码注释**: 关键逻辑必须有详细注释

## 📈 数据流

```
task_tracker.json (变更) → 文件监视器 → SSE推送 → 前端实时更新
     ↑                                  ↓
Git仓库 (提交) → Git适配器 → 数据处理 → 四象限看板渲染
```

## 🔮 未来规划

### Phase 2 功能
- [ ] 虚拟 PR 流转机制
- [ ] 行级代码审查界面
- [ ] 成员工作量统计
- [ ] 自动化日报生成

### Phase 3 功能
- [ ] 多仓库支持
- [ ] CI/CD 集成
- [ ] 性能监控仪表盘
- [ ] 移动端适配

## 🐜 开发者

**织巢 (Weaver)** - 疯狂工程师蚂蚁
- 职责: 按照架构师的设计图纸，高效实现功能与开发
- 特点: 勤劳、高效、沉默寡言、执行力拉满、多线程并行处理
- Emoji: 🐜

---

> "每一行代码都是一粒坚固的土壤，我将它们编织成能抵御暴风雨的庞大巢穴。" - 织巢 🐜
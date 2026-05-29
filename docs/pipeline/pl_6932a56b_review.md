# Review 报告: pl_6932a56b — 飝龘动物园 README 过时更新

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: review  
**审查对象**: 当前仓库 `README.md`（上游无 design/impl commit，直接审查现有 README 现状）

---

## 一、现状分析

当前 `README.md` 仅 13 行，内容如下：

```markdown
# 飝龘动物园 (Feida Zoo) 项目仓库
## 成员列表
| 定位 | 名字 | 种族 | 专属大脑 | 核心职责 | 专属emoji |
| 中枢调度大管家 | 达达 (Panda) | 熊猫 🐼 | MiniMax-M2.7 | 对接园长、任务调度、全局协调 | 🐼 |
| 首席架构师 | 阿尔法 (Alpha) | 玄龟 🐢 | DeepSeek V4 Flash | 系统设计、规则制定、架构评审 | 🐢 |
| 疯狂工程师 | 织巢 (Weaver) | 蚂蚁 🐜 | MiniMax-M2.7 | 代码实现、功能开发、问题修复 | 🐜 |
| 无情审计师 | 毒刺 (Duci) | 蝎子 🦂 | GLM-5.1 | 漏洞挖掘、代码审计、压测试毒 | 🦂 |
| 永恒史官 | Aeterna (埃特娜) | 黑曜石 🪨 | MiniMax-M2.7 | 记忆归档、文档撰写、知识库维护 | 🪨 |
| 美术设计师 | 咕噜 (Gulu) | 史莱姆 🟢 | MiniMax-M2.7 | UI设计、原画创作、视觉输出 | 🟢 |

## 核心守则
详见 
```

---

## 二、架构合理性

### P0 — 成员列表严重过时

1. **已退出活跃成员仍列出**: Weaver（织巢）、Aeterna（埃特娜）、Gulu（咕噜）已于 2026-05-14 退出活跃成员，但 README 仍列为完整成员。这是最核心的事实性错误。

2. **硬编码路径**: `dashboard/app_v2.py` 中 `PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")` 写死绝对路径，而当前仓库实际运行在 `/Volumes/data/workspace/code/feida_zoo`（macOS）。README 未说明部署环境差异。

### P1 — README 结构严重缺失

3. **"核心守则"断裂**: `详见` 后无任何链接或内容，信息丢失。

4. **缺少项目概述**: 没有说明这是什么项目、做什么用、解决什么问题。

5. **缺少项目结构说明**: 仓库包含 `dashboard/`、`agents/`、`framework/`、`scripts/`、`plugins/`、`skills/` 等目录，README 完全未提及。

6. **缺少安装/运行指南**: `dashboard/README.md` 有启动说明但主 README 没有。访问地址、依赖安装、启动命令均缺失。

7. **缺少界面截图**: 需求明确要求附上界面截图，当前 README 无任何图片。

8. **缺少技术栈说明**: Python 后端 + 原生前端 + SSE 实时通信，未在主 README 说明。

9. **缺少 Pipeline 机制说明**: 这是项目的核心工作流（需求→设计→开发→测试→审计→交付），README 完全未介绍。

### P2 — 信息准确性

10. **模型版本可能过时**: README 列出的模型（MiniMax-M2.7、DeepSeek V4 Flash、GLM-5.1）需与实际运行配置核对。

11. **Dashboard README 同步问题**: `dashboard/README.md` 将自己标注为"Zoo Dev-Center v1.0"且包含 Phase 2/3 规划，可能与实际进展不符。

---

## 三、安全风险

12. **硬编码路径泄露**: `dashboard/app_v2.py` 包含用户主目录路径 `/home/afei/`，README 如果引用该路径会暴露服务器用户名和目录结构。**修复方案**: README 中使用相对路径或环境变量说明。

13. **端口信息暴露**: Dashboard 运行在 18792，Daemon 运行在 18793。公开 README 暴露端口号虽非高危，但需确认是否需要内网限定。

---

## 四、遗漏检查

14. **Pipeline 工作流**: README 完全没有介绍 Zoo Pipeline 机制（需求管理 → 多阶段流转 → 自动化上报），这是项目的核心协作机制。

15. **成员头像展示**: `agents/*/avatar.png` 和 `dashboard/static/avatars/*.png` 存在头像资源，README 可展示但未使用。

16. **plugins/zoo-pipeline**: 项目包含 OpenClaw 插件，README 未提及。

17. **脚本工具说明**: `scripts/zoo-phase-complete`、`scripts/zoo-service-restart` 是运维关键工具，README 未介绍。

18. **需求管理**: `dashboard/data/requirements.json` 包含 24 条需求记录（20 done + 4 cancelled），README 未提及需求管理功能。

---

## 五、改进建议

### 必须修复（P0）

| # | 问题 | 建议 |
|---|------|------|
| 1 | 退出成员仍列出 | 移除 Weaver/Aeterna/Gulu，或标注为「已归档」成员。仅保留活跃成员：达达、阿尔法、毒刺 |
| 2 | "核心守则"断裂 | 补全链接或内联内容，删除空链接 |

### 应该修复（P1）

| # | 问题 | 建议 |
|---|------|------|
| 3 | 无项目概述 | 新增项目简介段落：说明动物园是什么、做什么 |
| 4 | 无项目结构 | 新增目录结构说明（agents/dashboard/framework/scripts/plugins/skills） |
| 5 | 无运行指南 | 新增安装依赖 + 启动命令 + 访问地址 |
| 6 | 无界面截图 | 新增 Dashboard 界面截图（需求管理/看板/成员管理/聊天室） |
| 7 | 无技术栈 | 新增技术栈段落 |
| 8 | 无 Pipeline 介绍 | 新增 Pipeline 工作流说明 |

### 建议优化（P2）

| # | 问题 | 建议 |
|---|------|------|
| 9 | 模型版本核对 | 核对实际模型配置，确保 README 列出的是当前使用的版本 |
| 10 | Dashboard README 同步 | 审查 dashboard/README.md 是否与主 README 保持一致 |

---

## 六、判定

**REJECT**

理由：
1. **P0 事实性错误**: 成员列表包含已退出活跃的3位成员，严重误导读者
2. **P0 内容断裂**: "核心守则"链接为空，信息丢失
3. **P1 结构性缺失**: 无项目概述、无结构说明、无运行指南、无截图——作为项目 README，核心要素全部缺失
4. 需求明确要求「附上界面截图」，当前完全未满足

上游（design/impl）需产出：
- 更新后的 README.md（含活跃成员、项目概述、目录结构、运行指南、Pipeline 介绍、技术栈）
- 至少 3 张界面截图（看板/成员管理/聊天室）
- 核心守则链接修复

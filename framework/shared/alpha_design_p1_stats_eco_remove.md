# P1 技术设计方案：统计页去除生态成员栏

## 问题
统计页的「生态成员」栏目与成员管理页重复，且压缩了统计页其他栏目的显示空间，导致 UI 变形。

## 现状分析
统计页（Tab 2）当前包含 6 个卡片：
1. 项目概览
2. 成员状态
3. Git 统计
4. 当前阶段
5. Git 时间线
6. **生态成员** ⬅ 问题所在

成员管理（Tab 5）已完整显示所有成员详细信息（头像、名称、角色、模型等），「生态成员」卡片是其子集，完全冗余。

## 改动方案
仅修改 `dashboard/templates/dev_center.html`：
- 删除 `<div class="stats-card"><h3>生态成员</h3>...</div>` 块（第 159-167 行）

无需改动 JS：
- `dev_center.js` 中生态成员通过 `id="members-loading"` / `id="members-list"` 加载
- 删除后该部分 JS 不再触发，无副作用
- 看板（tab-kanban）也有自己的 members-container，不受影响

## 影响范围
- 文件：仅 `dashboard/templates/dev_center.html`
- 无后端改动
- 无 JS 逻辑改动

## 受审
- [ ] 方案是否正确
- [ ] 是否影响其他 tab 的成员加载

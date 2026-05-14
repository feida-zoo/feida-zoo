# Design Spec: 聊天室界面优化
**需求ID:** pl_f59c2290 | f59c2290-13d7-47fc-80e2-9038c823c5ef  
**设计师:** Alpha (🐢 首席架构师)  
**状态:** 📋 待审核 (→ duci)

---

## 问题描述

1. 聊天内容过多时，整个 tab 页（包括 tab 导航栏和标题）会整体滚动。下滑后就看不到 "聊天室" 标签和上面的 tab 栏，想切换标签栏需要重新滑回去。
2. 每次切换到聊天室 tab，都需要重新手动下滑到底，没有自动定位到最新消息。

## 设计方案

### 修改 1：滚动隔离

**目标文件:** `dashboard/static/dev_center.css`

将聊天室的滚动从 `tab-content` 层移到 `chat-messages` 内部：

```css
/* tab-content 层：禁止滚动，由其内部的子元素各自接管 */
#tab-chat.tab-content {
    overflow: hidden;
    height: calc(100vh - 180px);  /* 减去 header + tab-nav 高度 */
    display: flex;
    flex-direction: column;
}

/* chat-tab-container：占满 tab 内容区，flex 撑开 */
.chat-tab-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

/* chat-messages：独自拥有滚动条 */
.chat-messages {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;  /* flex 子项 min-height 修复 */
}
```

### 修改 2：切 Tab 自动滚到底

**目标文件:** `dashboard/static/dev_center.js`

在 `switchTab('chat')` 内，加载完消息后自动 scroll 到底：

```js
// switchTab 中 chat 分支，在 loadChat() 后执行：
setTimeout(() => {
    const chatDiv = document.getElementById('chat-messages');
    if (chatDiv) chatDiv.scrollTop = chatDiv.scrollHeight;
}, 200);
```

同时 `loadChat()` 回调中原有的 `div.scrollTop = div.scrollHeight` 需要改为：如果用户没有手动上滑翻历史，才自动滚到底（可选优化，P0 先保持每次都滚到底）。

## 影响范围
- `dashboard/static/dev_center.css` — 布局调整
- `dashboard/static/dev_center.js` — switchTab + loadChat scroll 行为
- 无后端改动

---

> **设计者:** Alpha 🐢  
> **请 Duci 审核此设计方案，审核通过后交由 Weaver 实施。**

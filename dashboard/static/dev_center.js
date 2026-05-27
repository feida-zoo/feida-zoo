// Zoo Dev-Center JavaScript
// 实现四象限看板、Git时间线和实时更新的交互功能

// ===== Tab 切换 =====
function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === 'tab-' + tabId);
    });
    // Resize kanban if needed
    if (tabId === 'kanban' && window.zooDevCenter) {
        setTimeout(() => window.zooDevCenter.loadKanbanData(), 100);
    }
    // Load chat messages when switching to chat tab
    if (tabId === 'chat') {
        loadChat();
        // 切到聊天室 tab 自动滚到底
        setTimeout(() => {
            const chatDiv = document.getElementById('chat-messages');
            if (chatDiv) chatDiv.scrollTop = chatDiv.scrollHeight;
        }, 200);
        if (window._chatInterval) {
            clearInterval(window._chatInterval);
        }
        window._chatInterval = setInterval(loadChat, 3000);
    } else if (window._chatInterval) {
        clearInterval(window._chatInterval);
    }
    // Load requirements list when switching to requirements tab
    if (tabId === 'requirements') {
        loadRequirementsList();
    }
    // Load members when switching to members tab
    if (tabId === 'members') {
        window.zooDevCenter.loadMembers();
    }
    // Load issues when switching to issues tab
    if (tabId === 'issues') {
        loadIssues();
    }
}

class ZooDevCenter {
    constructor() {
        this.baseUrl = window.location.origin;
        this.eventSource = null;
        this.eventCount = 0;
        this.autoRefresh = true;
        this.autoRefreshInterval = null;
        this.lastKanbanUpdate = null;
        this.lastTimelineUpdate = null;
        this.currentProject = 'feida_zoo';
        
        // @mention support
        this.mentionAgents = [
            { id: 'alpha', name: '阿尔法', emoji: '🐢' },
            { id: 'duci', name: '毒刺', emoji: '🦂' },
            { id: 'panda', name: '达达', emoji: '🐼' }
        ];
        
        // 成员 Emoji 映射
        this.memberEmojiMap = {
            'alpha': '🐢',
            'duci': '🦂',
            'panda': '🐼'
        };
        
        // 成员名称统一映射（无论后端返回什么name，前端统一显示）
        this.memberNameMap = {
            'alpha': '阿尔法',
            'duci': '毒刺',
            'panda': '达达'
        };
        
        // 状态文本映射
        this.statusTextMap = {
            'executing': '执行中',
            'idle': '空闲',
            'unknown': '离线'
        };
        
        // 初始化
        this.init();
    }
    
    init() {
        // 绑定事件监听器
        this.bindEvents();
        
        // 初始化 @mention 支持
        this.initMentionSupport();
        
        // 加载初始数据
        this.loadInitialData();
        
        // 建立 SSE 连接
        this.connectSSE();
        
        // 启动自动刷新
        this.startAutoRefresh();
        
        // 初始化聊天
        this.initChat();
    }
    
    bindEvents() {
        // 刷新看板按钮
        const refreshKanban = document.getElementById('refresh-kanban');
        if (refreshKanban) {
            refreshKanban.addEventListener('click', () => {
                this.loadKanbanData();
            });
        }
        
        // 刷新时间线按钮
        const refreshTimeline = document.getElementById('refresh-timeline');
        if (refreshTimeline) {
            refreshTimeline.addEventListener('click', () => {
                this.loadGitTimeline();
            });
        }
        
        // 模态框关闭按钮
        const modalClose = document.getElementById('modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                this.closeTaskModal();
            });
        }
        
        // 点击模态框背景关闭
        const taskModal = document.getElementById('task-modal');
        if (taskModal) {
            taskModal.addEventListener('click', (e) => {
                if (e.target.id === 'task-modal') {
                    this.closeTaskModal();
                }
            });
        }
        
        // 每小时刷新成员数据
        this._membersRefreshInterval = null;
        
        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeTaskModal();
            }
            if (e.key === 'r' && e.ctrlKey) {
                e.preventDefault();
                this.loadKanbanData();
            }
        });
    }
    
    initMentionSupport() {
        const input = document.getElementById('chat-input');
        if (!input) return;
        
        const dropdown = document.getElementById('mention-dropdown');
        let mentionActive = false;
        let mentionQuery = '';
        let selectedIndex = -1;
        
        input.addEventListener('input', () => {
            const pos = input.selectionStart;
            const text = input.value.substring(0, pos);
            const atMatch = text.match(/@(\w*)$/);
            
            if (atMatch) {
                mentionQuery = atMatch[1].toLowerCase();
                mentionActive = true;
                const filtered = this.mentionAgents.filter(a => 
                    a.id.includes(mentionQuery) || a.name.includes(mentionQuery)
                );
                
                if (filtered.length > 0) {
                    dropdown.style.display = 'block';
                    dropdown.innerHTML = filtered.map((a, i) => 
                        `<div class="mention-item ${i === 0 ? 'active' : ''}" data-id="${a.id}">
                            <span class="mention-emoji">${a.emoji}</span>
                            <span>@${a.id}</span>
                            <span class="mention-name">${a.name}</span>
                        </div>`
                    ).join('');
                    selectedIndex = 0;
                    
                    dropdown.querySelectorAll('.mention-item').forEach((el, i) => {
                        el.addEventListener('click', () => {
                            this.insertMention(input, el.dataset.id);
                            dropdown.style.display = 'none';
                            mentionActive = false;
                        });
                        el.addEventListener('mouseenter', () => {
                            dropdown.querySelectorAll('.mention-item').forEach(e => e.classList.remove('active'));
                            el.classList.add('active');
                            selectedIndex = i;
                        });
                    });
                } else {
                    dropdown.style.display = 'none';
                }
            } else {
                dropdown.style.display = 'none';
                mentionActive = false;
            }
        });
        
        input.addEventListener('keydown', (e) => {
            if (!mentionActive || dropdown.style.display === 'none') return;
            
            const items = dropdown.querySelectorAll('.mention-item');
            if (items.length === 0) return;
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % items.length;
                items.forEach((el, i) => el.classList.toggle('active', i === selectedIndex));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                items.forEach((el, i) => el.classList.toggle('active', i === selectedIndex));
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                const activeItem = dropdown.querySelector('.mention-item.active');
                if (activeItem) {
                    this.insertMention(input, activeItem.dataset.id);
                    dropdown.style.display = 'none';
                    mentionActive = false;
                }
            } else if (e.key === 'Escape') {
                dropdown.style.display = 'none';
                mentionActive = false;
            }
        });
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-mention-wrapper')) {
                dropdown.style.display = 'none';
                mentionActive = false;
            }
        });
    }
    
    insertMention(input, agentId) {
        const pos = input.selectionStart;
        const before = input.value.substring(0, pos);
        const after = input.value.substring(pos);
        const atIdx = before.lastIndexOf('@');
        const prefix = before.substring(0, atIdx);
        input.value = prefix + '@' + agentId + ' ' + after;
        const newPos = prefix.length + agentId.length + 2;
        input.setSelectionRange(newPos, newPos);
        input.focus();
    }
    
    initChat() {
        // Enter key sends message
        const input = document.getElementById('chat-input');
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendChat();
                }
            });
        }
    }
    
    loadInitialData() {
        // 并行加载所有初始数据
        Promise.all([
            this.loadTaskStats(),
            this.loadKanbanData(),
            this.loadGitTimeline(),
            this.loadGitStats(),
            this.loadMemberStatus(),
            this.loadMemberCards()
        ]).then(() => {
            console.log('所有初始数据加载完成');
        }).catch(error => {
            console.error('加载初始数据时出错:', error);
            this.showError('加载数据失败，请刷新页面重试');
        });
    }
    
    async loadMemberStatus() {
        try {
            // 同时获取成员详细信息和状态
            const [membersResponse, statusResponse] = await Promise.all([
                fetch('/api/members'),
                fetch('/api/member-status')
            ]);
            
            if (!membersResponse.ok) throw new Error(`获取成员详情失败: HTTP ${membersResponse.status}`);
            if (!statusResponse.ok) throw new Error(`获取成员状态失败: HTTP ${statusResponse.status}`);
            
            const membersData = await membersResponse.json();
            const statusData = await statusResponse.json();
            
            // 合并数据
            const combinedData = { members: membersData, status: statusData };
            this.renderMemberStatus(combinedData);
        } catch (error) {
            console.error('加载成员状态失败:', error);
            // 回退到只显示状态
            try {
                const response = await fetch('/api/member-status');
                if (response.ok) {
                    const data = await response.json();
                    this.renderMemberStatus({ status: data, members: [] });
                }
            } catch (fallbackError) {
                console.error('回退加载也失败:', fallbackError);
            }
        }
    }
    
    renderMemberStatus(data) {
        const listEl = document.getElementById('member-status-list');
        if (!listEl) return;
        
        const membersData = data.members || [];
        const statusData = data.status || {};
        
        // 如果没有成员详细数据，使用完整的成员列表（统一显示名称）
        const members = membersData.length > 0 ? membersData.map(m => ({
            ...m,
            name: this.memberNameMap[m.id] || m.name
        })) : [
            { id: 'alpha', name: '阿尔法', code_name: 'Alpha', role_display: '首席架构师 · 玄龟', avatar_emoji: '🐢' },
            { id: 'duci', name: '毒刺', code_name: 'Duci', role_display: '代码审计师 · 毒刺蝎', avatar_emoji: '🦂' },
            { id: 'panda', name: '达达', code_name: 'Panda', role_display: '调度者 · 熊猫', avatar_emoji: '🐼' }
        ];
        
        let html = '<div class="member-status-grid">';
        
        members.forEach(member => {
            const status = statusData[member.id] || 'unknown';
            const statusClass = status === 'executing' ? 'status-executing' : (status === 'idle' ? 'status-idle' : 'status-unknown');
            const statusText = this.statusTextMap[status] || '未知';
            
            html += `
                <div class="member-status-item">
                    <div class="member-info-mini">
                        <span class="member-emoji">${member.avatar_emoji || this.memberEmojiMap[member.id] || '🐾'}</span>
                        <span class="member-name">${member.name}</span>
                    </div>
                    <div class="member-details-mini">
                        <span class="member-role" title="${this.escapeHtml(member.role_display || '')}">${this.escapeHtml(member.role_display || '未知角色')}</span>
                        <span class="member-model" title="模型">${member.model || '未知模型'}</span>
                    </div>
                    <div class="status-badge ${statusClass}">
                        <span class="status-dot"></span>
                        <span class="status-label">${statusText}</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        listEl.innerHTML = html;
        
        // 更新看板中的头像状态
        this.updateKanbanAssigneeStatus(statusData);
    }
    
    updateKanbanAssigneeStatus(statusData) {
        document.querySelectorAll('.task-assignee').forEach(el => {
            const nameSpan = el.querySelector('span');
            if (!nameSpan) return;
            
            const assigneeName = nameSpan.textContent.trim();
            // 简单映射名称到ID
            const nameToId = {
                '阿尔法': 'alpha', '毒刺': 'duci', 
                '达达': 'panda'
            };
            
            const id = nameToId[assigneeName] || assigneeName.toLowerCase();
            const status = statusData[id];
            
            if (status) {
                if (status === 'executing') {
                    el.classList.add('is-executing');
                } else {
                    el.classList.remove('is-executing');
                }
            }
        });
    }

    async loadMemberCards() {
        const loadingEl = document.getElementById('members-loading');
        const listEl = document.getElementById('members-list');
        
        if (!loadingEl || !listEl) return;
        
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        try {
            const response = await fetch('/api/members');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const memberData = await response.json();
            this.renderMemberCards(memberData);
        } catch (error) {
            console.error('加载成员卡片失败:', error);
            loadingEl.innerHTML = `
                <div style="text-align: center; color: #e74c3c;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span>加载失败</span>
                </div>
            `;
        }
    }
    
    renderMemberCards(memberData) {
        const listEl = document.getElementById('members-list');
        const loadingEl = document.getElementById('members-loading');
        
        if (!listEl || !loadingEl) return;
        
        // 清空现有内容
        listEl.innerHTML = '';
        
        if (!memberData || memberData.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-users"></i>
                    <p>暂无成员数据</p>
                </div>
            `;
        } else {
            // 创建成员卡片网格
            const gridEl = document.createElement('div');
            gridEl.className = 'members-grid';
            
            memberData.forEach(member => {
                // 统一名称显示
                const displayName = this.memberNameMap[member.id] || member.name;
                const memberCard = this.createMemberCard({...member, name: displayName});
                gridEl.appendChild(memberCard);
            });
            
            listEl.appendChild(gridEl);
        }
        
        // 显示成员列表并隐藏加载状态
        listEl.style.display = 'block';
        loadingEl.style.display = 'none';
    }
    
    createMemberCard(member) {
        const cardEl = document.createElement('div');
        cardEl.className = 'member-card';
        
        // 获取成员 Emoji 和头像
        const memberEmoji = member.avatar_emoji || this.memberEmojiMap[member.id] || '🐾';
        const displayName = this.memberNameMap[member.id] || member.name;
        
        cardEl.innerHTML = `
            <div class="member-card-header">
                <div class="member-avatar">
                    <img src="/avatar/${member.id}" alt="${this.escapeHtml(displayName)}" 
                         class="member-avatar-img" 
                         onerror="this.style.display='none'; this.parentElement.innerHTML='${memberEmoji}'; this.parentElement.className='member-avatar member-avatar-fallback';">
                </div>
                <div class="member-title">
                    <h4 class="member-name">${this.escapeHtml(displayName)}</h4>
                    <div class="member-code-name">${this.escapeHtml(member.code_name || '')}</div>
                </div>
            </div>
            <div class="member-card-body">
                <div class="member-field">
                    <span class="field-label">角色:</span>
                    <span class="field-value">${this.escapeHtml(member.role_display || '')}</span>
                </div>
                <div class="member-field">
                    <span class="field-label">种族:</span>
                    <span class="field-value">${this.escapeHtml(member.species || '')}</span>
                </div>
                <div class="member-field">
                    <span class="field-label">模型:</span>
                    <span class="field-value">${this.escapeHtml(member.model || '')}</span>
                </div>
            </div>
            <div class="member-card-footer">
                <div class="member-description">${this.escapeHtml(member.description || '暂无描述')}</div>
            </div>
        `;
        
        return cardEl;
    }

    async loadTaskStats() {
        try {
            const response = await fetch('/api/task-stats');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.updateTaskStats(data);
            this.updateCurrentPhase(data);
        } catch (error) {
            console.error('加载任务统计失败:', error);
        }
    }
    
    async loadKanbanData() {
        const loadingEl = document.getElementById('kanban-loading');
        const columnsEl = document.getElementById('kanban-columns');
        
        loadingEl.style.display = 'flex';
        columnsEl.style.display = 'none';
        
        try {
            const response = await fetch('/api/kanban');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.renderKanban(data);
            this.lastKanbanUpdate = new Date();
            this.updateLastUpdated();
        } catch (error) {
            console.error('加载看板数据失败:', error);
            loadingEl.innerHTML = `
                <div style="text-align: center; color: #e74c3c;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 10px;"></i>
                    <p>加载看板数据失败</p>
                    <button onclick="window.location.reload()" style="margin-top: 10px; padding: 5px 15px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        刷新页面
                    </button>
                </div>
            `;
        }
    }
    
    async loadGitTimeline() {
        const loadingEl = document.getElementById('timeline-loading');
        const listEl = document.getElementById('timeline-list');
        
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        try {
            const response = await fetch(`/api/git-timeline?project=${this.currentProject}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.renderGitTimeline(data);
            this.renderProjectSwitcher(data.projects);
            this.lastTimelineUpdate = new Date();
        } catch (error) {
            console.error('加载Git时间线失败:', error);
            loadingEl.innerHTML = `
                <div style="text-align: center; color: #e74c3c;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span>加载失败</span>
                </div>
            `;
        }
    }
    
    renderProjectSwitcher(projects) {
        const containerEl = document.getElementById('project-switcher');
        if (!containerEl || !projects) return;
        
        containerEl.innerHTML = `
            <select id="project-select" class="project-select">
                ${Object.entries(projects).map(([key, proj]) => `
                    <option value="${key}" ${key === this.currentProject ? 'selected' : ''}>
                        ${proj.emoji} ${proj.name}
                    </option>
                `).join('')}
            </select>
        `;
        
        document.getElementById('project-select').addEventListener('change', (e) => {
            this.currentProject = e.target.value;
            this.loadGitTimeline();
        });
    }
    
    async loadGitStats() {
        try {
            const response = await fetch('/api/git-stats');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.renderGitStats(data);
        } catch (error) {
            console.error('加载Git统计失败:', error);
        }
    }
    
    updateTaskStats(stats) {
        // 更新统计数字
        document.getElementById('total-tasks').textContent = stats.total_tasks || 0;
        document.getElementById('completed-tasks').textContent = stats.completed_tasks || 0;
        document.getElementById('completion-rate').textContent = `${stats.completion_rate || 0}%`;
        document.getElementById('in-progress-tasks').textContent = stats.in_progress_tasks || 0;
    }
    
    updateCurrentPhase(stats) {
        const phaseEl = document.getElementById('current-phase');
        
        let statusClass = 'pending';
        if (stats.current_phase_status === 'completed') {
            statusClass = 'completed';
        } else if (stats.current_phase_status === 'in_progress') {
            statusClass = 'in-progress';
        }
        
        phaseEl.innerHTML = `
            <div class="phase-info ${statusClass}">
                <div class="phase-name">${stats.current_phase_name || stats.current_phase}</div>
                <div class="phase-status">${this.getPhaseStatusText(stats.current_phase_status)}</div>
                <div class="phase-tasks">
                    <span>任务: ${stats.completed_tasks}/${stats.total_tasks}</span>
                    <span>完成率: ${stats.completion_rate}%</span>
                </div>
                ${stats.tdd_enabled ? '<div class="tdd-badge"><i class="fas fa-check-circle"></i> TDD启用</div>' : ''}
            </div>
        `;
    }
    
    getPhaseStatusText(status) {
        const statusMap = {
            'pending': '🕐 等待开始',
            'in_progress': '🚧 进行中',
            'completed': '✅ 已完成',
            'blocked': '⛔ 受阻'
        };
        return statusMap[status] || status;
    }
    
    renderKanban(kanbanData) {
        const columnsEl = document.getElementById('kanban-columns');
        const loadingEl = document.getElementById('kanban-loading');
        
        // 清空现有内容
        columnsEl.innerHTML = '';
        
        // 渲染四象限列（仅渲染5个已知列，防御未知列名）
        const knownColumns = ['request', 'design', 'develop', 'audit', 'done'];
        for (const [statusKey, columnData] of Object.entries(kanbanData.columns)) {
            if (!knownColumns.includes(statusKey)) continue;
            const columnEl = this.createKanbanColumn(statusKey, columnData);
            columnsEl.appendChild(columnEl);
        }
        
        // 显示列并隐藏加载状态
        columnsEl.style.display = 'grid';
        loadingEl.style.display = 'none';
    }
    
    createKanbanColumn(statusKey, columnData) {
        const columnEl = document.createElement('div');
        columnEl.className = `kanban-column ${statusKey.replace('_', '-')}`;
        
        // 列标题
        const headerEl = document.createElement('div');
        headerEl.className = 'column-header';
        headerEl.innerHTML = `
            <div class="column-title">${columnData.title}</div>
            <div class="task-count">${columnData.tasks.length}</div>
        `;
        
        columnEl.appendChild(headerEl);
        
        // Request column gets inline add form
        if (statusKey === 'request') {
            const formEl = document.createElement('div');
            formEl.className = 'request-add-form';
            formEl.innerHTML = `
                <input type="text" id="request-title-input" placeholder="新需求标题..." />
                <div class="add-row">
                    <select id="request-assignee-select">
                        <option value="">指派给...</option>
                        <option value="alpha">🐢 阿尔法</option>
                        <option value="duci">🦂 毒刺</option>
                        <option value="panda">🐼 达达</option>
                    </select>
                    <button onclick="submitRequestRequirement()">添加</button>
                </div>
            `;
            columnEl.appendChild(formEl);
            
            // Enter key in title input
            const titleInput = document.getElementById('request-title-input');
            if (titleInput) {
                titleInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        submitRequestRequirement();
                    }
                });
            }
        }
        
        // 任务列表
        const tasksListEl = document.createElement('div');
        tasksListEl.className = 'tasks-list';
        
        if (columnData.tasks.length === 0) {
            tasksListEl.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>暂无任务</p>
                </div>
            `;
        } else {
            columnData.tasks.forEach(task => {
                const taskCard = this.createTaskCard(task);
                tasksListEl.appendChild(taskCard);
            });
        }
        
        columnEl.appendChild(tasksListEl);
        
        return columnEl;
    }
    
    createTaskCard(task) {
        const taskCard = document.createElement('div');
        taskCard.className = `task-card severity-${task.severity?.toLowerCase() || 'p3'}`;
        taskCard.dataset.taskId = task.id;
        
        // 检测异常状态（cancelled/timed_out/escalated）
        const isException = task.pipeline_status_raw && ['cancelled', 'timed_out', 'escalated'].includes(task.pipeline_status_raw);
        if (isException) {
            taskCard.classList.add('task-exception');
        }
        
        // 获取成员 Emoji — 优先使用 current_executor（当前阶段执行人）
        const executor = task.current_executor || task.assignee || '';
        const assigneeEmoji = this.memberEmojiMap[executor] || '👤';
        const avatarSrc = executor ? `/static/avatars/${executor}.png` : '';
        
        // 阶段状态中文映射
        const STATUS_CN = {
            'request': '需求池', 'validate': '验证中',
            'design': '设计中', 'ui_design': 'UI设计中',
            'review': '审核中',
            'develop_wt': '测试编写中', 'review_test': '测试审核中',
            'develop_code': '开发中', 'develop': '开发中',
            'test': '测试中',
            'audit': '审计中', 'final_check': '终审中',
            'deliver': '交付中', 'done': '已完成',
            'cancelled': '已取消', 'timed_out': '超时', 'escalated': '升级处理',
        };
        const statusCN = STATUS_CN[task.pipeline_status] || task.pipeline_status || '';
        // 阶段状态 HTML（中文显示，异常状态加红色类）
        let phaseHtml = '';
        if (task.pipeline_status) {
            const phaseClass = isException ? 'task-phase task-phase-exception' : 'task-phase';
            phaseHtml = `<div class="${phaseClass}" title="${task.phase_name}">${statusCN}</div>`;
        } else if (task.phase_name) {
            phaseHtml = `<div class="task-phase">${task.phase_name}</div>`;
        }
        
        taskCard.innerHTML = `
            <div class="task-header">
                <div class="task-id">${task.pipeline_id || task.id || ''}</div>
                <div class="task-severity">${task.severity}</div>
            </div>
            <div class="task-title">${this.escapeHtml(task.name)}</div>
            <div class="task-meta">
                <div class="task-assignee">
                    ${avatarSrc ? `<img src="${avatarSrc}" class="assignee-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ''}
                    <div class="assignee-avatar" style="${avatarSrc ? 'display:none;' : ''}">${assigneeEmoji}</div>
                    <span>${this.memberEmojiMap[executor] ? this.memberEmojiMap[executor] + ' ' : ''}${executor || '未分配'}</span>
                </div>
                ${phaseHtml}
            </div>
        `;
        
        // 点击查看任务详情
        taskCard.addEventListener('click', () => {
            this.showTaskDetail(task);
        });
        
        return taskCard;
    }
    
    renderGitTimeline(timelineData) {
        const listEl = document.getElementById('timeline-list');
        const loadingEl = document.getElementById('timeline-loading');
        
        // 清空现有内容
        listEl.innerHTML = '';
        
        if (!timelineData.commits || timelineData.commits.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-code-branch"></i>
                    <p>暂无提交记录</p>
                </div>
            `;
        } else {
            timelineData.commits.forEach(commit => {
                const timelineItem = this.createTimelineItem(commit);
                listEl.appendChild(timelineItem);
            });
        }
        
        // 显示时间线并隐藏加载状态
        listEl.style.display = 'block';
        loadingEl.style.display = 'none';
    }
    
    createTimelineItem(commit) {
        const itemEl = document.createElement('div');
        itemEl.className = 'timeline-item';
        
        // 格式化日期
        const commitDate = new Date(commit.date);
        const formattedDate = commitDate.toLocaleDateString('zh-CN', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        itemEl.innerHTML = `
            <div class="timeline-header-row">
                <div class="timeline-emoji">${commit.emoji || '📝'}</div>
                <div class="timeline-hash">${commit.hash}</div>
            </div>
            <div class="timeline-message">${this.escapeHtml(commit.message)}</div>
            <div class="timeline-meta">
                <span class="timeline-author">${commit.author_name}</span>
                <span class="timeline-date">${formattedDate}</span>
            </div>
        `;
        
        return itemEl;
    }
    
    renderGitStats(statsData) {
        const statsEl = document.getElementById('git-stats');
        
        if (!statsData || !statsData.members) {
            statsEl.innerHTML = '<div class="error">Git统计加载失败</div>';
            return;
        }
        
        let html = '<div class="git-members-stats">';
        
        // 按提交数量排序
        const members = Object.entries(statsData.members)
            .filter(([id, data]) => data.count > 0)
            .sort((a, b) => b[1].count - a[1].count);
        
        members.forEach(([id, data]) => {
            html += `
                <div class="git-member-stat">
                    <div class="git-member-header">
                        <span class="git-member-emoji">${data.emoji}</span>
                        <span class="git-member-name">${data.name}</span>
                    </div>
                    <div class="git-member-count">${data.count} 次提交</div>
                </div>
            `;
        });
        
        html += '</div>';
        statsEl.innerHTML = html;
    }
    
    showTaskDetail(task) {
        const modal = document.getElementById('task-modal');
        const titleEl = document.getElementById('modal-title');
        const bodyEl = document.getElementById('modal-body');
        
        // 获取成员 Emoji
        const assigneeEmoji = this.memberEmojiMap[task.assignee] || '👤';
        
        // 构建详情内容
        let detailsHtml = `
            <div class="task-detail">
                <div class="detail-section">
                    <h4><i class="fas fa-info-circle"></i> 基本信息</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">任务ID:</span>
                            <span class="detail-value">${task.id}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">严重程度:</span>
                            <span class="detail-value severity-${task.severity?.toLowerCase() || 'p3'}">${task.severity}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">分配成员:</span>
                            <span class="detail-value">${assigneeEmoji} ${task.assignee || '未分配'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">所属阶段:</span>
                            <span class="detail-value">${task.phase_name || task.phase}</span>
                        </div>
                    </div>
                </div>
        `;
        
        if (task.description) {
            detailsHtml += `
                <div class="detail-section">
                    <h4><i class="fas fa-align-left"></i> 任务描述</h4>
                    <p>${this.escapeHtml(task.description)}</p>
                </div>
            `;
        }
        
        if (task.notes) {
            detailsHtml += `
                <div class="detail-section">
                    <h4><i class="fas fa-sticky-note"></i> 备注</h4>
                    <p>${this.escapeHtml(task.notes)}</p>
                </div>
            `;
        }
        
        if (task.verification && task.verification.length > 0) {
            detailsHtml += `
                <div class="detail-section">
                    <h4><i class="fas fa-check-double"></i> 验证项</h4>
                    <ul class="verification-list">
                        ${task.verification.map(item => `<li>${this.escapeHtml(item)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        if (task.completed_at) {
            detailsHtml += `
                <div class="detail-section">
                    <h4><i class="fas fa-calendar-check"></i> 完成时间</h4>
                    <p>${new Date(task.completed_at).toLocaleString('zh-CN')}</p>
                </div>
            `;
        }
        
        detailsHtml += '</div>';
        
        // 更新模态框内容
        titleEl.textContent = task.name;
        bodyEl.innerHTML = detailsHtml;
        
        // 显示模态框
        modal.style.display = 'flex';
    }
    
    closeTaskModal() {
        document.getElementById('task-modal').style.display = 'none';
    }
    
    connectSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        this.eventSource = new EventSource('/events');
        
        this.eventSource.addEventListener('connected', (event) => {
            this.updateSSEStatus(true);
            console.log('SSE连接已建立');
        });
        
        this.eventSource.addEventListener('git_timeline', (event) => {
            this.eventCount++;
            this.updateEventCount();
            
            const data = JSON.parse(event.data);
            if (data.type === 'timeline_update') {
                // 更新Git时间线
                this.renderGitTimeline({ commits: data.data });
            }
        });
        
        this.eventSource.addEventListener('member_status', (event) => {
            this.eventCount++;
            this.updateEventCount();
            
            const data = JSON.parse(event.data);
            if (data.type === 'status_update') {
                this.renderMemberStatus(data.data);
            }
        });
        
        this.eventSource.addEventListener('pipeline_status', (event) => {
            this.eventCount++;
            this.updateEventCount();
            
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'pipeline_update') {
                    // Refresh kanban to show updated pipeline state
                    this.loadKanbanData();
                    console.log('Pipeline状态已更新:', data.data);
                }
            } catch (e) {
                console.error('pipeline_status解析错误:', e);
            }
        });
        
        this.eventSource.addEventListener('heartbeat', (event) => {
            this.eventCount++;
            this.updateEventCount();
            this.updateLastUpdated();
        });
        
        this.eventSource.addEventListener('error', (event) => {
            console.error('SSE连接错误:', event);
            this.updateSSEStatus(false);
            
            // 尝试重新连接
            setTimeout(() => {
                if (this.eventSource.readyState === EventSource.CLOSED) {
                    this.connectSSE();
                }
            }, 5000);
        });
    }
    
    updateSSEStatus(connected) {
        const statusEl = document.getElementById('sse-status');
        const connectionEl = document.getElementById('connection-status');
        
        if (connected) {
            statusEl.className = 'sse-status connected';
            statusEl.innerHTML = '<i class="fas fa-bolt"></i> 实时连接已建立';
            connectionEl.textContent = '🟢 已连接';
        } else {
            statusEl.className = 'sse-status disconnected';
            statusEl.innerHTML = '<i class="fas fa-unlink"></i> 连接断开';
            connectionEl.textContent = '🔴 连接断开';
        }
    }
    
    updateEventCount() {
        document.getElementById('event-count').textContent = `事件: ${this.eventCount}`;
    }
    
    updateLastUpdated() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        document.querySelector('#last-updated span').textContent = `最后更新: ${timeStr}`;
    }
    
    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        
        this.autoRefreshInterval = setInterval(() => {
            if (this.autoRefresh) {
                this.loadTaskStats();
                this.loadGitStats();
                this.loadMemberStatus();
                
                // 每5分钟全量刷新一次看板
                const now = new Date();
                if (!this.lastKanbanUpdate || (now - this.lastKanbanUpdate) > 5 * 60 * 1000) {
                    this.loadKanbanData();
                }
                
                // 每3分钟刷新一次时间线
                if (!this.lastTimelineUpdate || (now - this.lastTimelineUpdate) > 3 * 60 * 1000) {
                    this.loadGitTimeline();
                }
            }
        }, 30000); // 每30秒检查一次
    }
    
    showError(message) {
        // 简单的错误提示
        const errorEl = document.createElement('div');
        errorEl.className = 'error-toast';
        errorEl.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(errorEl);
        
        setTimeout(() => {
            errorEl.remove();
        }, 5000);
    }
    
    // ===== 成员管理 Tab 方法 =====
    
    async loadMembers() {
        const loadingEl = document.getElementById('members-tab-loading');
        const gridEl = document.getElementById('members-card-grid');
        
        if (!loadingEl || !gridEl) return;
        
        loadingEl.style.display = 'flex';
        gridEl.style.display = 'none';
        
        try {
            const response = await fetch('/api/members');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const members = await response.json();
            this.renderMembersTab(members);
        } catch (error) {
            console.error('加载成员数据失败:', error);
            loadingEl.innerHTML = `
                <div style="text-align: center; color: #f38ba8;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 10px;"></i>
                    <p>加载成员数据失败</p>
                </div>
            `;
        }
        
        // 设置每小时自动刷新
        if (this._membersRefreshInterval) {
            clearInterval(this._membersRefreshInterval);
        }
        this._membersRefreshInterval = setInterval(() => {
            this.loadMembers();
        }, 3600000); // 1小时
    }
    
    renderMembersTab(members) {
        const loadingEl = document.getElementById('members-tab-loading');
        const gridEl = document.getElementById('members-card-grid');
        
        if (!gridEl || !loadingEl) return;
        
        gridEl.innerHTML = '';
        
        if (!members || members.length === 0) {
            gridEl.innerHTML = '<div class="empty-state" style="padding:40px;text-align:center;"><i class="fas fa-users" style="font-size:3rem;color:#585b70;margin-bottom:12px;"></i><p style="color:#6c7086;">暂无成员数据</p></div>';
            gridEl.style.display = 'block';
            loadingEl.style.display = 'none';
            return;
        }
        
        members.forEach(m => {
            const card = document.createElement('div');
            card.className = 'member-tab-card';
            
            const status = m.status || 'unknown';
            const statusClass = (status === 'executing' || status === 'online') ? 'online' :
                               (status === 'idle' || status === 'sleeping') ? 'idle' : 'offline';
            const statusText = this.memberTabStatusText(status);
            const emoji = m.avatar_emoji || this.memberEmojiMap[m.id] || '🐾';
            const displayName = this.memberNameMap[m.id] || m.name || m.id;
            
            card.innerHTML = `
                <div class="member-tab-card-header">
                    <div class="member-tab-avatar">
                        <img src="/static/avatars/${m.id}.png" alt="${this.escapeHtml(displayName)}"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="member-tab-avatar-fallback">${emoji}</div>
                    </div>
                    <div class="member-tab-status-indicator ${statusClass}"
                         title="${statusText}"></div>
                </div>
                <div class="member-tab-card-body">
                    <h3 class="member-tab-name">${this.escapeHtml(displayName)}</h3>
                    <div class="member-tab-totem">${emoji}</div>
                    <div class="member-tab-role-badge">${this.escapeHtml(m.role_display || '未知')}</div>
                    <div class="member-tab-model">🧠 ${this.escapeHtml(m.model || '未知')}</div>
                    <div class="member-tab-status-text ${statusClass}">${statusText}</div>
                </div>
            `;
            gridEl.appendChild(card);
        });
        
        gridEl.style.display = 'grid';
        loadingEl.style.display = 'none';
        
        // 更新最后更新时间
        const updateEl = document.getElementById('members-last-update');
        if (updateEl) {
            const now = new Date();
            updateEl.textContent = `最后更新: ${now.toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'})}`;
        }
    }
    
    memberTabStatusText(status) {
        const map = {
            'online': '🟢 在线',
            'executing': '🟢 在线',
            'idle': '🟢 空闲',
            'sleeping': '💤 休眠',
            'dead': '🔴 离线',
            'terminated': '🔴 离线',
            'unknown': '⚫ 离线'
        };
        return map[status] || '⚫ 离线';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ===== Global Chat Functions =====
function loadChat() {
    if (!window.zooDevCenter) return;
    const div = document.getElementById('chat-messages');
    if (!div) return;
    
    fetch('/api/chat')
        .then(r => r.json())
        .then(msgs => {
            div.innerHTML = msgs.map(m => {
                const hasMention = m.mentioned ? '<span class="mention-badge">📨 已转发</span>' : '';
                return `<div class="chat-message-item">
                    <strong class="msg-from">${escapeHtml(m.from)}</strong>:
                    ${escapeHtml(m.content)}
                    <span class="msg-time">${m.timestamp || ''}</span>
                    ${hasMention}
                </div>`;
            }).join('');
            div.scrollTop = div.scrollHeight;
        })
        .catch(e => console.error('loadChat error:', e));
}

function sendChat() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const content = input.value.trim();
    if (!content) return;
    input.value = '';
    
    fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content})
    })
    .then(r => r.json())
    .then(() => {
        loadChat();
        // Also refresh kanban to show new backlog items
        if (window.zooDevCenter) {
            window.zooDevCenter.loadKanbanData();
        }
    })
    .catch(e => console.error('sendChat error:', e));
}

function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ===== Issue Functions =====
function loadIssues() {
    const list = document.getElementById('issues-list');
    if (!list) return;
    
    list.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';
    
    const statusFilter = document.getElementById('issue-status-filter')?.value || 'all';
    const priorityFilter = document.getElementById('issue-priority-filter')?.value || 'all';
    const searchQuery = document.getElementById('issue-search')?.value || '';
    
    let url = '/api/issues';
    const params = [];
    if (statusFilter !== 'all') params.push('status=' + encodeURIComponent(statusFilter));
    if (priorityFilter !== 'all') params.push('priority=' + encodeURIComponent(priorityFilter));
    if (searchQuery.trim()) params.push('search=' + encodeURIComponent(searchQuery.trim()));
    if (params.length) url += '?' + params.join('&');
    
    fetch(url)
        .then(r => r.json())
        .then(issues => {
            if (!issues || issues.length === 0) {
                list.innerHTML = '<div class="empty-state" style="padding:40px;text-align:center;color:#6c7086;"><i class="fas fa-inbox" style="font-size:3rem;margin-bottom:12px;color:#585b70;"></i><p style="font-size:1rem;">暂无问题</p><p style="font-size:0.85rem;margin-top:6px;">点击上方"新建问题"按钮创建</p></div>';
                return;
            }
            
            const priorityLabels = { 'P0': 'P0 紧急', 'P1': 'P1 高', 'P2': 'P2 中', 'P3': 'P3 低' };
            const priorityClasses = { 'P0': 'p0', 'P1': 'p1', 'P2': 'p2', 'P3': 'p3' };
            const statusLabels = { 'open': '待处理', 'in_progress': '处理中', 'resolved': '已解决', 'closed': '已关闭' };
            const statusClasses = { 'open': 'open', 'in_progress': 'in-progress', 'resolved': 'resolved', 'closed': 'closed' };
            const agentNames = {
                'alpha': '🐢 阿尔法', 'duci': '🦂 毒刺',
                'panda': '🐼 达达'
            };
            
            // Build next-status options for quick actions
            const nextStatusMap = {
                'open': 'in_progress',
                'in_progress': 'resolved',
                'resolved': 'closed',
                'closed': 'open'
            };
            const nextActionLabels = {
                'open': '开始处理',
                'in_progress': '标记解决',
                'resolved': '关闭问题',
                'closed': '重新打开'
            };
            
            var sortedIssues = sortIssuesForDisplay(issues);
            list.innerHTML = sortedIssues.map(issue => {
                const nextStatus = nextStatusMap[issue.status] || 'open';
                const nextLabel = nextActionLabels[issue.status] || '操作';
                const isClosed = CLOSED_ISSUE_STATUSES.indexOf(String(issue.status || '').trim()) !== -1;
                const displayTime = isClosed
                    ? (issue.resolved_at ? new Date(issue.resolved_at).toLocaleString('zh-CN') : '')
                    : (issue.created_at ? new Date(issue.created_at).toLocaleString('zh-CN') : '');
                
                return `
                    <div class="issue-card priority-${priorityClasses[issue.priority] || 'p3'}">
                        <div class="issue-card-left">
                            <div class="issue-priority-badge priority-${priorityClasses[issue.priority] || 'p3'}">${priorityLabels[issue.priority] || 'P3 低'}</div>
                        </div>
                        <div class="issue-card-body">
                            <div class="issue-title-row">
                                <span class="issue-title">${escapeHtml(issue.title)}</span>
                                <span class="issue-status-badge status-${statusClasses[issue.status] || 'open'}">${statusLabels[issue.status] || issue.status}</span>
                            </div>
                            ${issue.description ? `<div class="issue-desc">${escapeHtml(issue.description)}</div>` : ''}
                            <div class="issue-meta">
                                <span class="issue-assignee"><i class="fas fa-user"></i> ${agentNames[issue.assignee] || escapeHtml(issue.assignee) || '未指派'}</span>
                                <span class="issue-time"><i class="fas fa-clock"></i> ${isClosed ? '已解决: ' : ''}${displayTime}</span>
                            </div>
                        </div>
                        <div class="issue-card-actions">
                            <button class="issue-btn-action" onclick="updateIssueStatus('${issue.id}', '${nextStatus}')" title="${nextLabel}">
                                <i class="fas fa-arrow-right"></i>
                            </button>
                            <button class="issue-btn-delete" onclick="deleteIssue('${issue.id}')" title="删除问题">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        })
        .catch(e => {
            console.error('loadIssues error:', e);
            list.innerHTML = '<div style="padding:40px;text-align:center;color:#e74c3c;"><i class="fas fa-exclamation-triangle" style="font-size:2rem;margin-bottom:10px;"></i><p>加载失败</p></div>';
        });
}

function showCreateIssueForm() {
    const modal = document.getElementById('issue-modal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('issue-title').value = '';
        document.getElementById('issue-desc').value = '';
        document.getElementById('issue-priority').value = 'P3';
        document.getElementById('issue-assignee').value = '';
        document.getElementById('issue-title').focus();
    }
}

function closeIssueModal() {
    document.getElementById('issue-modal').style.display = 'none';
}

function submitIssue() {
    const title = document.getElementById('issue-title');
    const desc = document.getElementById('issue-desc');
    const priority = document.getElementById('issue-priority');
    const assignee = document.getElementById('issue-assignee');
    
    if (!title || !title.value.trim()) {
        title.focus();
        title.style.borderColor = '#e74c3c';
        setTimeout(() => { title.style.borderColor = ''; }, 2000);
        return;
    }
    
    fetch('/api/issues', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: title.value.trim(),
            description: desc ? desc.value.trim() : '',
            priority: priority ? priority.value : 'P3',
            assignee: assignee ? assignee.value : ''
        })
    })
    .then(r => r.json())
    .then(() => {
        closeIssueModal();
        loadIssues();
        const toast = document.createElement('div');
        toast.className = 'success-toast';
        toast.innerHTML = '<i class="fas fa-check-circle"></i> 问题已创建';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    })
    .catch(e => {
        console.error('submitIssue error:', e);
        alert('创建失败: ' + e.message);
    });
}

function updateIssueStatus(id, newStatus) {
    fetch('/api/issues/' + id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ status: newStatus })
    })
    .then(r => r.json())
    .then(() => {
        loadIssues();
    })
    .catch(e => {
        console.error('updateIssueStatus error:', e);
        alert('更新状态失败: ' + e.message);
    });
}

function deleteIssue(id) {
    if (!confirm('确定要删除这个问题吗？')) return;
    
    fetch('/api/issues/' + id, {
        method: 'DELETE'
    })
    .then(r => r.json())
    .then(() => {
        loadIssues();
        const toast = document.createElement('div');
        toast.className = 'success-toast';
        toast.innerHTML = '<i class="fas fa-check-circle"></i> 问题已删除';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    })
    .catch(e => {
        console.error('deleteIssue error:', e);
        alert('删除失败: ' + e.message);
    });
}

// Close issue modal when clicking outside
if (document) {
    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'issue-modal') {
            closeIssueModal();
        }
    });
}

// Keyboard shortcut: Escape closes issue modal
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('issue-modal');
        if (modal && modal.style.display === 'flex') {
            closeIssueModal();
        }
    }
});

// ===== Requirement Functions =====
// ===== 分组排序函数 =====

// 需求终端状态（已解决/已关闭）
var TERMINAL_REQ_STATUSES = ['done', 'cancelled', 'timed_out', 'escalated'];

// 问题终端状态（已解决/已关闭）
var CLOSED_ISSUE_STATUSES = ['resolved', 'closed', 'cancelled'];

// 优先级排序权重
var PRIORITY_ORDER = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3 };

// 优先级显示名和 CSS 类
var PRIORITY_LABELS = { 'P0': 'P0 紧急', 'P1': 'P1 高', 'P2': 'P2 中', 'P3': 'P3 低' };
var PRIORITY_CLASSES = { 'P0': 'p0', 'P1': 'p1', 'P2': 'p2', 'P3': 'p3' };

function sortRequirementsForDisplay(reqs) {
    var openReqs = reqs.filter(function(r) {
        return TERMINAL_REQ_STATUSES.indexOf(r.status) === -1;
    });
    var closedReqs = reqs.filter(function(r) {
        return TERMINAL_REQ_STATUSES.indexOf(r.status) !== -1;
    });

    openReqs.sort(function(a, b) {
        return (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
    });
    closedReqs.sort(function(a, b) {
        var ta = b.completed_at || b.updated_at || b.created_at || '';
        var tb = a.completed_at || a.updated_at || a.created_at || '';
        return ta.localeCompare(tb); // 新→旧
    });

    return openReqs.concat(closedReqs);
}

function sortIssuesForDisplay(issues) {
    var openIssues = issues.filter(function(i) {
        return CLOSED_ISSUE_STATUSES.indexOf(String(i.status || '').trim()) === -1;
    });
    var closedIssues = issues.filter(function(i) {
        return CLOSED_ISSUE_STATUSES.indexOf(String(i.status || '').trim()) !== -1;
    });
    console.log('sortIssuesForDisplay: total=' + issues.length + ' open=' + openIssues.length + ' closed=' + closedIssues.length);

    openIssues.sort(function(a, b) {
        return (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
    });
    closedIssues.sort(function(a, b) {
        var ta = b.resolved_at || b.updated_at || b.created_at || '';
        var tb = a.resolved_at || a.updated_at || a.created_at || '';
        return ta.localeCompare(tb); // 新→旧
    });

    return openIssues.concat(closedIssues);
}

function submitRequirement() {
    const title = document.getElementById('req-title');
    const desc = document.getElementById('req-desc');
    const assignee = document.getElementById('req-assignee');
    const priority = document.getElementById('req-priority');
    const btn = document.getElementById('req-submit-btn');
    
    if (!title || !title.value.trim()) {
        title.focus();
        title.style.borderColor = '#e74c3c';
        setTimeout(() => { title.style.borderColor = ''; }, 2000);
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';
    
    fetch('/api/requirements', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: title.value.trim(),
            description: desc ? desc.value.trim() : '',
            assignee: assignee ? assignee.value : '',
            priority: priority ? priority.value : 'P3'
        })
    })
    .then(r => r.json())
    .then(req => {
        title.value = '';
        if (desc) desc.value = '';
        if (assignee) assignee.value = '';
        
        // Show success toast
        const toast = document.createElement('div');
        toast.className = 'success-toast';
        toast.innerHTML = '<i class="fas fa-check-circle"></i> 需求已提交';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
        
        // Refresh lists
        loadRequirementsList();
        if (window.zooDevCenter) {
            window.zooDevCenter.loadKanbanData();
        }
    })
    .catch(e => {
        console.error('submitRequirement error:', e);
        alert('提交失败: ' + e.message);
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane"></i> 提交需求';
    });
}

function submitRequestRequirement() {
    const titleInput = document.getElementById('request-title-input');
    const assigneeSelect = document.getElementById('request-assignee-select');
    
    if (!titleInput || !titleInput.value.trim()) {
        if (titleInput) { titleInput.focus(); titleInput.style.borderColor = '#e74c3c'; setTimeout(() => { titleInput.style.borderColor = ''; }, 2000); }
        return;
    }
    
    fetch('/api/requirements', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: titleInput.value.trim(),
            description: '',
            assignee: assigneeSelect ? assigneeSelect.value : ''
        })
    })
    .then(r => r.json())
    .then(() => {
        titleInput.value = '';
        if (assigneeSelect) assigneeSelect.value = '';
        if (window.zooDevCenter) {
            window.zooDevCenter.loadKanbanData();
        }
    })
    .catch(e => console.error('submitRequestRequirement error:', e));
}

function loadRequirementsList() {
    const list = document.getElementById('req-list');
    if (!list) return;
    
    fetch('/api/requirements')
        .then(r => r.json())
        .then(reqs => {
            if (!reqs || reqs.length === 0) {
                list.innerHTML = '<div class="empty-state" style="padding:30px;text-align:center;color:#95a5a6;"><i class="fas fa-inbox" style="font-size:2rem;margin-bottom:10px;"></i><p>暂无需求</p></div>';
                return;
            }
            
            const statusLabels = {
                'request': '待处理',
                'validate': '验证中',
                'design': '设计中',
                'ui_design': 'UI设计中',
                'review': '审查中',
                'develop_wt': '开发中(WT)',
                'review_test': '测试审查',
                'develop_code': '编码中',
                'develop': '开发中',
                'test': '测试中',
                'audit': '验收中',
                'final_check': '终检中',
                'deliver': '交付中',
                'done': '已完成',
                'cancelled': '🚫 已取消',
                'timed_out': '⏰ 已超时',
                'escalated': '🚨 已升级'
            };
            
            const agentNames = {
                'alpha': '🐢 阿尔法',
                'duci': '🦂 毒刺',
                'panda': '🐼 达达'
            };
            
            var sortedReqs = sortRequirementsForDisplay(reqs);
            list.innerHTML = sortedReqs.map(function(r) { return `
                <div class="req-list-item">
                    <div class="req-title">${escapeHtml(r.title)}</div>
                    <div class="req-meta">
                        <span><i class="fas fa-flag"></i> <span class="req-priority-badge ${PRIORITY_CLASSES[r.priority] || 'p3'}">${PRIORITY_LABELS[r.priority] || 'P3低'}</span></span>
                        <span><i class="fas fa-tag"></i> <span class="req-status-badge ${r.status}">${statusLabels[r.status] || r.status}</span></span>
                        <span><i class="fas fa-user"></i> ${agentNames[r.assignee] || '未指派'}</span>
                        <span><i class="fas fa-clock"></i> ${r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : ''}</span>
                    </div>
                </div>
            `; }).join('');
        })
        .catch(e => {
            console.error('loadRequirementsList error:', e);
            list.innerHTML = '<div style="padding:20px;text-align:center;color:#e74c3c;">加载失败</div>';
        });
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.zooDevCenter = new ZooDevCenter();
    // Load requirements list if that tab is visible
    loadRequirementsList();
});

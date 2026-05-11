// Zoo Dev-Center JavaScript
// 实现四象限看板、Git时间线和实时更新的交互功能

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
        
        // 成员 Emoji 映射
        this.memberEmojiMap = {
            'alpha': '🐢',
            'weaver': '🐜',
            'stinger': '🦂',
            'duci': '🦂',
            'panda': '🐼',
            'aeterna': '📜',
            'gulu': '🟢'
        };
        
        // 成员名称统一映射（无论后端返回什么name，前端统一显示）
        this.memberNameMap = {
            'alpha': '阿尔法',
            'weaver': '织巢',
            'duci': '毒刺',
            'aeterna': '史官',
            'gulu': '咕噜',
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
        
        // 加载初始数据
        this.loadInitialData();
        
        // 建立 SSE 连接
        this.connectSSE();
        
        // 启动自动刷新
        this.startAutoRefresh();
    }
    
    bindEvents() {
        // 刷新看板按钮
        document.getElementById('refresh-kanban').addEventListener('click', () => {
            this.loadKanbanData();
        });
        
        // 刷新时间线按钮
        document.getElementById('refresh-timeline').addEventListener('click', () => {
            this.loadGitTimeline();
        });
        
        // 刷新成员按钮
        const refreshMembersBtn = document.getElementById('refresh-members');
        if (refreshMembersBtn) {
            refreshMembersBtn.addEventListener('click', () => {
                this.loadMemberCards();
            });
        }
        
        // 模态框关闭按钮
        document.getElementById('modal-close').addEventListener('click', () => {
            this.closeTaskModal();
        });
        
        // 点击模态框背景关闭
        document.getElementById('task-modal').addEventListener('click', (e) => {
            if (e.target.id === 'task-modal') {
                this.closeTaskModal();
            }
        });
        
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
            { id: 'alpha', name: '阿尔法', code_name: 'Alpha', role_display: '首席架构师 · 玄龟', model: 'DeepSeek V4 Flash', avatar_emoji: '🐢' },
            { id: 'weaver', name: '织巢', code_name: 'Weaver', role_display: '疯狂工程师 · 织巢蚁', model: 'MiniMax-M2.7', avatar_emoji: '🐜' },
            { id: 'duci', name: '毒刺', code_name: 'Duci', role_display: '代码审计师 · 毒刺蝎', model: 'GLM-5.1', avatar_emoji: '🦂' },
            { id: 'panda', name: '达达', code_name: 'Panda', role_display: '调度者 · 熊猫', model: 'MiniMax-M2.7', avatar_emoji: '🐼' },
            { id: 'aeterna', name: '史官', code_name: 'Aeterna', role_display: '永恒史官 · 磐石', model: 'MiniMax-M2.7', avatar_emoji: '🪨' },
            { id: 'gulu', name: '咕噜', code_name: 'Gulu', role_display: '画师/UI设计师 · 咕噜', model: 'MiniMax-M2.7', avatar_emoji: '🟢' }
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
                '阿尔法': 'alpha', '织巢': 'weaver', '毒刺': 'duci', 
                '达达': 'panda', '史官': 'aeterna', '史官 (Aeterna)': 'aeterna', '咕噜': 'gulu'
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
        
        // 渲染四象限列
        for (const [statusKey, columnData] of Object.entries(kanbanData.columns)) {
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
        
        columnEl.appendChild(headerEl);
        columnEl.appendChild(tasksListEl);
        
        return columnEl;
    }
    
    createTaskCard(task) {
        const taskCard = document.createElement('div');
        taskCard.className = `task-card severity-${task.severity?.toLowerCase() || 'p3'}`;
        taskCard.dataset.taskId = task.id;
        
        // 获取成员 Emoji
        const assigneeEmoji = this.memberEmojiMap[task.assignee] || '👤';
        const avatarSrc = task.assignee ? `/static/avatars/${task.assignee === 'stinger' ? 'stinger' : task.assignee}.png` : '';
        
        taskCard.innerHTML = `
            <div class="task-header">
                <div class="task-id">${task.id}</div>
                <div class="task-severity">${task.severity}</div>
            </div>
            <div class="task-title">${this.escapeHtml(task.name)}</div>
            <div class="task-meta">
                <div class="task-assignee">
                    ${avatarSrc ? `<img src="${avatarSrc}" class="assignee-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ''}
                    <div class="assignee-avatar" style="${avatarSrc ? 'display:none;' : ''}">${assigneeEmoji}</div>
                    <span>${task.assignee || '未分配'}</span>
                </div>
                ${task.phase_name ? `<div class="task-phase">${task.phase_name}</div>` : ''}
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
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.zooDevCenter = new ZooDevCenter();
});
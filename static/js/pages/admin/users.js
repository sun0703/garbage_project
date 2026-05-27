import { escapeHtml } from '../../utils/escape.js';

export class AdminUsers {
    container = null;
    _api = null;
    _page = 1;
    _search = '';
    _role = '';
    _totalPages = 1;
    _boundHandlers = {};

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadUsers();
    }

    _render() {
        this.container.innerHTML = `
            <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin-bottom:20px">
                \u{1F465} 用户管理
            </h2>

            <div class="admin-search-bar">
                <input type="text" class="admin-input" id="adminUserSearch"
                       placeholder="搜索用户名或昵称..." style="max-width:280px">
                <select class="admin-select" id="adminUserRoleFilter">
                    <option value="">全部角色</option>
                    <option value="admin">管理员</option>
                    <option value="user">普通用户</option>
                </select>
                <button class="admin-btn admin-btn-primary" id="adminUserSearchBtn">搜索</button>
            </div>

            <div class="admin-card" style="padding:0;overflow:hidden">
                <div class="admin-table-wrap">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>昵称</th>
                                <th>用户名</th>
                                <th>积分</th>
                                <th>打卡</th>
                                <th>角色</th>
                                <th>状态</th>
                                <th>注册时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="adminUserTableBody">
                            <tr><td colspan="8" class="admin-loading">\u23F3 加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="admin-pagination" id="adminUserPagination"></div>
        `;

        this._boundHandlers.searchClick = () => {
            this._search = document.getElementById('adminUserSearch').value.trim();
            this._role = document.getElementById('adminUserRoleFilter').value;
            this._page = 1;
            this._loadUsers();
        };
        document.getElementById('adminUserSearchBtn').addEventListener('click', this._boundHandlers.searchClick);

        this._boundHandlers.searchKeypress = (e) => {
            if (e.key === 'Enter') {
                this._search = e.target.value.trim();
                this._role = document.getElementById('adminUserRoleFilter').value;
                this._page = 1;
                this._loadUsers();
            }
        };
        document.getElementById('adminUserSearch').addEventListener('keypress', this._boundHandlers.searchKeypress);

        this._boundHandlers.tbodyClick = async (e) => {
            const btn = e.target.closest('[data-action="toggleStatus"]');
            if (!btn) return;
            const userId = btn.dataset.userId;
            const newStatus = btn.dataset.currentStatus === 'active' ? 'disabled' : 'active';
            btn.disabled = true;
            btn.textContent = '处理中...';
            try {
                await this._api.adminUpdateUserStatus(userId, newStatus);
                this._loadUsers();
            } catch (err) {
                console.error('[AdminUsers] 状态更新失败:', err);
                btn.disabled = false;
                btn.textContent = btn.dataset.currentStatus === 'active' ? '禁用' : '启用';
            }
        };
        document.getElementById('adminUserTableBody').addEventListener('click', this._boundHandlers.tbodyClick);

        this._boundHandlers.tbodyChange = async (e) => {
            const select = e.target.closest('[data-action="changeRole"]');
            if (!select) return;
            const userId = select.dataset.userId;
            const newRole = select.value;
            select.disabled = true;
            try {
                await this._api.adminUpdateUserRole(userId, newRole);
                this._loadUsers();
            } catch (err) {
                console.error('[AdminUsers] 角色更新失败:', err);
                this._loadUsers();
            }
        };
        document.getElementById('adminUserTableBody').addEventListener('change', this._boundHandlers.tbodyChange);

        this._boundHandlers.paginationClick = (e) => {
            const btn = e.target.closest('button:not([disabled])');
            if (!btn || !btn.dataset.page) return;
            this._page = parseInt(btn.dataset.page);
            this._loadUsers();
        };
        document.getElementById('adminUserPagination').addEventListener('click', this._boundHandlers.paginationClick);
    }

    async _loadUsers() {
        const tbody = document.getElementById('adminUserTableBody');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="8" class="admin-loading">\u23F3 加载中...</td></tr>';

        try {
            const data = await this._api.adminGetUsers(this._page, this._search, this._role);
            const users = data.users || data.data || [];
            const pagination = data.pagination || {};
            this._totalPages = pagination.total_pages || 1;

            if (users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="admin-empty">暂无用户数据</td></tr>';
            } else {
                tbody.innerHTML = users.map(u => this._renderUserRow(u)).join('');
            }

            this._renderPagination();
        } catch (err) {
            console.error('[AdminUsers] 加载用户失败:', err);
            tbody.innerHTML = '<tr><td colspan="8" class="admin-empty" style="color:#dc3545">加载失败，请重试</td></tr>';
        }
    }

    _renderUserRow(u) {
        const createdAt = u.created_at
            ? new Date(u.created_at * 1000).toLocaleDateString('zh-CN')
            : '—';

        const isAdmin = u.role === 'admin';
        const isActive = u.status !== 'disabled';

        const roleBadge = isAdmin ? 'admin-badge--admin' : 'admin-badge--user';
        const roleLabel = isAdmin ? '管理员' : '普通用户';
        const statusBadge = isActive ? 'admin-badge--active' : 'admin-badge--disabled';
        const statusLabel = isActive ? '正常' : '已禁用';

        return `
            <tr data-user-id="${u.id || u.user_id}">
                <td>${escapeHtml(u.nickname || '—')}</td>
                <td>${escapeHtml(u.username || '—')}</td>
                <td>${u.points ?? 0}</td>
                <td>${u.checkin_count ?? 0}</td>
                <td>
                    <span class="admin-badge ${roleBadge}">${roleLabel}</span>
                    <select class="admin-select admin-btn-xs" style="margin-left:6px;padding:2px 6px;font-size:11px"
                            data-action="changeRole" data-user-id="${u.id || u.user_id}">
                        <option value="user" ${!isAdmin ? 'selected' : ''}>普通用户</option>
                        <option value="admin" ${isAdmin ? 'selected' : ''}>管理员</option>
                    </select>
                </td>
                <td><span class="admin-badge ${statusBadge}">${statusLabel}</span></td>
                <td>${createdAt}</td>
                <td>
                    <button class="admin-btn admin-btn-sm ${isActive ? 'admin-btn-danger' : 'admin-btn-primary'}"
                            data-action="toggleStatus"
                            data-user-id="${u.id || u.user_id}"
                            data-current-status="${isActive ? 'active' : 'disabled'}">
                        ${isActive ? '禁用' : '启用'}
                    </button>
                </td>
            </tr>
        `;
    }

    _renderPagination() {
        const pagination = document.getElementById('adminUserPagination');
        if (!pagination || this._totalPages <= 1) {
            if (pagination) pagination.innerHTML = '';
            return;
        }

        let html = '';
        html += `<button ${this._page <= 1 ? 'disabled' : ''} data-page="${this._page - 1}">上一页</button>`;

        const start = Math.max(1, this._page - 3);
        const end = Math.min(this._totalPages, this._page + 3);

        for (let i = start; i <= end; i++) {
            html += `<button class="${i === this._page ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        html += `<button ${this._page >= this._totalPages ? 'disabled' : ''} data-page="${this._page + 1}">下一页</button>`;

        pagination.innerHTML = html;
    }

    destroy() {
        document.getElementById('adminUserSearchBtn')?.removeEventListener('click', this._boundHandlers.searchClick);
        document.getElementById('adminUserSearch')?.removeEventListener('keypress', this._boundHandlers.searchKeypress);
        document.getElementById('adminUserTableBody')?.removeEventListener('click', this._boundHandlers.tbodyClick);
        document.getElementById('adminUserTableBody')?.removeEventListener('change', this._boundHandlers.tbodyChange);
        document.getElementById('adminUserPagination')?.removeEventListener('click', this._boundHandlers.paginationClick);
        if (this.container) {
            this.container.innerHTML = '';
        }
        this._boundHandlers = {};
    }
}

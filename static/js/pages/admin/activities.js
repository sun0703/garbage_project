import { escapeHtml } from '../../utils/escape.js';
import { showToast, confirm } from '../../utils/ui.js';

export class AdminActivities {
    container = null;
    _api = null;
    _activitiesData = [];
    _boundHandlers = {};

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadActivities();
    }

    _render() {
        this.container.innerHTML = `
            <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin-bottom:20px">
                \u{1F389} 活动管理
            </h2>

            <div class="admin-card" style="padding:0;overflow:hidden">
                <div class="admin-table-wrap">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>活动标题</th>
                                <th>状态</th>
                                <th>开始时间</th>
                                <th>结束时间</th>
                                <th>报名人数</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="adminActivitiesTableBody">
                            <tr><td colspan="6" class="admin-loading">\u23F3 加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        this._boundHandlers.tbodyClick = async (e) => {
            const editBtn = e.target.closest('[data-action="editActivity"]');
            if (editBtn) {
                const idx = parseInt(editBtn.dataset.idx);
                this._showActivityEditModal(this._activitiesData[idx], idx);
                return;
            }

            const deleteBtn = e.target.closest('[data-action="deleteActivity"]');
            if (deleteBtn) {
                const idx = parseInt(deleteBtn.dataset.idx);
                const activity = this._activitiesData[idx];
                const confirmed = await confirm(`确定要删除活动「${activity.title || activity.name}」吗？此操作不可撤销。`);
                if (!confirmed) return;
                deleteBtn.disabled = true;
                deleteBtn.textContent = '删除中...';
                try {
                    await this._api.adminDeleteActivity(activity.id);
                    this._loadActivities();
                } catch (err) {
                    console.error('[AdminActivities] 删除失败:', err);
                    showToast('删除失败，请重试', 'error');
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '删除';
                }
            }
        };
        document.getElementById('adminActivitiesTableBody').addEventListener('click', this._boundHandlers.tbodyClick);
    }

    async _loadActivities() {
        const tbody = document.getElementById('adminActivitiesTableBody');
        if (!tbody) return;

        try {
            const data = await this._api.getActivities('', 1);
            this._activitiesData = data.activities || data.data || [];

            if (this._activitiesData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="admin-empty">暂无活动数据</td></tr>';
            } else {
                tbody.innerHTML = this._activitiesData.map((a, idx) => this._renderActivityRow(a, idx)).join('');
            }
        } catch (err) {
            console.error('[AdminActivities] 加载活动失败:', err);
            tbody.innerHTML = '<tr><td colspan="6" class="admin-empty" style="color:#dc3545">加载失败</td></tr>';
        }
    }

    _renderActivityRow(a, idx) {
        const isOpen = a.status === 'open' || a.status === 'active';
        const statusBadge = isOpen ? 'admin-badge--active' : 'admin-badge--disabled';
        const statusLabel = { open: '进行中', active: '进行中', closed: '已结束', upcoming: '即将开始' }[a.status] || a.status || '—';

        const startTime = a.start_time ? new Date(a.start_time * 1000).toLocaleDateString('zh-CN') : '—';
        const endTime = a.end_time ? new Date(a.end_time * 1000).toLocaleDateString('zh-CN') : '—';

        return `
            <tr>
                <td style="font-weight:500">${escapeHtml(a.title || a.name || '—')}</td>
                <td><span class="admin-badge ${statusBadge}">${statusLabel}</span></td>
                <td>${startTime}</td>
                <td>${endTime}</td>
                <td>${a.signup_count ?? a.participants ?? 0}</td>
                <td>
                    <button class="admin-btn admin-btn-sm admin-btn-secondary"
                            data-action="editActivity" data-idx="${idx}">编辑</button>
                    <button class="admin-btn admin-btn-sm admin-btn-danger"
                            data-action="deleteActivity" data-idx="${idx}">删除</button>
                </td>
            </tr>
        `;
    }

    _showActivityEditModal(activity, idx) {
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal" style="max-width:520px">
                <h3 class="admin-modal__title">编辑活动</h3>
                <div class="admin-form-group">
                    <label>活动标题</label>
                    <input class="admin-input" id="actEditTitle" value="${escapeHtml(activity.title || activity.name || '')}">
                </div>
                <div class="admin-form-group">
                    <label>状态</label>
                    <select class="admin-select" id="actEditStatus">
                        <option value="open" ${activity.status === 'open' || activity.status === 'active' ? 'selected' : ''}>进行中</option>
                        <option value="closed" ${activity.status === 'closed' ? 'selected' : ''}>已结束</option>
                        <option value="upcoming" ${activity.status === 'upcoming' ? 'selected' : ''}>即将开始</option>
                    </select>
                </div>
                <div class="admin-form-group">
                    <label>描述</label>
                    <textarea class="admin-textarea" id="actEditDesc">${escapeHtml(activity.description || '')}</textarea>
                </div>
                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="actEditCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="actEditSave">保存修改</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('actEditCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('actEditSave').addEventListener('click', async () => {
            const formData = {
                title: document.getElementById('actEditTitle').value.trim(),
                status: document.getElementById('actEditStatus').value,
                description: document.getElementById('actEditDesc').value.trim()
            };

            if (!formData.title) {
                showToast('活动标题不能为空', 'error');
                return;
            }

            const saveBtn = document.getElementById('actEditSave');
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';

            try {
                await this._api.adminUpdateActivity(activity.id, formData);
                closeModal();
                this._loadActivities();
            } catch (err) {
                console.error('[AdminActivities] 编辑活动失败:', err);
                showToast('保存失败，请重试', 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = '保存修改';
            }
        });
    }

    destroy() {
        document.getElementById('adminActivitiesTableBody')?.removeEventListener('click', this._boundHandlers.tbodyClick);
        if (this.container) {
            this.container.innerHTML = '';
        }
        this._boundHandlers = {};
        this._activitiesData = [];
    }
}

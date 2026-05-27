import { escapeHtml } from '../../utils/escape.js';
import { showToast } from '../../utils/ui.js';

export class AdminModels {
    container = null;
    _api = null;
    _boundHandlers = {};
    _activeModelId = null;

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadModels();
    }

    _render() {
        this.container.innerHTML = `
            <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin-bottom:20px">
                🤖 模型管理
            </h2>

            <div class="admin-tabs">
                <button class="admin-tab active" data-tab="models">模型列表</button>
                <button class="admin-tab" data-tab="badcases">Badcase收集</button>
            </div>

            <div id="adminModelsTabContent">
                <div id="adminModelsList">
                    <div class="admin-loading">⏳ 加载中...</div>
                </div>
            </div>
        `;

        this._boundHandlers.tabClick = (e) => {
            const tab = e.target.closest('.admin-tab');
            if (!tab) return;
            this.container.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const tabName = tab.dataset.tab;
            if (tabName === 'models') {
                this._loadModels();
            } else if (tabName === 'badcases') {
                this._loadBadcases();
            }
        };
        this.container.querySelector('.admin-tabs').addEventListener('click', this._boundHandlers.tabClick);
    }

    async _loadModels() {
        const content = document.getElementById('adminModelsList');
        if (!content) return;
        content.innerHTML = '<div class="admin-loading">⏳ 加载中...</div>';

        try {
            const data = await this._api.adminGetModels();
            const models = data.models || data.data || [];
            this._activeModelId = data.active_model_id || models.find(m => m.is_active || m.status === 'active')?.id;

            if (models.length === 0) {
                content.innerHTML = '<div class="admin-empty">暂无模型数据</div>';
                return;
            }

            content.innerHTML = `
                <div class="models-grid">
                    ${models.map((m, idx) => this._renderModelCard(m, idx)).join('')}
                </div>
            `;

            this._bindModelActions(models);
        } catch (err) {
            console.error('[AdminModels] 加载模型失败:', err);
            content.innerHTML = '<div class="admin-empty" style="color:#dc3545">加载失败，请检查后端服务</div>';
        }
    }

    _renderModelCard(m, idx) {
        const isActive = m.is_active || m.status === 'active' || m.id === this._activeModelId;
        const status = isActive ? 'active' : (m.status || 'inactive');
        const statusClass = status === 'active' ? 'admin-badge--active'
            : status === 'error' ? 'admin-badge--disabled'
            : 'admin-badge--user';

        const statusLabel = {
            active: '运行中', ready: '就绪', loading: '加载中',
            error: '故障', inactive: '未激活', unknown: '未知'
        }[status] || status;

        return `
            <div class="model-card ${isActive ? 'model-card--active' : ''}" data-model-id="${m.id || idx}">
                <div class="model-card__header">
                    <span class="model-card__name">${escapeHtml(m.name || `模型 #${idx + 1}`)}</span>
                    <span class="admin-badge ${statusClass}">${statusLabel}</span>
                </div>
                <div class="model-card__info">
                    ${this._infoRow('版本', m.version || '—')}
                    ${this._infoRow('类型', m.type || m.model_type || '—')}
                    ${this._infoRow('精度', m.accuracy ? `${(m.accuracy * 100).toFixed(1)}%` : '—')}
                    ${this._infoRow('大小', m.size || m.model_size || '—')}
                </div>
                ${m.description ? `<div class="model-card__desc">${escapeHtml(m.description)}</div>` : ''}
                <div class="model-card__actions">
                    ${!isActive ? `
                        <button class="admin-btn admin-btn-primary admin-btn-sm"
                                data-action="switchModel" data-model-id="${m.id || idx}">
                            切换使用
                        </button>
                    ` : '<span class="model-card__active-label">当前使用中</span>'}
                    <button class="admin-btn admin-btn-secondary admin-btn-sm"
                            data-action="viewBadcases" data-model-id="${m.id || idx}">
                        查看Badcase
                    </button>
                </div>
            </div>
        `;
    }

    _bindModelActions(models) {
        const content = document.getElementById('adminModelsList');
        if (!content) return;

        this._boundHandlers.contentClick = async (e) => {
            const switchBtn = e.target.closest('[data-action="switchModel"]');
            if (switchBtn) {
                const modelId = switchBtn.dataset.modelId;
                await this._switchModel(modelId);
                return;
            }

            const badcaseBtn = e.target.closest('[data-action="viewBadcases"]');
            if (badcaseBtn) {
                const modelId = badcaseBtn.dataset.modelId;
                this._showBadcaseModal(modelId);
                return;
            }
        };
        content.addEventListener('click', this._boundHandlers.contentClick);
    }

    async _switchModel(modelId) {
        try {
            showToast('正在切换模型...', 'info');
            await this._api.adminSwitchModel(modelId);
            showToast('模型切换成功', 'success');
            await this._loadModels();
        } catch (err) {
            console.error('[AdminModels] 切换模型失败:', err);
            showToast('切换失败，请重试', 'error');
        }
    }

    async _loadBadcases() {
        const content = document.getElementById('adminModelsTabContent');
        if (!content) return;
        content.innerHTML = '<div class="admin-loading">⏳ 加载中...</div>';

        try {
            const data = await this._api.adminGetBadcases();
            const badcases = data.badcases || data.data || [];

            if (badcases.length === 0) {
                content.innerHTML = '<div class="admin-empty">暂无Badcase记录</div>';
                return;
            }

            content.innerHTML = `
                <div class="admin-card" style="padding:0;overflow:hidden">
                    <div class="admin-table-wrap">
                        <table class="admin-table">
                            <thead>
                                <tr>
                                    <th>图片</th>
                                    <th>预测结果</th>
                                    <th>正确分类</th>
                                    <th>提交时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${badcases.map(bc => this._renderBadcaseRow(bc)).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            this._bindBadcaseActions();
        } catch (err) {
            console.error('[AdminModels] 加载Badcase失败:', err);
            content.innerHTML = '<div class="admin-empty" style="color:#dc3545">加载失败</div>';
        }
    }

    _renderBadcaseRow(bc) {
        const createdAt = bc.created_at
            ? new Date(bc.created_at * 1000).toLocaleDateString('zh-CN')
            : '—';

        return `
            <tr>
                <td>
                    ${bc.image_url ? `<img src="${escapeHtml(bc.image_url)}" alt="图片" style="width:50px;height:50px;object-fit:cover;border-radius:4px;">` : '—'}
                </td>
                <td><span class="admin-badge admin-badge--danger">${escapeHtml(bc.predicted || '—')}</span></td>
                <td><span class="admin-badge admin-badge--active">${escapeHtml(bc.correct || '—')}</span></td>
                <td>${createdAt}</td>
                <td>
                    <button class="admin-btn admin-btn-sm admin-btn-secondary"
                            data-action="deleteBadcase" data-badcase-id="${bc.id}">删除</button>
                </td>
            </tr>
        `;
    }

    _bindBadcaseActions() {
        const content = document.getElementById('adminModelsTabContent');
        if (!content) return;

        this._boundHandlers.badcaseClick = async (e) => {
            const deleteBtn = e.target.closest('[data-action="deleteBadcase"]');
            if (deleteBtn) {
                const badcaseId = deleteBtn.dataset.badcaseId;
                if (confirm('确定要删除这条Badcase记录吗？')) {
                    try {
                        await this._api.adminDeleteBadcase(badcaseId);
                        showToast('删除成功', 'success');
                        await this._loadBadcases();
                    } catch (err) {
                        showToast('删除失败', 'error');
                    }
                }
            }
        };
        content.addEventListener('click', this._boundHandlers.badcaseClick);
    }

    _showBadcaseModal(modelId) {
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal" style="max-width:600px">
                <h3 class="admin-modal__title">📋 查看Badcase</h3>
                <div id="badcaseModalContent" style="padding:12px 0">
                    <div class="admin-loading">⏳ 加载中...</div>
                </div>
                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="badcaseModalClose">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();
        document.getElementById('badcaseModalClose').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        this._loadBadcasesForModel(modelId, document.getElementById('badcaseModalContent'));
    }

    async _loadBadcasesForModel(modelId, container) {
        try {
            const data = await this._api.adminGetBadcasesByModel(modelId);
            const badcases = data.badcases || data.data || [];

            if (badcases.length === 0) {
                container.innerHTML = '<div class="admin-empty">该模型暂无Badcase记录</div>';
                return;
            }

            container.innerHTML = `
                <div class="badcase-list">
                    ${badcases.slice(0, 10).map(bc => `
                        <div class="badcase-item">
                            ${bc.image_url ? `<img src="${escapeHtml(bc.image_url)}" alt="图片" class="badcase-image">` : ''}
                            <div class="badcase-info">
                                <div>预测: <strong>${escapeHtml(bc.predicted || '—')}</strong></div>
                                <div>正确: <strong>${escapeHtml(bc.correct || '—')}</strong></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (err) {
            container.innerHTML = '<div class="admin-empty" style="color:#dc3545">加载失败</div>';
        }
    }

    _infoRow(label, value) {
        return `
            <div class="model-info-row">
                <span class="model-info-label">${label}:</span>
                <span class="model-info-value">${escapeHtml(value)}</span>
            </div>
        `;
    }

    destroy() {
        this.container?.querySelector('.admin-tabs')?.removeEventListener('click', this._boundHandlers.tabClick);
        const modelsList = document.getElementById('adminModelsList');
        modelsList?.removeEventListener('click', this._boundHandlers.contentClick);
        const content = document.getElementById('adminModelsTabContent');
        content?.removeEventListener('click', this._boundHandlers.badcaseClick);
        if (this.container) {
            this.container.innerHTML = '';
        }
        this._boundHandlers = {};
    }
}

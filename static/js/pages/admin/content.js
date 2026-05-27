import { escapeHtml } from '../../utils/escape.js';
import { showToast } from '../../utils/ui.js';

export class AdminContent {
    container = null;
    _api = null;
    _activeTab = 'vocabulary';
    _vocabularyData = [];
    _categoriesData = [];
    _boundHandlers = {};

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadVocabulary();
    }

    _render() {
        this.container.innerHTML = `
            <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin-bottom:20px">
                \u{1F4DD} 内容管理
            </h2>

            <div class="admin-tabs">
                <button class="admin-tab active" data-tab="vocabulary">词库管理</button>
                <button class="admin-tab" data-tab="categories">分类标准</button>
            </div>

            <div id="adminContentTabContent"></div>
        `;

        this._boundHandlers.tabClick = (e) => {
            const tab = e.target.closest('.admin-tab');
            if (!tab) return;
            this.container.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            this._activeTab = tab.dataset.tab;

            if (this._activeTab === 'vocabulary') this._loadVocabulary();
            else this._loadCategories();
        };
        this.container.querySelector('.admin-tabs').addEventListener('click', this._boundHandlers.tabClick);

        this._boundHandlers.contentClick = async (e) => {
            const vocabBtn = e.target.closest('[data-action="editVocab"]');
            if (vocabBtn) {
                const idx = parseInt(vocabBtn.dataset.idx);
                this._showVocabEditModal(this._vocabularyData[idx], idx);
                return;
            }

            const catBtn = e.target.closest('[data-action="saveCat"]');
            if (catBtn) {
                const idx = parseInt(catBtn.dataset.idx);
                const content = document.getElementById('adminContentTabContent');
                const catData = { ...this._categoriesData[idx] };
                content.querySelectorAll(`[data-cat-idx="${idx}"]`).forEach(textarea => {
                    const field = textarea.dataset.field;
                    catData[field] = textarea.value.trim();
                });

                catBtn.disabled = true;
                catBtn.textContent = '保存中...';

                try {
                    await this._api.adminUpdateCategories(this._categoriesData);
                    this._categoriesData[idx] = catData;
                } catch (err) {
                    console.error('[AdminContent] 分类更新失败:', err);
                    showToast('保存失败，请重试', 'error');
                } finally {
                    catBtn.disabled = false;
                    catBtn.textContent = '保存';
                }
            }
        };
        document.getElementById('adminContentTabContent').addEventListener('click', this._boundHandlers.contentClick);
    }

    async _loadVocabulary() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;
        content.innerHTML = '<div class="admin-loading">\u23F3 加载中...</div>';

        try {
            const data = await this._api.adminGetVocabulary();
            this._vocabularyData = data.items || data.data || [];
            this._renderVocabulary();
        } catch (err) {
            content.innerHTML = '<div class="admin-empty" style="color:#dc3545">词库加载失败</div>';
        }
    }

    _renderVocabulary() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;

        if (this._vocabularyData.length === 0) {
            content.innerHTML = '<div class="admin-empty">词库为空</div>';
            return;
        }

        content.innerHTML = `
            <div class="admin-card" style="padding:0;overflow:hidden">
                <div class="admin-table-wrap">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>物品名称</th>
                                <th>分类</th>
                                <th>别名</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this._vocabularyData.map((item, idx) => `
                                <tr>
                                    <td>${escapeHtml(item.label || item.name || '')}</td>
                                    <td>${escapeHtml(item.category || '')}</td>
                                    <td style="font-size:12px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                                        ${escapeHtml((item.aliases || []).join(', ') || '—')}
                                    </td>
                                    <td>
                                        <button class="admin-btn admin-btn-sm admin-btn-secondary"
                                                data-action="editVocab" data-idx="${idx}">编辑</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    _showVocabEditModal(item, idx) {
        const aliasesStr = (item.aliases || []).join(', ');
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal">
                <h3 class="admin-modal__title">编辑词条</h3>
                <div class="admin-form-group">
                    <label>物品名称</label>
                    <input class="admin-input" id="vocabEditLabel" value="${escapeHtml(item.label || item.name || '')}">
                </div>
                <div class="admin-form-group">
                    <label>分类</label>
                    <input class="admin-input" id="vocabEditCategory" value="${escapeHtml(item.category || '')}">
                </div>
                <div class="admin-form-group">
                    <label>别名（逗号分隔）</label>
                    <input class="admin-input" id="vocabEditAliases" value="${escapeHtml(aliasesStr)}">
                </div>
                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="vocabEditCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="vocabEditSave">保存</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('vocabEditCancel').addEventListener('click', closeModal);

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('vocabEditSave').addEventListener('click', async () => {
            const label = document.getElementById('vocabEditLabel').value.trim();
            const category = document.getElementById('vocabEditCategory').value.trim();
            const aliasesRaw = document.getElementById('vocabEditAliases').value.trim();

            if (!label || !category) {
                showToast('物品名称和分类不能为空', 'error');
                return;
            }

            this._vocabularyData[idx] = {
                ...this._vocabularyData[idx],
                label: label,
                name: label,
                category: category,
                aliases: aliasesRaw ? aliasesRaw.split(',').map(s => s.trim()).filter(Boolean) : []
            };

            try {
                await this._api.adminUpdateVocabulary(this._vocabularyData);
                closeModal();
                this._renderVocabulary();
            } catch (err) {
                console.error('[AdminContent] 词库更新失败:', err);
                showToast('保存失败，请重试', 'error');
            }
        });
    }

    async _loadCategories() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;
        content.innerHTML = '<div class="admin-loading">\u23F3 加载中...</div>';

        try {
            const data = await this._api.adminGetCategories();
            this._categoriesData = data.categories || data.data || [];
            this._renderCategories();
        } catch (err) {
            content.innerHTML = '<div class="admin-empty" style="color:#dc3545">分类加载失败</div>';
        }
    }

    _renderCategories() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;

        if (this._categoriesData.length === 0) {
            content.innerHTML = '<div class="admin-empty">暂无分类数据</div>';
            return;
        }

        const catColors = {
            '\u53EF\u56DE\u6536\u7269': '#007bff',
            '\u6709\u5BB3\u5783\u573E': '#dc3545',
            '\u53A8\u4F59\u5783\u573E': '#8B4513',
            '\u5176\u4ED6\u5783\u573E': '#333333'
        };

        content.innerHTML = this._categoriesData.map((cat, idx) => `
            <div class="admin-card" style="border-left:4px solid ${cat.color || catColors[cat.name] || '#999'}">
                <h3 style="font-size:16px;font-weight:600;margin-bottom:12px;color:var(--text-primary)">
                    ${escapeHtml(cat.name || '')}
                </h3>
                <div class="admin-form-group">
                    <label>定义描述</label>
                    <textarea class="admin-textarea" data-cat-idx="${idx}" data-field="definition"
                              placeholder="输入分类定义...">${escapeHtml(cat.definition || '')}</textarea>
                </div>
                <div class="admin-form-group">
                    <label>投放注意事项</label>
                    <textarea class="admin-textarea" data-cat-idx="${idx}" data-field="tips"
                              placeholder="输入投放注意事项...">${escapeHtml(cat.tips || '')}</textarea>
                </div>
                <button class="admin-btn admin-btn-primary admin-btn-sm"
                        data-action="saveCat" data-idx="${idx}">保存</button>
            </div>
        `).join('');
    }

    destroy() {
        this.container?.querySelector('.admin-tabs')?.removeEventListener('click', this._boundHandlers.tabClick);
        document.getElementById('adminContentTabContent')?.removeEventListener('click', this._boundHandlers.contentClick);
        if (this.container) {
            this.container.innerHTML = '';
        }
        this._boundHandlers = {};
        this._vocabularyData = [];
        this._categoriesData = [];
    }
}

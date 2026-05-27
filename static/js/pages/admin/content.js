import { escapeHtml } from '../../utils/escape.js';
import { showToast, confirm } from '../../utils/ui.js';

export class AdminContent {
    container = null;
    _api = null;
    _activeTab = 'vocabulary';
    _vocabularyData = [];
    _categoriesData = [];
    _confusingData = [];
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
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
                <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin:0">
                    📝 内容管理
                </h2>
            </div>

            <div class="admin-tabs">
                <button class="admin-tab active" data-tab="vocabulary">词库管理</button>
                <button class="admin-tab" data-tab="categories">分类标准</button>
                <button class="admin-tab" data-tab="confusing">易错物品对</button>
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
            else if (this._activeTab === 'categories') this._loadCategories();
            else if (this._activeTab === 'confusing') this._loadConfusing();
        };
        this.container.querySelector('.admin-tabs').addEventListener('click', this._boundHandlers.tabClick);

        this._boundHandlers.contentClick = async (e) => {
            const vocabBtn = e.target.closest('[data-action="editVocab"]');
            if (vocabBtn) {
                const idx = parseInt(vocabBtn.dataset.idx);
                this._showVocabEditModal(this._vocabularyData[idx], idx);
                return;
            }

            const deleteVocabBtn = e.target.closest('[data-action="deleteVocab"]');
            if (deleteVocabBtn) {
                const idx = parseInt(deleteVocabBtn.dataset.idx);
                const item = this._vocabularyData[idx];
                const label = item.label || item.name || '';
                const confirmed = await confirm(`确定要删除词条「${label}」吗？`);
                if (!confirmed) return;
                deleteVocabBtn.disabled = true;
                deleteVocabBtn.textContent = '删除中...';
                try {
                    await this._api.adminDeleteVocabularyItem(label);
                    showToast('词条已删除', 'success');
                    this._loadVocabulary();
                } catch (err) {
                    console.error('[AdminContent] 删除词条失败:', err);
                    showToast('删除失败，请重试', 'error');
                    deleteVocabBtn.disabled = false;
                    deleteVocabBtn.textContent = '删除';
                }
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

            const deleteConfusingBtn = e.target.closest('[data-action="deleteConfusing"]');
            if (deleteConfusingBtn) {
                const pairId = parseInt(deleteConfusingBtn.dataset.pairId);
                const pair = this._confusingData.find(p => p.id === pairId);
                const nameA = pair?.item_a?.name || '';
                const nameB = pair?.item_b?.name || '';
                const confirmed = await confirm(`确定要删除易错物品对「${nameA} vs ${nameB}」吗？`);
                if (!confirmed) return;
                deleteConfusingBtn.disabled = true;
                deleteConfusingBtn.textContent = '删除中...';
                try {
                    await this._api.adminDeleteConfusingPair(pairId);
                    showToast('易错物品对已删除', 'success');
                    this._loadConfusing();
                } catch (err) {
                    console.error('[AdminContent] 删除易错物品对失败:', err);
                    showToast('删除失败，请重试', 'error');
                    deleteConfusingBtn.disabled = false;
                    deleteConfusingBtn.textContent = '删除';
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
            content.innerHTML = `
                <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
                    <button class="admin-btn admin-btn-primary" id="adminAddVocabBtn">+ 新增词条</button>
                </div>
                <div class="admin-empty">词库为空</div>
            `;
            document.getElementById('adminAddVocabBtn')?.addEventListener('click', () => this._showVocabCreateModal());
            return;
        }

        content.innerHTML = `
            <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
                <button class="admin-btn admin-btn-primary" id="adminAddVocabBtn">+ 新增词条</button>
            </div>
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
                                        <button class="admin-btn admin-btn-sm admin-btn-danger"
                                                data-action="deleteVocab" data-idx="${idx}">删除</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        document.getElementById('adminAddVocabBtn')?.addEventListener('click', () => this._showVocabCreateModal());
    }

    _showVocabCreateModal() {
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal">
                <h3 class="admin-modal__title">新增词条</h3>
                <div class="admin-form-group">
                    <label>物品名称 <span style="color:#dc3545">*</span></label>
                    <input class="admin-input" id="vocabCreateLabel" placeholder="如：外卖餐盒">
                </div>
                <div class="admin-form-group">
                    <label>分类 <span style="color:#dc3545">*</span></label>
                    <select class="admin-select" id="vocabCreateCategory">
                        <option value="可回收物">可回收物</option>
                        <option value="有害垃圾">有害垃圾</option>
                        <option value="厨余垃圾">厨余垃圾</option>
                        <option value="其他垃圾">其他垃圾</option>
                    </select>
                </div>
                <div class="admin-form-group">
                    <label>别名（逗号分隔）</label>
                    <input class="admin-input" id="vocabCreateAliases" placeholder="如：外卖盒,打包盒">
                </div>
                <div class="admin-form-group">
                    <label>投放指引</label>
                    <textarea class="admin-textarea" id="vocabCreateGuidance" rows="2" placeholder="投放建议"></textarea>
                </div>
                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="vocabCreateCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="vocabCreateSave">创建</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('vocabCreateCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('vocabCreateSave').addEventListener('click', async () => {
            const label = document.getElementById('vocabCreateLabel').value.trim();
            const category = document.getElementById('vocabCreateCategory').value;
            const aliasesRaw = document.getElementById('vocabCreateAliases').value.trim();
            const guidance = document.getElementById('vocabCreateGuidance').value.trim();

            if (!label) {
                showToast('物品名称不能为空', 'error');
                return;
            }

            const saveBtn = document.getElementById('vocabCreateSave');
            saveBtn.disabled = true;
            saveBtn.textContent = '创建中...';

            try {
                await this._api.adminAddVocabularyItem({
                    label: label,
                    category: category,
                    aliases: aliasesRaw ? aliasesRaw.split(',').map(s => s.trim()).filter(Boolean) : [],
                    guidance: guidance,
                });
                showToast('词条创建成功', 'success');
                closeModal();
                this._loadVocabulary();
            } catch (err) {
                console.error('[AdminContent] 创建词条失败:', err);
                showToast('创建失败，请重试', 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = '创建';
            }
        });

        document.getElementById('vocabCreateLabel').focus();
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

    async _loadConfusing() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;
        content.innerHTML = '<div class="admin-loading">\u23F3 加载中...</div>';

        try {
            const data = await this._api.adminGetConfusingPairs();
            this._confusingData = data.pairs || data.data || [];
            this._renderConfusing();
        } catch (err) {
            content.innerHTML = '<div class="admin-empty" style="color:#dc3545">易错物品对加载失败</div>';
        }
    }

    _renderConfusing() {
        const content = document.getElementById('adminContentTabContent');
        if (!content) return;

        // 混淆频率标签样式映射
        const freqStyle = {
            critical: 'background:#dc3545;color:#fff',
            high: 'background:#fd7e14;color:#fff',
            medium: 'background:#ffc107;color:#333',
            low: 'background:#28a745;color:#fff',
        };
        const freqLabel = { critical: '极易混淆', high: '高', medium: '中', low: '低' };

        if (this._confusingData.length === 0) {
            content.innerHTML = `
                <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
                    <button class="admin-btn admin-btn-primary" id="adminAddConfusingBtn">+ 新增易错物品对</button>
                </div>
                <div class="admin-empty">暂无易错物品对数据</div>
            `;
            document.getElementById('adminAddConfusingBtn')?.addEventListener('click', () => this._showConfusingCreateModal());
            return;
        }

        content.innerHTML = `
            <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
                <button class="admin-btn admin-btn-primary" id="adminAddConfusingBtn">+ 新增易错物品对</button>
            </div>
            <div class="admin-card" style="padding:0;overflow:hidden">
                <div class="admin-table-wrap">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>物品A</th>
                                <th>物品B</th>
                                <th>关键区别</th>
                                <th>混淆频率</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this._confusingData.map(pair => {
                                const a = pair.item_a || {};
                                const b = pair.item_b || {};
                                const f = pair.frequency || 'medium';
                                return `
                                <tr>
                                    <td>
                                        <div style="font-weight:600">${escapeHtml(a.name || '')}</div>
                                        <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(a.category || '')}</div>
                                    </td>
                                    <td>
                                        <div style="font-weight:600">${escapeHtml(b.name || '')}</div>
                                        <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(b.category || '')}</div>
                                    </td>
                                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                                        ${escapeHtml(pair.key_difference || '')}
                                    </td>
                                    <td>
                                        <span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;${freqStyle[f] || freqStyle.medium}">
                                            ${freqLabel[f] || f}
                                        </span>
                                    </td>
                                    <td>
                                        <button class="admin-btn admin-btn-sm admin-btn-danger"
                                                data-action="deleteConfusing" data-pair-id="${pair.id}">删除</button>
                                    </td>
                                </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        document.getElementById('adminAddConfusingBtn')?.addEventListener('click', () => this._showConfusingCreateModal());
    }

    _showConfusingCreateModal() {
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal" style="max-width:600px">
                <h3 class="admin-modal__title">新增易错物品对</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 16px">
                    <h4 style="grid-column:1;font-size:14px;margin:8px 0 4px;color:var(--text-primary)">物品A</h4>
                    <h4 style="grid-column:2;font-size:14px;margin:8px 0 4px;color:var(--text-primary)">物品B</h4>

                    <div class="admin-form-group">
                        <label>名称 <span style="color:#dc3545">*</span></label>
                        <input class="admin-input" id="confusingCreateAName" placeholder="如：奶茶杯(干净)">
                    </div>
                    <div class="admin-form-group">
                        <label>名称 <span style="color:#dc3545">*</span></label>
                        <input class="admin-input" id="confusingCreateBName" placeholder="如：奶茶杯(有残留)">
                    </div>

                    <div class="admin-form-group">
                        <label>分类 <span style="color:#dc3545">*</span></label>
                        <select class="admin-select" id="confusingCreateACategory">
                            <option value="可回收物">可回收物</option>
                            <option value="有害垃圾">有害垃圾</option>
                            <option value="厨余垃圾">厨余垃圾</option>
                            <option value="其他垃圾">其他垃圾</option>
                        </select>
                    </div>
                    <div class="admin-form-group">
                        <label>分类 <span style="color:#dc3545">*</span></label>
                        <select class="admin-select" id="confusingCreateBCategory">
                            <option value="可回收物">可回收物</option>
                            <option value="有害垃圾">有害垃圾</option>
                            <option value="厨余垃圾">厨余垃圾</option>
                            <option value="其他垃圾">其他垃圾</option>
                        </select>
                    </div>

                    <div class="admin-form-group">
                        <label>分类原因 <span style="color:#dc3545">*</span></label>
                        <textarea class="admin-textarea" id="confusingCreateAReason" rows="2" placeholder="为何属于此分类"></textarea>
                    </div>
                    <div class="admin-form-group">
                        <label>分类原因 <span style="color:#dc3545">*</span></label>
                        <textarea class="admin-textarea" id="confusingCreateBReason" rows="2" placeholder="为何属于此分类"></textarea>
                    </div>
                </div>

                <div class="admin-form-group">
                    <label>关键区别 <span style="color:#dc3545">*</span></label>
                    <input class="admin-input" id="confusingCreateKeyDiff" placeholder="如：是否清洗干净">
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 16px">
                    <div class="admin-form-group">
                        <label>混淆频率</label>
                        <select class="admin-select" id="confusingCreateFrequency">
                            <option value="critical">极易混淆</option>
                            <option value="high">高</option>
                            <option value="medium" selected>中</option>
                            <option value="low">低</option>
                        </select>
                    </div>
                    <div class="admin-form-group">
                        <label>场景</label>
                        <input class="admin-input" id="confusingCreateScene" placeholder="如：食堂/宿舍">
                    </div>
                </div>
                <div class="admin-form-group">
                    <label>标签（逗号分隔）</label>
                    <input class="admin-input" id="confusingCreateTags" placeholder="如：奶茶,杯子,塑料">
                </div>

                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="confusingCreateCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="confusingCreateSave">创建</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('confusingCreateCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('confusingCreateSave').addEventListener('click', async () => {
            const aName = document.getElementById('confusingCreateAName').value.trim();
            const aCategory = document.getElementById('confusingCreateACategory').value;
            const aReason = document.getElementById('confusingCreateAReason').value.trim();
            const bName = document.getElementById('confusingCreateBName').value.trim();
            const bCategory = document.getElementById('confusingCreateBCategory').value;
            const bReason = document.getElementById('confusingCreateBReason').value.trim();
            const keyDiff = document.getElementById('confusingCreateKeyDiff').value.trim();
            const frequency = document.getElementById('confusingCreateFrequency').value;
            const scene = document.getElementById('confusingCreateScene').value.trim();
            const tagsRaw = document.getElementById('confusingCreateTags').value.trim();

            // 必填校验
            if (!aName || !bName || !aReason || !bReason || !keyDiff) {
                showToast('物品名称、分类原因和关键区别不能为空', 'error');
                return;
            }

            const saveBtn = document.getElementById('confusingCreateSave');
            saveBtn.disabled = true;
            saveBtn.textContent = '创建中...';

            try {
                await this._api.adminAddConfusingPair({
                    item_a_name: aName,
                    item_a_category: aCategory,
                    item_a_reason: aReason,
                    item_b_name: bName,
                    item_b_category: bCategory,
                    item_b_reason: bReason,
                    key_difference: keyDiff,
                    frequency: frequency,
                    scene: scene,
                    tags: tagsRaw ? tagsRaw.split(',').map(s => s.trim()).filter(Boolean) : [],
                });
                showToast('易错物品对创建成功', 'success');
                closeModal();
                this._loadConfusing();
            } catch (err) {
                console.error('[AdminContent] 创建易错物品对失败:', err);
                showToast('创建失败，请重试', 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = '创建';
            }
        });

        document.getElementById('confusingCreateAName').focus();
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
        this._confusingData = [];
    }
}

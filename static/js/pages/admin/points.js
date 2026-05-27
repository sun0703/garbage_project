import { escapeHtml } from '../../utils/escape.js';
import { showToast, confirm } from '../../utils/ui.js';

export class AdminPoints {
    container = null;
    _api = null;
    _pointsData = [];
    _boundHandlers = {};

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadPoints();
    }

    _render() {
        this.container.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
                <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin:0">
                    📍 投放点维护
                </h2>
                <div style="display:flex;gap:8px">
                    <button class="admin-btn admin-btn-secondary" id="adminImportBtn">📥 批量导入</button>
                    <button class="admin-btn admin-btn-primary" id="adminAddPointBtn">+ 新增投放点</button>
                </div>
            </div>

            <div class="admin-search-bar" style="margin-bottom:16px">
                <input type="text" class="admin-input" id="adminPointSearch"
                       placeholder="搜索投放点名称或区域..." style="max-width:280px">
                <select class="admin-select" id="adminPointZoneFilter">
                    <option value="">全部区域</option>
                </select>
                <button class="admin-btn admin-btn-primary" id="adminPointSearchBtn">搜索</button>
            </div>

            <div class="admin-card" style="padding:0;overflow:hidden">
                <div class="admin-table-wrap">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>名称</th>
                                <th>区域</th>
                                <th>类别</th>
                                <th>经度</th>
                                <th>纬度</th>
                                <th>地址</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="adminPointsTableBody">
                            <tr><td colspan="7" class="admin-loading">⏳ 加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        this._boundHandlers.addPoint = () => {
            this._showPointModal();
        };
        document.getElementById('adminAddPointBtn').addEventListener('click', this._boundHandlers.addPoint);

        this._boundHandlers.importClick = () => {
            this._showImportModal();
        };
        document.getElementById('adminImportBtn').addEventListener('click', this._boundHandlers.importClick);

        this._boundHandlers.searchClick = () => {
            this._loadPoints();
        };
        document.getElementById('adminPointSearchBtn').addEventListener('click', this._boundHandlers.searchClick);

        this._boundHandlers.searchKeypress = (e) => {
            if (e.key === 'Enter') this._loadPoints();
        };
        document.getElementById('adminPointSearch').addEventListener('keypress', this._boundHandlers.searchKeypress);

        this._boundHandlers.tbodyClick = async (e) => {
            const editBtn = e.target.closest('[data-action="editPoint"]');
            if (editBtn) {
                const idx = parseInt(editBtn.dataset.idx);
                this._showPointModal(this._pointsData[idx], idx);
                return;
            }

            const deleteBtn = e.target.closest('[data-action="deletePoint"]');
            if (deleteBtn) {
                const idx = parseInt(deleteBtn.dataset.idx);
                const point = this._pointsData[idx];
                const confirmed = await confirm(`确定要删除投放点「${point.name}」吗？此操作不可撤销。`);
                if (!confirmed) return;
                deleteBtn.disabled = true;
                deleteBtn.textContent = '删除中...';
                try {
                    await this._api.adminDeletePoint(point.id);
                    showToast('删除成功', 'success');
                    this._loadPoints();
                } catch (err) {
                    console.error('[AdminPoints] 删除失败:', err);
                    showToast('删除失败，请重试', 'error');
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '删除';
                }
            }
        };
        document.getElementById('adminPointsTableBody').addEventListener('click', this._boundHandlers.tbodyClick);
    }

    async _loadPoints() {
        const tbody = document.getElementById('adminPointsTableBody');
        if (!tbody) return;

        const search = document.getElementById('adminPointSearch')?.value.trim() || '';
        const zoneFilter = document.getElementById('adminPointZoneFilter')?.value || '';

        try {
            const data = await this._api.adminGetPoints();
            let points = data.points || data.data || [];

            if (search) {
                const lower = search.toLowerCase();
                points = points.filter(p =>
                    (p.name || '').toLowerCase().includes(lower) ||
                    (p.zone || p.area || '').toLowerCase().includes(lower) ||
                    (p.address || '').toLowerCase().includes(lower)
                );
            }

            if (zoneFilter) {
                points = points.filter(p =>
                    (p.zone || p.area || '') === zoneFilter
                );
            }

            this._pointsData = points;
            this._updateZoneOptions(data.points || data.data || []);

            if (points.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="admin-empty">暂无投放点数据</td></tr>';
            } else {
                tbody.innerHTML = points.map((p, idx) => `
                    <tr>
                        <td><strong>${escapeHtml(p.name || '—')}</strong></td>
                        <td>${escapeHtml(p.zone || p.area || '—')}</td>
                        <td>${escapeHtml(Array.isArray(p.categories) ? p.categories.join(', ') : (p.category || '—'))}</td>
                        <td>${p.lng ?? '—'}</td>
                        <td>${p.lat ?? '—'}</td>
                        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                            title="${escapeHtml(p.address || '')}">
                            ${escapeHtml(p.address || '—')}
                        </td>
                        <td>
                            <button class="admin-btn admin-btn-sm admin-btn-secondary"
                                    data-action="editPoint" data-idx="${idx}">编辑</button>
                            <button class="admin-btn admin-btn-sm admin-btn-danger"
                                    data-action="deletePoint" data-idx="${idx}">删除</button>
                        </td>
                    </tr>
                `).join('');
            }
        } catch (err) {
            console.error('[AdminPoints] 加载投放点失败:', err);
            tbody.innerHTML = '<tr><td colspan="7" class="admin-empty" style="color:#dc3545">加载失败</td></tr>';
        }
    }

    _updateZoneOptions(allPoints) {
        const select = document.getElementById('adminPointZoneFilter');
        if (!select) return;

        const zones = [...new Set((allPoints || [])
            .map(p => p.zone || p.area)
            .filter(Boolean))].sort();

        select.innerHTML = '<option value="">全部区域</option>' +
            zones.map(z => `<option value="${escapeHtml(z)}">${escapeHtml(z)}</option>`).join('');
    }

    _showPointModal(point = null, idx = null) {
        const isEdit = !!point;
        const title = isEdit ? '编辑投放点' : '新增投放点';

        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal" style="max-width:520px">
                <h3 class="admin-modal__title">${title}</h3>
                <div class="admin-form-group">
                    <label>投放点名称 <span style="color:#dc3545">*</span></label>
                    <input class="admin-input" id="pointEditName" value="${escapeHtml(point?.name || '')}"
                           placeholder="例如：东区教学楼投放点">
                </div>
                <div class="admin-form-group">
                    <label>区域 <span style="color:#dc3545">*</span></label>
                    <input class="admin-input" id="pointEditZone" value="${escapeHtml(point?.zone || point?.area || '')}"
                           placeholder="例如：东区、南区">
                </div>
                <div class="admin-form-group">
                    <label>垃圾类别</label>
                    <input class="admin-input" id="pointEditCategories"
                           value="${escapeHtml(Array.isArray(point?.categories) ? point.categories.join(', ') : (point?.category || ''))}"
                           placeholder="可回收物,厨余垃圾 (逗号分隔)">
                </div>
                <div style="display:flex;gap:12px">
                    <div class="admin-form-group" style="flex:1">
                        <label>经度</label>
                        <input class="admin-input" id="pointEditLng" type="number" step="any"
                               value="${point?.lng ?? ''}" placeholder="如：116.4074">
                    </div>
                    <div class="admin-form-group" style="flex:1">
                        <label>纬度</label>
                        <input class="admin-input" id="pointEditLat" type="number" step="any"
                               value="${point?.lat ?? ''}" placeholder="如：39.9042">
                    </div>
                </div>
                <div class="admin-form-group">
                    <label>详细地址</label>
                    <input class="admin-input" id="pointEditAddress" value="${escapeHtml(point?.address || '')}"
                           placeholder="详细地址描述">
                </div>
                <div class="admin-form-group">
                    <label>备注</label>
                    <input class="admin-input" id="pointEditNote" value="${escapeHtml(point?.note || '')}"
                           placeholder="其他说明信息">
                </div>
                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="pointEditCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="pointEditSave">
                        ${isEdit ? '保存修改' : '创建'}
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('pointEditCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('pointEditSave').addEventListener('click', async () => {
            const name = document.getElementById('pointEditName').value.trim();
            const zone = document.getElementById('pointEditZone').value.trim();

            if (!name) {
                showToast('投放点名称不能为空', 'error');
                return;
            }

            if (!zone) {
                showToast('区域不能为空', 'error');
                return;
            }

            const formData = {
                name: name,
                zone: zone,
                categories: document.getElementById('pointEditCategories').value
                    .split(',').map(s => s.trim()).filter(Boolean),
                lng: parseFloat(document.getElementById('pointEditLng').value) || 0,
                lat: parseFloat(document.getElementById('pointEditLat').value) || 0,
                address: document.getElementById('pointEditAddress').value.trim(),
                note: document.getElementById('pointEditNote').value.trim()
            };

            const saveBtn = document.getElementById('pointEditSave');
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';

            try {
                if (isEdit) {
                    await this._api.adminUpdatePoint(point.id, formData);
                    showToast('修改成功', 'success');
                } else {
                    await this._api.adminCreatePoint(formData);
                    showToast('创建成功', 'success');
                }
                closeModal();
                this._loadPoints();
            } catch (err) {
                console.error('[AdminPoints] 保存投放点失败:', err);
                showToast('保存失败，请重试', 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = isEdit ? '保存修改' : '创建';
            }
        });

        document.getElementById('pointEditName').focus();
    }

    _showImportModal() {
        const overlay = document.createElement('div');
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = `
            <div class="admin-modal" style="max-width:600px">
                <h3 class="admin-modal__title">📥 批量导入投放点</h3>

                <div style="margin-bottom:16px">
                    <p style="font-size:13px;color:#666;line-height:1.6">
                        请上传 JSON 格式的文件，每行一个投放点对象：
                    </p>
                    <pre style="background:#f5f5f5;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto">
[
  {"name": "投放点A", "zone": "东区", "lng": 116.4, "lat": 39.9, "categories": ["可回收物"]},
  {"name": "投放点B", "zone": "西区", "lng": 116.5, "lat": 39.8, "categories": ["厨余垃圾"]}
]</pre>
                </div>

                <div class="admin-form-group">
                    <label>或粘贴 JSON 数据</label>
                    <textarea class="admin-textarea" id="importJsonData"
                              rows="8" placeholder="[&#10;  {"name": "...", "zone": "...", ...}&#10;]"></textarea>
                </div>

                <div style="color:#dc3545;font-size:12px;margin-bottom:12px">
                    ⚠️ 导入将追加新数据，不会覆盖已有数据
                </div>

                <div class="admin-modal__footer">
                    <button class="admin-btn admin-btn-secondary" id="importCancel">取消</button>
                    <button class="admin-btn admin-btn-primary" id="importConfirm">确认导入</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();

        document.getElementById('importCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        document.getElementById('importConfirm').addEventListener('click', async () => {
            const jsonStr = document.getElementById('importJsonData').value.trim();

            if (!jsonStr) {
                showToast('请输入JSON数据', 'error');
                return;
            }

            let points;
            try {
                points = JSON.parse(jsonStr);
            } catch (e) {
                showToast('JSON格式错误，请检查', 'error');
                return;
            }

            if (!Array.isArray(points)) {
                showToast('JSON必须是一个数组', 'error');
                return;
            }

            const saveBtn = document.getElementById('importConfirm');
            saveBtn.disabled = true;
            saveBtn.textContent = '导入中...';

            try {
                let successCount = 0;
                for (const point of points) {
                    if (point.name && point.zone) {
                        await this._api.adminCreatePoint({
                            name: point.name,
                            zone: point.zone,
                            categories: point.categories || [],
                            lng: point.lng || 0,
                            lat: point.lat || 0,
                            address: point.address || '',
                            note: point.note || ''
                        });
                        successCount++;
                    }
                }

                showToast(`成功导入 ${successCount} 个投放点`, 'success');
                closeModal();
                this._loadPoints();
            } catch (err) {
                console.error('[AdminPoints] 批量导入失败:', err);
                showToast('导入失败，请重试', 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = '确认导入';
            }
        });
    }

    destroy() {
        document.getElementById('adminAddPointBtn')?.removeEventListener('click', this._boundHandlers.addPoint);
        document.getElementById('adminImportBtn')?.removeEventListener('click', this._boundHandlers.importClick);
        document.getElementById('adminPointSearchBtn')?.removeEventListener('click', this._boundHandlers.searchClick);
        document.getElementById('adminPointSearch')?.removeEventListener('keypress', this._boundHandlers.searchKeypress);
        document.getElementById('adminPointsTableBody')?.removeEventListener('click', this._boundHandlers.tbodyClick);
        if (this.container) {
            this.container.innerHTML = '';
        }
        this._boundHandlers = {};
        this._pointsData = [];
    }
}

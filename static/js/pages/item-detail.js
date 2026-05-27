// 物品详情页 — 单个垃圾的完整投放指引
// 数据来自 /api/guide/item/:keyword

import { api } from '../api.js';
import { store } from '../store.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { escapeHtml } from '../utils/escape.js';
import { ConfusingPairCard } from '../components/confusing-pair-card.js';

const CATEGORY_COLORS = {
    0: { bg: '#8B4513', light: '#FFF3E0', name: '厨余垃圾' },
    1: { bg: '#007bff', light: '#E3F2FD', name: '可回收物' },
    2: { bg: '#333333', light: '#F5F5F5', name: '其他垃圾' },
    3: { bg: '#dc3545', light: '#FFEBEE', name: '有害垃圾' },
};

export class ItemDetailPage {
    container = null;
    _keyword = '';
    _pairCard = null;
    _boundHandlers = {};

    init(params = {}) {
        this.container = document.getElementById('page-item');
        if (!this.container) {
            console.error('[ItemDetailPage] 容器 #page-item 不存在');
            return;
        }

        this._keyword = params.keyword || store.getState('currentItemKeyword') || '';
        if (!this._keyword) {
            this.container.innerHTML = `<div class="card empty-categories"><p>未指定物品</p></div>`;
            return;
        }

        this._pairCard = new ConfusingPairCard();
        this._render();
        this._loadItem(this._keyword);

        console.log('[ItemDetailPage] 物品详情页初始化完成, keyword:', this._keyword);
    }

    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.container = null;
        this._keyword = '';
        if (this._pairCard) {
            this._pairCard.destroy();
            this._pairCard = null;
        }
        this._boundHandlers = {};
    }

    _render() {
        this.container.innerHTML = `
            <div class="item-detail-nav">
                <button class="nav-back-btn" id="itemBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="item-detail-nav-title">物品详情</h2>
            </div>
            <div id="itemDetailContent">
                <div class="guide-loading-skeleton">
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                </div>
            </div>
        `;
    }

    async _loadItem(keyword) {
        const content = document.getElementById('itemDetailContent');
        if (!content) return;

        try {
            const response = await api.getGuideItem(keyword);

            if (!response.success) {
                content.innerHTML = `<div class="card empty-categories"><p>未找到物品 "${escapeHtml(keyword)}"</p></div>`;
                return;
            }

            this._renderDetail(content, response);
        } catch (error) {
            console.warn('[ItemDetailPage] 加载物品详情失败:', error);
            content.innerHTML = `<div class="card empty-categories"><p>加载失败，请稍后重试</p></div>`;
        }
    }

    _renderDetail(container, data) {
        const item = data.item || {};
        const steps = data.disposal_steps || [];
        const tips = data.disposal_tips || [];
        const related = data.related_items || [];
        const confusing = data.confusing_pairs || [];

        const catId = item.category_id ?? 0;
        const catInfo = CATEGORY_COLORS[catId] || {};
        const catName = escapeHtml(item.category_name || catInfo.name || '未知');
        const label = escapeHtml(item.label || item.match_label || this._keyword);
        const guidance = escapeHtml(item.guidance || '');
        const aliases = (item.aliases || []).map(a => escapeHtml(a));

        const stepsHTML = steps.map(s => `
            <div class="step-item">
                <div class="step-number">${s.step}</div>
                <div class="step-content">
                    <div class="step-action">${escapeHtml(s.action)}</div>
                    <div class="step-desc">${escapeHtml(s.desc)}</div>
                </div>
            </div>
        `).join('');

        const tipsHTML = tips.map(t => `
            <li class="detail-tip-item">
                <span class="tip-bullet">💡</span>
                <span>${escapeHtml(t)}</span>
            </li>
        `).join('');

        const relatedHTML = related.map(r => `
            <div class="related-item-chip" data-keyword="${escapeHtml(r.label)}">
                ${escapeHtml(r.label)}
            </div>
        `).join('');

        container.innerHTML = `
            <div class="item-hero" style="background: ${catInfo.bg || '#666'}">
                <div class="item-hero-cat">${catName}</div>
                <h2 class="item-hero-name">${label}</h2>
                ${aliases.length > 0 ? `<div class="item-hero-aliases">${aliases.map(a => `<span class="alias-tag">${a}</span>`).join('')}</div>` : ''}
            </div>

            ${guidance ? `
            <div class="item-guidance card">
                <div class="guidance-icon">🪣</div>
                <div class="guidance-text">${guidance}</div>
            </div>
            ` : ''}

            ${steps.length > 0 ? `
            <div class="item-section card">
                <h3 class="item-section-title">📋 处理步骤</h3>
                <div class="steps-flow">
                    ${stepsHTML}
                </div>
            </div>
            ` : ''}

            ${tips.length > 0 ? `
            <div class="item-section card">
                <h3 class="item-section-title">💡 注意事项</h3>
                <ul class="detail-tips-list">${tipsHTML}</ul>
            </div>
            ` : ''}

            ${confusing.length > 0 ? `
            <div class="item-section">
                <h3 class="item-section-title">⚠️ 易混淆提醒</h3>
                <div class="item-confusing-list"></div>
            </div>
            ` : ''}

            ${related.length > 0 ? `
            <div class="item-section card">
                <h3 class="item-section-title">📦 同类物品</h3>
                <div class="related-items-grid">${relatedHTML}</div>
            </div>
            ` : ''}
        `;

        this._bindDetailEvents();

        if (confusing.length > 0 && this._pairCard) {
            const confusingContainer = container.querySelector('.item-confusing-list');
            confusing.slice(0, 3).forEach(pair => {
                const compactEl = this._pairCard.renderCompact(pair);
                confusingContainer.appendChild(compactEl);
            });
        }
    }

    _bindDetailEvents() {
        const backBtn = document.getElementById('itemBackBtn');
        if (backBtn) {
            this._boundHandlers.back = () => { window.location.hash = '#/'; };
            backBtn.addEventListener('click', this._boundHandlers.back);
        }

        const relatedChips = this.container?.querySelectorAll('.related-item-chip');
        relatedChips?.forEach(chip => {
            const kw = chip.dataset.keyword;
            if (kw) {
                this._boundHandlers[`related-${kw}`] = () => {
                    this._keyword = kw;
                    store.setState('currentItemKeyword', kw);
                    this._render();
                    this._loadItem(kw);
                };
                chip.addEventListener('click', this._boundHandlers[`related-${kw}`]);
            }
        });
    }
}

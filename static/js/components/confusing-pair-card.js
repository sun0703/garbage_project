/**
 * 易错物品对比卡片组件 (ConfusingPairCard)
 *
 * 职责：展示一对易混淆垃圾的左右对比卡片；
 *       每侧显示物品名称、正确分类、原因和投放建议；
 *       中间显示关键区分点。
 */

import { escapeHtml } from '../utils/escape.js';

const CATEGORY_COLORS = {
    0: { bg: '#8B4513', light: '#FFF3E0', label: '厨余垃圾' },
    1: { bg: '#007bff', light: '#E3F2FD', label: '可回收物' },
    2: { bg: '#333333', light: '#F5F5F5', label: '其他垃圾' },
    3: { bg: '#dc3545', light: '#FFEBEE', label: '有害垃圾' },
};

export class ConfusingPairCard {
    _container = null;
    _boundHandlers = {};

    render(pair) {
        const wrapper = document.createElement('div');
        wrapper.className = 'confusing-pair-card';
        wrapper.dataset.pairId = pair.id;

        const catA = CATEGORY_COLORS[pair.item_a.category_id] || {};
        const catB = CATEGORY_COLORS[pair.item_b.category_id] || {};

        const freqBadge = this._buildFreqBadge(pair.frequency);
        const sceneBadge = pair.scene ? `<span class="pair-scene-badge">📍 ${escapeHtml(pair.scene)}</span>` : '';

        wrapper.innerHTML = `
            <div class="pair-header">
                <div class="pair-badges">
                    ${freqBadge}
                    ${sceneBadge}
                </div>
                <span class="pair-id">#${pair.id}</span>
            </div>

            <div class="pair-compare">
                <div class="pair-side pair-side-a" style="border-color: ${catA.bg}; background: ${catA.light}">
                    <div class="pair-side-cat" style="background: ${catA.bg}">
                        ${escapeHtml(pair.item_a.category)}
                    </div>
                    <h4 class="pair-side-name">${escapeHtml(pair.item_a.name)}</h4>
                    <p class="pair-side-reason">${escapeHtml(pair.item_a.reason)}</p>
                    <p class="pair-side-tip">💡 ${escapeHtml(pair.item_a.tip)}</p>
                </div>

                <div class="pair-vs">
                    <div class="pair-vs-line"></div>
                    <span class="pair-vs-text">VS</span>
                    <div class="pair-vs-line"></div>
                </div>

                <div class="pair-side pair-side-b" style="border-color: ${catB.bg}; background: ${catB.light}">
                    <div class="pair-side-cat" style="background: ${catB.bg}">
                        ${escapeHtml(pair.item_b.category)}
                    </div>
                    <h4 class="pair-side-name">${escapeHtml(pair.item_b.name)}</h4>
                    <p class="pair-side-reason">${escapeHtml(pair.item_b.reason)}</p>
                    <p class="pair-side-tip">💡 ${escapeHtml(pair.item_b.tip)}</p>
                </div>
            </div>

            <div class="pair-key-diff">
                <span class="key-diff-icon">🔑</span>
                <span>关键区分：<strong>${escapeHtml(pair.key_difference)}</strong></span>
            </div>
        `;

        this._container = wrapper;
        return wrapper;
    }

    _buildFreqBadge(frequency) {
        const config = {
            critical: { cls: 'freq-critical', text: '极易混淆' },
            high: { cls: 'freq-high', text: '常混淆' },
            medium: { cls: 'freq-medium', text: '易混淆' },
            low: { cls: 'freq-low', text: '偶尔混淆' },
        };
        const c = config[frequency] || config.medium;
        return `<span class="pair-freq-badge ${c.cls}">${c.text}</span>`;
    }

    renderCompact(pair) {
        const catA = CATEGORY_COLORS[pair.item_a.category_id] || {};
        const catB = CATEGORY_COLORS[pair.item_b.category_id] || {};

        const wrapper = document.createElement('div');
        wrapper.className = 'confusing-pair-compact';
        wrapper.dataset.pairId = pair.id;

        wrapper.innerHTML = `
            <div class="compact-item" style="border-left: 3px solid ${catA.bg}">
                <span class="compact-name">${escapeHtml(pair.item_a.name)}</span>
                <span class="compact-cat" style="color: ${catA.bg}">${escapeHtml(pair.item_a.category)}</span>
            </div>
            <span class="compact-vs">vs</span>
            <div class="compact-item" style="border-left: 3px solid ${catB.bg}">
                <span class="compact-name">${escapeHtml(pair.item_b.name)}</span>
                <span class="compact-cat" style="color: ${catB.bg}">${escapeHtml(pair.item_b.category)}</span>
            </div>
            <div class="compact-diff">🔑 ${escapeHtml(pair.key_difference)}</div>
        `;

        return wrapper;
    }

    destroy() {
        this._container = null;
        this._boundHandlers = {};
    }
}

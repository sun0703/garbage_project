/**
 * 分类指南页视图（Guide Page）— 阶段二增强版
 *
 * 职责：展示4类垃圾分类的标准说明卡片（厨余/可回收/其他/有害）；
 *       每个卡片包含：类别名称、颜色标识、图标、定义、投放注意事项、
 *       常见示例、校园特有物品、容易分错的物品；
 *       支持折叠/展开交互；
 *       数据来源优先 /api/guide/standard 接口，失败时使用本地静态数据兜底。
 * 容器：#page-guide
 */

import { api } from '../api.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { escapeHtml } from '../utils/escape.js';
import { ConfusingPairCard } from '../components/confusing-pair-card.js';

const FALLBACK_CATEGORIES = [
    {
        id: 0, name: '厨余垃圾', color: '#8B4513',
        bg_gradient: 'linear-gradient(135deg, #8B4513, #A0522D)',
        icon: '🍎', bin_color: '棕色/绿色',
        definition: '易腐烂的食物残渣和生物质废弃物',
        disposal_tips: ['投放前沥干水分', '去除食品包装物', '大骨头属于其他垃圾'],
        common_items: [
            {name: '剩饭剩菜', tip: '沥干水分后投放'},
            {name: '果皮果核', tip: '苹果核、香蕉皮等'},
            {name: '蛋壳', tip: '鸡蛋壳、鸭蛋壳'},
            {name: '茶叶渣', tip: '沥干水分'}
        ],
        campus_special_items: [
            {name: '食堂剩饭剩菜', tip: '沥干汤汁后投入厨余垃圾桶'},
            {name: '奶茶中的珍珠', tip: '珍珠倒入厨余，杯子归其他垃圾'}
        ],
        wrong_items: [
            {name: '大骨头', correct_category: '其他垃圾', reason: '难以分解'},
            {name: '用过的纸巾', correct_category: '其他垃圾', reason: '已污染'}
        ]
    },
    {
        id: 1, name: '可回收物', color: '#007bff',
        bg_gradient: 'linear-gradient(135deg, #007bff, #0056b3)',
        icon: '♻️', bin_color: '蓝色',
        definition: '可循环利用的废弃物，具有再生利用价值',
        disposal_tips: ['投放前清空内容物', '纸箱压扁折叠', '塑料瓶压扁投放'],
        common_items: [
            {name: '塑料瓶', tip: '清空冲洗，压扁投放'},
            {name: '废纸类', tip: '报纸、书本、纸箱'},
            {name: '易拉罐', tip: '踩扁后投放'},
            {name: '旧衣物', tip: '清洗打包后投放'}
        ],
        campus_special_items: [
            {name: '快递纸箱', tip: '拆开压扁后投入蓝色可回收桶'},
            {name: '教材书本', tip: '保持整洁，可捐赠或投入可回收桶'}
        ],
        wrong_items: [
            {name: '用过的纸巾', correct_category: '其他垃圾', reason: '已污染'},
            {name: '外卖餐盒(有残留)', correct_category: '其他垃圾', reason: '被食物污染'}
        ]
    },
    {
        id: 2, name: '其他垃圾', color: '#333333',
        bg_gradient: 'linear-gradient(135deg, #555555, #333333)',
        icon: '🗑️', bin_color: '灰色/黑色',
        definition: '除以上三类之外的其他生活废弃物',
        disposal_tips: ['尽量沥干水分', '尖锐物品用纸包裹', '大件垃圾投放至指定收集点'],
        common_items: [
            {name: '用过的纸巾', tip: '卫生纸、面巾纸'},
            {name: '烟蒂', tip: '熄灭后投放'},
            {name: '陶瓷碎片', tip: '包裹后投放'},
            {name: '大骨头', tip: '猪腿骨、牛骨'}
        ],
        campus_special_items: [
            {name: '外卖餐盒(有残留)', tip: '清空食物残渣后投入灰色桶'},
            {name: '奶茶杯(有残留)', tip: '珍珠倒入厨余，杯子归其他垃圾'}
        ],
        wrong_items: [
            {name: '废电池', correct_category: '有害垃圾', reason: '含重金属'},
            {name: '果皮', correct_category: '厨余垃圾', reason: '食物残渣'}
        ]
    },
    {
        id: 3, name: '有害垃圾', color: '#dc3545',
        bg_gradient: 'linear-gradient(135deg, #dc3545, #c82333)',
        icon: '☠️', bin_color: '红色',
        definition: '对人体健康或自然环境造成直接或潜在危害的废弃物',
        disposal_tips: ['投放时轻放防止破损', '废灯管保持完整', '过期药品连同包装投放'],
        common_items: [
            {name: '废电池', tip: '充电电池、纽扣电池'},
            {name: '废灯管', tip: '荧光灯管、节能灯'},
            {name: '过期药品', tip: '药品及包装'},
            {name: '水银温度计', tip: '小心轻放'}
        ],
        campus_special_items: [
            {name: '充电宝/锂电池', tip: '投入红色有害垃圾桶，防止短路'},
            {name: '废墨盒/硒鼓', tip: '打印机耗材投入有害垃圾桶'}
        ],
        wrong_items: [
            {name: 'LED灯', correct_category: '可回收物', reason: '不含汞'},
            {name: '普通玻璃瓶', correct_category: '可回收物', reason: '不含害物质'}
        ]
    }
];

export class GuidePage {
    container = null;
    _categories = [];
    _confusingPairs = [];
    _loading = false;
    _expandedCardId = null;
    _pairCard = null;
    _boundHandlers = {};

    async init() {
        this.container = document.getElementById('page-guide');
        if (!this.container) {
            console.error('[GuidePage] 容器 #page-guide 不存在');
            return;
        }

        this._pairCard = new ConfusingPairCard();
        this._render();
        try {
            await Promise.all([
                this._loadCategories(),
                this._loadConfusingPairs()
            ]);
        } catch (err) {
            console.error('[GuidePage] 初始化失败:', err);
        }

        console.log('[GuidePage] 分类指南页初始化完成');
    }

    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }

        this.container = null;
        this._categories = [];
        this._confusingPairs = [];
        this._expandedCardId = null;
        if (this._pairCard) {
            this._pairCard.destroy();
            this._pairCard = null;
        }
        this._boundHandlers = {};

        console.log('[GuidePage] 分类指南页已销毁');
    }

    _render() {
        this.container.innerHTML = `
            <div class="guide-nav">
                <button class="nav-back-btn" id="guideBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="guide-nav-title">分类指南</h2>
            </div>

            <div class="guide-intro card">
                <div class="guide-intro-icon">
                    <svg viewBox="0 0 24 24" width="32" height="32" fill="#2D9B5E">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                    </svg>
                </div>
                <div class="guide-intro-text">
                    <h3>校园垃圾分类标准</h3>
                    <p>了解四类垃圾的正确分类方法，共同维护校园环境</p>
                </div>
            </div>

            <div id="categoryCardsContainer" class="category-cards-list">
                <div class="guide-loading-skeleton">
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                </div>
            </div>

            <div class="confusing-section">
                <div class="confusing-section-header">
                    <h3 class="confusing-section-title">
                        <span>⚠️</span> 易混淆物品对比
                    </h3>
                    <div class="confusing-filter-bar">
                        <button class="confusing-filter-btn active" data-filter="all">全部</button>
                        <button class="confusing-filter-btn" data-filter="critical">极易混淆</button>
                        <button class="confusing-filter-btn" data-filter="high">常混淆</button>
                        <button class="confusing-filter-btn" data-filter="medium">易混淆</button>
                    </div>
                </div>
                <div id="confusingPairsContainer" class="confusing-pairs-list">
                    <div class="guide-loading-skeleton">
                        <div class="skeleton-card"></div>
                        <div class="skeleton-card"></div>
                    </div>
                </div>
            </div>

            <div class="guide-footer">
                <p>数据来源：国家标准《生活垃圾分类标志》GB/T 19095-2019</p>
            </div>
        `;
    }

    async _loadCategories() {
        this._loading = true;

        try {
            const response = await api.getGuideStandard();

            if (response.categories && response.categories.length > 0) {
                this._categories = response.categories;
                console.log(`[GuidePage] 从 API 加载了 ${this._categories.length} 条分类数据`);
            } else {
                this._categories = FALLBACK_CATEGORIES;
                console.log('[GuidePage] API 返回空数据，使用本地兜底');
            }
        } catch (error) {
            console.warn('[GuidePage] API 加载失败，使用本地兜底数据:', error);
            this._categories = FALLBACK_CATEGORIES;
        } finally {
            this._loading = false;
            this._renderCategoryCards();
        }
    }

    _renderCategoryCards() {
        const container = document.getElementById('categoryCardsContainer');
        if (!container) return;

        if (!this._categories || this._categories.length === 0) {
            container.innerHTML = `<div class="card empty-categories"><p>暂无分类数据</p></div>`;
            return;
        }

        const cardsHTML = this._categories.map((category, index) => {
            return this._buildCategoryCard(category, index);
        }).join('');

        container.innerHTML = cardsHTML;
        this._bindEvents();
    }

    _buildCategoryCard(category, index) {
        const color = category.color || category.color_code || '#666';
        const bgGradient = category.bg_gradient || `linear-gradient(135deg, ${color}, ${color}dd)`;
        const icon = category.icon || '';
        const name = escapeHtml(category.name || '未命名分类');
        const definition = escapeHtml(category.definition || category.description || '');
        const binColor = escapeHtml(category.bin_color || category.binColor || '');
        const disposalTips = category.disposal_tips || [];
        const commonItems = category.common_items || category.examples || [];
        const campusItems = category.campus_special_items || [];
        const wrongItems = category.wrong_items || [];

        const tipsHTML = disposalTips.map(tip => `
            <li class="disposal-tip-item">
                <span class="tip-bullet">•</span>
                <span>${escapeHtml(tip)}</span>
            </li>
        `).join('');

        const commonItemsHTML = commonItems.map(item => {
            const itemName = item.name || item;
            const itemTip = item.tip || item.desc || '';
            return `
                <li class="guide-item-chip" title="${escapeHtml(itemTip)}">
                    ${escapeHtml(itemName)}
                </li>
            `;
        }).join('');

        const campusItemsHTML = campusItems.map(item => `
            <li class="campus-item">
                <span class="campus-item-name">${escapeHtml(item.name)}</span>
                <span class="campus-item-tip">${escapeHtml(item.tip)}</span>
            </li>
        `).join('');

        const wrongItemsHTML = wrongItems.map(item => `
            <li class="wrong-item">
                <span class="wrong-item-name">${escapeHtml(item.name)}</span>
                <span class="wrong-item-arrow">→</span>
                <span class="wrong-item-correct">${escapeHtml(item.correct_category)}</span>
                <span class="wrong-item-reason">${escapeHtml(item.reason)}</span>
            </li>
        `).join('');

        return `
            <div class="card category-card"
                 data-category-id="${category.id}"
                 style="animation-delay: ${index * 0.1}s">

                <div class="category-card-header" style="background: ${bgGradient}" data-toggle="${category.id}">
                    <div class="category-header-info">
                        <span class="category-icon">${icon}</span>
                        <div class="category-title-group">
                            <h3 class="category-name">${name}</h3>
                            ${binColor ? `<span class="category-bin-label">🪣 ${binColor}桶</span>` : ''}
                        </div>
                    </div>
                    <div class="category-expand-icon">
                        <svg viewBox="0 0 24 24" width="20" height="20" stroke="white" stroke-width="2" fill="none">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                    </div>
                </div>

                <div class="category-card-body" id="cardBody-${category.id}">
                    ${definition ? `<p class="category-definition">${definition}</p>` : ''}

                    ${disposalTips.length > 0 ? `
                    <div class="guide-section">
                        <h4 class="guide-section-title">
                            <span class="section-icon">📋</span>投放注意事项
                        </h4>
                        <ul class="disposal-tips-list">${tipsHTML}</ul>
                    </div>
                    ` : ''}

                    ${commonItems.length > 0 ? `
                    <div class="guide-section">
                        <h4 class="guide-section-title">
                            <span class="section-icon">📦</span>常见物品
                        </h4>
                        <div class="guide-items-chips">${commonItemsHTML}</div>
                    </div>
                    ` : ''}

                    ${campusItems.length > 0 ? `
                    <div class="guide-section">
                        <h4 class="guide-section-title">
                            <span class="section-icon">🏫</span>校园特有物品
                        </h4>
                        <ul class="campus-items-list">${campusItemsHTML}</ul>
                    </div>
                    ` : ''}

                    ${wrongItems.length > 0 ? `
                    <div class="guide-section">
                        <h4 class="guide-section-title">
                            <span class="section-icon">⚠️</span>容易分错的物品
                        </h4>
                        <ul class="wrong-items-list">${wrongItemsHTML}</ul>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    _bindEvents() {
        const backBtn = document.getElementById('guideBackBtn');
        if (backBtn) {
            this._boundHandlers.back = () => { window.location.hash = '#/'; };
            backBtn.addEventListener('click', this._boundHandlers.back);
        }

        const headers = this.container?.querySelectorAll('.category-card-header[data-toggle]');
        headers?.forEach(header => {
            const categoryId = header.dataset.toggle;
            this._boundHandlers[`toggle-${categoryId}`] = () => this._toggleCard(categoryId);
            header.addEventListener('click', this._boundHandlers[`toggle-${categoryId}`]);
        });
    }

    _toggleCard(categoryId) {
        const card = this.container?.querySelector(`.category-card[data-category-id="${categoryId}"]`);
        const body = document.getElementById(`cardBody-${categoryId}`);
        if (!card || !body) return;

        const isExpanded = card.classList.contains('expanded');

        if (isExpanded) {
            card.classList.remove('expanded');
            body.style.maxHeight = '0';
            body.style.opacity = '0';
        } else {
            card.classList.add('expanded');
            body.style.maxHeight = body.scrollHeight + 'px';
            body.style.opacity = '1';
        }
    }

    async _loadConfusingPairs(frequency = '') {
        try {
            const response = await api.getConfusingPairs(35, frequency);
            if (response.pairs && response.pairs.length > 0) {
                this._confusingPairs = response.pairs;
            }
        } catch (error) {
            console.warn('[GuidePage] 易混淆数据加载失败:', error);
            this._confusingPairs = [];
        } finally {
            this._renderConfusingPairs();
        }
    }

    _renderConfusingPairs() {
        const container = document.getElementById('confusingPairsContainer');
        if (!container) return;

        if (!this._confusingPairs || this._confusingPairs.length === 0) {
            container.innerHTML = `<div class="card empty-categories"><p>暂无易混淆数据</p></div>`;
            return;
        }

        container.innerHTML = '';

        this._confusingPairs.forEach(pair => {
            if (!this._pairCard) return;
            const cardEl = this._pairCard.render(pair);
            container.appendChild(cardEl);
        });

        this._bindFilterEvents();
    }

    _bindFilterEvents() {
        const filterBtns = this.container?.querySelectorAll('.confusing-filter-btn');
        filterBtns?.forEach(btn => {
            const filter = btn.dataset.filter;
            this._boundHandlers[`filter-${filter}`] = (e) => {
                this.container?.querySelectorAll('.confusing-filter-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                const freq = filter === 'all' ? '' : filter;
                this._loadConfusingPairs(freq);
            };
            btn.addEventListener('click', this._boundHandlers[`filter-${filter}`]);
        });
    }
}

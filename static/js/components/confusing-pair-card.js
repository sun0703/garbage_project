/**
 * 易错对比卡片组件 - ConfusingPairCard
 *
 * 功能说明：
 * - 左右对比展示两个易混淆物品的分类差异
 * - 包含：物品名称、分类标签、分类原因、关键区别标识
 * - 支持 VS 对比视觉强化（中间分隔线 + 动画）
 * - 频率标签（高/中/低频易错场景）
 * - 场景标签（食堂/宿舍/教室等）
 * - 丰富的入场动画和交互反馈
 * - 支持展开/收起详情模式
 *
 * 数据来源：confusing_pairs.json 或 /api/guide/confusing 接口
 *
 * @class ConfusingPairCard
 * @example
 * import { ConfusingPairCard } from './confusing-pair-card.js';
 * const card = new ConfusingPairCard();
 * const el = card.render('#container');
 * card.update({
 *     id: 'cp001',
 *     item_a: { name: '奶茶杯（干净）', category: '可回收物', reason: '...' },
 *     item_b: { name: '奶茶杯（残留）', category: '其他垃圾', reason: '...' },
 *     key_difference: '是否清洗干净',
 *     frequency: 'high',
 *     scene: '食堂/奶茶店'
 * });
 */

/** 分类ID到样式配置的映射表 */
const CATEGORY_STYLE_MAP = {
    '厨余垃圾': {
        id: 0,
        color: '#8B4513',
        bgLight: 'rgba(139, 69, 19, 0.08)',
        bgGradient: 'linear-gradient(135deg, #8B4513, #A0522D)',
        icon: '🍎'
    },
    '可回收物': {
        id: 1,
        color: '#007bff',
        bgLight: 'rgba(0, 123, 255, 0.08)',
        bgGradient: 'linear-gradient(135deg, #007bff, #0056b3)',
        icon: '♻️'
    },
    '其他垃圾': {
        id: 2,
        color: '#333333',
        bgLight: 'rgba(51, 51, 51, 0.06)',
        bgGradient: 'linear-gradient(135deg, #555555, #333333)',
        icon: '🗑️'
    },
    '有害垃圾': {
        id: 3,
        color: '#dc3545',
        bgLight: 'rgba(220, 53, 69, 0.08)',
        bgGradient: 'linear-gradient(135deg, #dc3545, #c82333)',
        icon: '☠️'
    }
};

/** 频率配置映射 */
const FREQUENCY_CONFIG = {
    high: { label: '高频易错', color: '#E74C3C', bg: 'rgba(231, 76, 60, 0.08)', icon: '🔥' },
    medium: { label: '中等频率', color: '#F39C12', bg: 'rgba(243, 156, 18, 0.08)', icon: '⚡' },
    low: { label: '较少出错', color: '#27AE60', bg: 'rgba(39, 174, 96, 0.08)', icon: '✓' }
};

export class ConfusingPairCard {
    /**
     * 构造函数 - 初始化对比卡片配置
     * @param {Object} [options={}] - 配置选项
     * @param {boolean} [options.showAnimation=true] - 是否启用入场动画
     * @param {boolean} [options.expandable=true] - 是否支持展开/收起
     * @param {boolean} [options.showScene=true] - 是否显示场景标签
     */
    constructor(options = {}) {
        /** @type {boolean} 是否启用动画效果 */
        this._showAnimation = options.showAnimation !== false;

        /** @type {boolean} 是否支持展开/收起 */
        this._expandable = options.expandable !== false;

        /** @type {boolean} 是否显示场景标签 */
        this._showScene = options.showScene !== false;

        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;

        /** @type {Object|null} 当前显示的数据快照 */
        this._currentData = null;

        /** @type {boolean} 当前展开状态 */
        this._expanded = false;
    }

    /**
     * 渲染对比卡片到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} 卡片根元素引用
     */
    render(containerSelector) {
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[ConfusingPairCard] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        /* 创建卡片根元素 */
        const cardEl = document.createElement('div');
        cardEl.className = 'confusing-pair-card';
        cardEl.setAttribute('role', 'article');
        cardEl.setAttribute('aria-label', '易错物品对比');

        /* ========== 卡片内部结构 ========== */
        cardEl.innerHTML = `
            <!-- 顶部区域：标题 + 频率标签 -->
            <div class="cpc-header">
                <div class="cpc-title-row">
                    <span class="cpc-icon">⚖️</span>
                    <h3 class="cpc-title" id="cpcTitle">易错对比</h3>
                </div>
                <div class="cpc-meta">
                    <span class="cpc-frequency" id="cpcFrequency"></span>
                    <span class="cpc-scene" id="cpcScene"></span>
                </div>
            </div>

            <!-- 关键区别提示条 -->
            <div class="cpc-key-diff" id="cpcKeyDiff">
                <span class="cpc-key-diff-icon">💡</span>
                <span class="cpc-key-diff-label">关键区别：</span>
                <span class="cpc-key-diff-text" id="cpcKeyDiffText">--</span>
            </div>

            <!-- VS 对比区域：左右两张卡片 -->
            <div class="cpc-compare-area">
                <!-- 物品A卡片（左侧） -->
                <div class="cpc-item cpc-item--left" id="cpcItemA">
                    <div class="cpc-item-label">物品 A</div>
                    <div class="cpc-item-name" id="cpcItemAName">--</div>
                    <div class="cpc-item-category" id="cpcItemACategory"></div>
                    <div class="cpc-item-reason" id="cpcItemAReason">
                        <span class="cpc-reason-icon">📝</span>
                        <span class="cpc-reason-text" id="cpcItemAReasonText">--</span>
                    </div>
                </div>

                <!-- VS 分隔符 -->
                <div class="cpc-vs-divider">
                    <div class="cpc-vs-circle">
                        <span class="cpc-vs-text">VS</span>
                    </div>
                    <div class="cpc-vs-line cpc-vs-line--top"></div>
                    <div class="cpc-vs-line cpc-vs-vs-line--bottom"></div>
                </div>

                <!-- 物品B卡片（右侧） -->
                <div class="cpc-item cpc-item--right" id="cpcItemB">
                    <div class="cpc-item-label">物品 B</div>
                    <div class="cpc-item-name" id="cpcItemBName">--</div>
                    <div class="cpc-item-category" id="cpcItemBCategory"></div>
                    <div class="cpc-item-reason" id="cpcItemBReason">
                        <span class="cpc-reason-icon">📝</span>
                        <span class="cpc-reason-text" id="cpcItemBReasonText">--</span>
                    </div>
                </div>
            </div>

            <!-- 展开按钮（可选） -->
            <button class="cpc-expand-btn" id="cpcExpandBtn" style="display:none;">
                <span class="cpc-expand-text">查看详情</span>
                <svg class="cpc-expand-icon" viewBox="0 0 24 24" width="16" height="16">
                    <polyline points="6 9 12 15 18 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </button>

            <!-- 展开详情区域 -->
            <div class="cpc-detail" id="cpcDetail" style="display:none;">
                <div class="cpc-detail-content" id="cpcDetailContent"></div>
            </div>
        `;

        /* 将卡片插入容器 */
        container.appendChild(cardEl);

        /* 缓存根元素引用 */
        this._element = cardEl;

        /* 绑定事件 */
        this._bindEvents();

        return cardEl;
    }

    /**
     * 更新卡片数据并触发渲染
     * 核心方法：接收易错对数据并渲染完整对比卡片
     *
     * @param {Object} pairData - 易错对数据
     * @param {string} pairData.id - 唯一标识（如 'cp001'）
     * @param {Object} pairData.item_a - 物品A数据
     * @param {string} pairData.item_a.name - 物品A名称
     * @param {string} pairData.item_a.category - 物品A分类
     * @param {string} pairData.item_a.reason - 物品A分类原因
     * @param {Object} pairData.item_b - 物品B数据
     * @param {string} pairData.item_b.name - 物品B名称
     * @param {string} pairData.item_b.category - 物品B分类
     * @param {string} pairData.item_b.reason - 物品B分类原因
     * @param {string} pairData.key_difference - 关键区别描述
     * @param {string} [pairData.frequency='medium'] - 出错频率（high/medium/low）
     * @param {string} [pairData.scene=''] - 常见场景
     * @returns {void}
     */
    update(pairData) {
        if (!this._element || !pairData) {
            console.warn('[ConfusingPairCard] update调用失败：组件未渲染或数据为空');
            return;
        }

        /* 保存数据快照 */
        this._currentData = pairData;

        /* 解构数据并设置默认值 */
        const {
            id = '',
            item_a = {},
            item_b = {},
            key_difference = '',
            frequency = 'medium',
            scene = ''
        } = pairData;

        /* ======== 1. 更新标题 ======== */
        this._updateTitle(item_a, item_b);

        /* ======== 2. 更新元信息（频率+场景）======== */
        this._updateMeta(frequency, scene);

        /* ======== 3. 更新关键区别 ======== */
        this._updateKeyDiff(key_difference);

        /* ======== 4. 更新物品A卡片 ======== */
        this._updateItem('A', item_a);

        /* ======== 5. 更新物品B卡片 ======== */
        this._updateItem('B', item_b);

        /* ======== 6. 触发入场动画 ======== */
        if (this._showAnimation) {
            this._playEnterAnimation();
        }
    }

    /**
     * 切换展开/收起状态
     * @returns {void}
     */
    toggleExpand() {
        if (!this._expandable || !this._element) return;

        this._expanded = !this._expanded;
        const detailEl = this._element.querySelector('#cpcDetail');
        const btnEl = this._element.querySelector('#cpcExpandBtn');
        const iconEl = this._element.querySelector('.cpc-expand-icon');

        if (detailEl && btnEl) {
            if (this._expanded) {
                detailEl.style.display = '';
                btnEl.classList.add('cpc-expand-btn--active');
                iconEl.style.transform = 'rotate(180deg)';
                btnEl.querySelector('.cpc-expand-text').textContent = '收起详情';
            } else {
                detailEl.style.display = 'none';
                btnEl.classList.remove('cpc-expand-btn--active');
                iconEl.style.transform = '';
                btnEl.querySelector('.cpc-expand-text').textContent = '查看详情';
            }
        }
    }

    /**
     * 显示卡片
     * @returns {void}
     */
    show() {
        if (this._element) {
            this._element.classList.add('cpc--visible');
            if (this._showAnimation) {
                this._playEnterAnimation();
            }
        }
    }

    /**
     * 隐藏卡片
     * @returns {void}
     */
    hide() {
        if (this._element) {
            this._element.classList.remove('cpc--visible');
        }
    }

    /**
     * 重置卡片到初始状态
     * @returns {void}
     */
    reset() {
        if (!this._element) return;

        this._setText('#cpcTitle', '易错对比');
        this._setText('#cpcFrequency', '');
        this._setText('#cpcScene', '');
        this._setText('#cpcKeyDiffText', '--');
        this._setText('#cpcItemAName', '--');
        this._setText('#cpcItemBName', '--');
        this._setHtml('#cpcItemACategory', '');
        this._setHtml('#cpcItemBCategory', '');
        this._setText('#cpcItemAReasonText', '--');
        this._setText('#cpcItemBReasonText', '--');

        this._element.classList.remove('cpc--animated', 'cpc--visible');
        this._currentData = null;
        this._expanded = false;
    }

    /**
     * 销毁组件 - 移除DOM和事件绑定
     * @returns {void}
     */
    destroy() {
        if (this._element && this._element.parentNode) {
            this._element.parentNode.removeChild(this._element);
        }
        this._element = null;
        this._currentData = null;
    }

    // ==================== 私有方法：各区域更新逻辑 ====================

    /**
     * 更新标题区域
     * @private
     * @param {Object} itemA - 物品A数据
     * @param {Object} itemB - 物品B数据
     * @returns {void}
     */
    _updateTitle(itemA, itemB) {
        const nameA = itemA?.name || '物品A';
        const nameB = itemB?.name || '物品B';
        this._setText('#cpcTitle', `${nameA} vs ${nameB}`);
    }

    /**
     * 更新元信息区域（频率标签 + 场景标签）
     * @private
     * @param {string} frequency - 频率等级
     * @param {string} scene - 场景描述
     * @returns {void}
     */
    _updateMeta(frequency, scene) {
        /* 更新频率标签 */
        const freqEl = this._element.querySelector('#cpcFrequency');
        if (freqEl && frequency && FREQUENCY_CONFIG[frequency]) {
            const config = FREQUENCY_CONFIG[frequency];
            freqEl.textContent = `${config.icon} ${config.label}`;
            freqEl.style.color = config.color;
            freqEl.style.background = config.bg;
            freqEl.style.display = '';
        } else if (freqEl) {
            freqEl.style.display = 'none';
        }

        /* 更新场景标签 */
        const sceneEl = this._element.querySelector('#cpcScene');
        if (sceneEl && scene && this._showScene) {
            sceneEl.textContent = `📍 ${scene}`;
            sceneEl.style.display = '';
        } else if (sceneEl) {
            sceneEl.style.display = 'none';
        }
    }

    /**
     * 更新关键区别提示条
     * @private
     * @param {string} keyDiff - 关键区别文本
     * @returns {void}
     */
    _updateKeyDiff(keyDiff) {
        this._setText('#cpcKeyDiffText', keyDiff || '--');

        const container = this._element.querySelector('#cpcKeyDiff');
        if (container) {
            container.style.display = keyDiff ? '' : 'none';
        }
    }

    /**
     * 更新单个物品卡片内容
     * @private
     * @param {'A'|'B'} side - 左侧(A)或右侧(B)
     * @param {Object} item - 物品数据
     * @returns {void}
     */
    _updateItem(side, item) {
        const prefix = `#cpcItem${side}`;
        const name = item?.name || '--';
        const category = item?.category || '未知分类';
        const reason = item?.reason || '--';

        /* 更新名称 */
        this._setText(`${prefix}Name`, name);

        /* 更新分类标签 */
        const catEl = this._element.querySelector(`${prefix}Category`);
        if (catEl) {
            const styleConfig = CATEGORY_STYLE_MAP[category] || CATEGORY_STYLE_MAP['其他垃圾'];
            catEl.innerHTML = `
                <span class="cpc-cat-dot" style="background:${styleConfig.color}"></span>
                <span class="cpc-cat-name">${this._escapeHtml(category)}</span>
            `;
            catEl.style.color = styleConfig.color;
            catEl.style.background = styleConfig.bgLight;
            catEl.style.borderColor = `${styleConfig.color}33`;
        }

        /* 更新原因说明 */
        this._setText(`${prefix}ReasonText`, reason);
    }

    /**
     * 播放入场动画组合（交错滑入 + VS弹跳）
     * @private
     * @returns {void}
     */
    _playEnterAnimation() {
        const card = this._element;

        /* 先移除动画类确保可以重新触发 */
        card.classList.remove('cpc--animated');

        /* 强制重排 */
        void card.offsetHeight;

        /* 添加动画类 */
        card.classList.add('cpc--animated');

        /* 动画结束后移除类（允许下次再次触发） */
        card.addEventListener('animationend', function handler() {
            card.removeEventListener('animationend', handler);
        }, { once: true });
    }

    /**
     * 绑定交互事件
     * @private
     * @returns {void}
     */
    _bindEvents() {
        if (!this._element) return;

        /* 展开按钮点击事件 */
        const expandBtn = this._element.querySelector('#cpcExpandBtn');
        if (expandBtn) {
            expandBtn.addEventListener('click', () => this.toggleExpand());
        }

        /* 可选：点击卡片区域也触发展开 */
        if (this._expandable) {
            const compareArea = this._element.querySelector('.cpc-compare-area');
            if (compareArea) {
                compareArea.addEventListener('click', () => this.toggleExpand());
                compareArea.style.cursor = 'pointer';
            }
        }
    }

    // ==================== DOM工具方法 ====================

    /**
     * 设置元素文本内容（安全转义）
     * @private
     * @param {string} selector - CSS选择器
     * @param {string} text - 文本内容
     * @returns {void}
     */
    _setText(selector, text) {
        const el = this._element.querySelector(selector);
        if (el) el.textContent = text;
    }

    /**
     * 设置元素HTML内容
     * @private
     * @param {string} selector - CSS选择器
     * @param {string} html - HTML字符串
     * @returns {void}
     */
    _setHtml(selector, html) {
        const el = this._element.querySelector(selector);
        if (el) el.innerHTML = html;
    }

    /**
     * HTML转义（防止XSS注入）
     * @private
     * @param {string} str - 原始字符串
     * @returns {string} 转义后的安全字符串
     */
    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

/* ========== 组件内联样式 ========== */
const CONFUSING_PAIR_CARD_STYLES = `
/* ======== ConfusingPairCard 易错对比卡片样式 ======== */

/* 根容器 */
.confusing-pair-card {
    background: var(--bg-card, rgba(255, 255, 255, 0.92));
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);

    border-radius: var(--radius-lg, 20px);
    padding: 20px;
    margin-bottom: 20px;

    box-shadow:
        0 4px 24px rgba(45, 155, 94, 0.08),
        0 1px 4px rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.7);

    opacity: 0;
    transform: translateY(16px);
    transition: opacity 0.4s ease, transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 可见状态 */
.confusing-pair-card.cpc--visible {
    opacity: 1;
    transform: translateY(0);
}

/* 入场动画激活态 */
.confusing-pair-card.cpc--animated {
    animation: cpcSlideInUp 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes cpcSlideInUp {
    0% {
        opacity: 0;
        transform: translateY(20px) scale(0.98);
    }
    60% {
        opacity: 1;
        transform: translateY(-3px) scale(1.005);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

/* ========== 头部区域 ========== */
.cpc-header {
    margin-bottom: 16px;
}

.cpc-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

.cpc-icon {
    font-size: 22px;
    line-height: 1;
}

.cpc-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary, #1A1A2E);
    margin: 0;
    line-height: 1.3;
}

/* 元信息行（频率 + 场景） */
.cpc-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.cpc-frequency,
.cpc-scene {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: var(--radius-full, 100px);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.cpc-scene {
    background: rgba(45, 155, 94, 0.06);
    color: var(--primary, #2D9B5E);
}

/* ========== 关键区别提示条 ========== */
.cpc-key-diff {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    margin-bottom: 16px;
    border-radius: var(--radius-sm, 10px);
    background: linear-gradient(
        135deg,
        rgba(255, 159, 67, 0.06),
        rgba(255, 190, 118, 0.08)
    );
    border-left: 3px solid var(--accent, #FF9F43);
}

.cpc-key-diff-icon {
    font-size: 16px;
    line-height: 1;
    flex-shrink: 0;
}

.cpc-key-diff-label {
    font-size: 12px;
    font-weight: 700;
    color: var(--accent, #FF9F43);
    white-space: nowrap;
}

.cpc-key-diff-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary, #1A1A2E);
    line-height: 1.4;
}

/* ========== VS 对比区域（核心布局）========== */
.cpc-compare-area {
    display: flex;
    align-items: stretch;
    gap: 0;
    position: relative;
}

/* 单个物品卡片 */
.cpc-item {
    flex: 1;
    padding: 16px;
    border-radius: var(--radius-md, 14px);
    background: linear-gradient(
        145deg,
        rgba(255, 255, 255, 0.8),
        rgba(250, 250, 252, 0.6)
    );
    border: 1.5px solid rgba(0, 0, 0, 0.06);

    transition:
        transform 0.25s ease,
        box-shadow 0.25s ease,
        border-color 0.25s ease;
}

.cpc-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    border-color: rgba(45, 155, 94, 0.2);
}

/* 左侧卡片入场动画延迟 */
.cpc-item--left {
    animation: cpcItemSlideLeft 0.5s ease-out both;
    animation-delay: 0.15s;
}

/* 右侧卡片入场动画延迟 */
.cpc-item--right {
    animation: cpcItemSlideRight 0.5s ease-out both;
    animation-delay: 0.25s;
}

@keyframes cpcItemSlideLeft {
    from {
        opacity: 0;
        transform: translateX(-20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes cpcItemSlideRight {
    from {
        opacity: 0;
        transform: translateX(20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

/* 物品标签（A/B） */
.cpc-item-label {
    display: inline-block;
    padding: 2px 10px;
    border-radius: var(--radius-full, 100px);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
    background: rgba(45, 155, 94, 0.08);
    color: var(--primary, #2D9B5E);
}

/* 物品名称 */
.cpc-item-name {
    font-size: 16px;
    font-weight: 800;
    color: var(--text-primary, #1A1A2E);
    line-height: 1.3;
    margin-bottom: 10px;
    word-break: break-word;
}

/* 分类标签容器 */
.cpc-item-category {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: var(--radius-full, 100px);
    font-size: 12px;
    font-weight: 700;
    border: 1.5px solid transparent;
    margin-bottom: 12px;
    transition: background 0.2s ease;
}

/* 分类圆点指示器 */
.cpc-cat-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* 分类名称文字 */
.cpc-cat-name {
    line-height: 1;
}

/* 原因说明区域 */
.cpc-item-reason {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.02);
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--text-secondary, #5A6776);
}

.cpc-reason-icon {
    flex-shrink: 0;
    font-size: 13px;
    line-height: 1.5;
}

.cpc-reason-text {
    flex: 1;
    word-break: break-word;
}

/* ========== VS 分隔符（视觉焦点）========== */
.cpc-vs-divider {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 50px;
    flex-shrink: 0;
    position: relative;
    padding: 0 4px;
}

/* VS圆形背景 */
.cpc-vs-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #E74C3C, #C0392B);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow:
        0 3px 12px rgba(231, 76, 60, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
    z-index: 2;
    animation: cpcVsPulse 2.5s ease-in-out infinite;
}

@keyframes cpcVsPulse {
    0%, 100% {
        box-shadow:
            0 3px 12px rgba(231, 76, 60, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }
    50% {
        box-shadow:
            0 3px 20px rgba(231, 76, 60, 0.45),
            0 0 0 6px rgba(231, 76, 60, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }
}

.cpc-vs-text {
    font-size: 13px;
    font-weight: 900;
    letter-spacing: 0.03em;
    font-style: italic;
}

/* VS上下连接线 */
.cpc-vs-line {
    width: 2px;
    flex: 1;
    background: linear-gradient(
        180deg,
        rgba(231, 76, 60, 0.25),
        rgba(231, 76, 60, 0.08)
    );
    border-radius: 1px;
}

/* ========== 展开按钮 ========== */
.cpc-expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 10px;
    margin-top: 14px;
    border: none;
    border-radius: var(--radius-sm, 10px);
    background: rgba(45, 155, 94, 0.05);
    color: var(--primary, #2D9B5E);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;

    transition:
        background 0.2s ease,
        color 0.2s ease;
}

.cpc-expand-btn:hover {
    background: rgba(45, 155, 94, 0.10);
}

.cpc-expand-btn:active {
    transform: scale(0.98);
}

.cpc-expand-btn--active {
    background: rgba(45, 155, 94, 0.10);
}

.cpc-expand-icon {
    transition: transform 0.3s ease;
}

/* ========== 展开详情区域 ========== */
.cpc-detail {
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.35s ease, padding 0.35s ease;
}

.cpc-detail[style*="display: block"],
.cpc-detail[style*=""] {
    max-height: 300px;
    padding-top: 12px;
}

.cpc-detail-content {
    padding: 14px;
    border-radius: var(--radius-sm, 10px);
    background: rgba(45, 155, 94, 0.03);
    border: 1px dashed rgba(45, 155, 94, 0.15);
    font-size: 13px;
    line-height: 1.65;
    color: var(--text-secondary, #5A6776);
}

/* ========== 响应式适配 ========== */

/* 小屏手机（宽度 ≤ 375px） */
@media screen and (max-width: 375px) {
    .confusing-pair-card {
        padding: 14px;
        border-radius: 16px;
    }

    .cpc-title {
        font-size: 15px;
    }

    .cpc-item {
        padding: 12px;
    }

    .cpc-item-name {
        font-size: 14px;
    }

    .cpc-vs-divider {
        width: 36px;
    }

    .cpc-vs-circle {
        width: 34px;
        height: 34px;
    }

    .cpc-vs-text {
        font-size: 11px;
    }

    .cpc-item-reason {
        font-size: 11.5px;
        padding: 8px 10px;
    }
}

/* 中等屏幕平板（宽度 ≥ 480px） */
@media screen and (min-width: 480px) {
    .confusing-pair-card {
        padding: 24px;
    }

    .cpc-item {
        padding: 20px;
    }

    .cpc-item-name {
        font-size: 17px;
    }

    .cpc-vs-circle {
        width: 46px;
        height: 46px;
    }

    .cpc-vs-text {
        font-size: 14px;
    }
}

/* ========== 减弱动效偏好支持 ========== */
@media (prefers-reduced-motion: reduce) {
    .confusing-pair-card,
    .cpc-item,
    .cpc-vs-circle {
        animation-duration: 0.01ms !important;
        transition-duration: 0.2s !important;
    }

    .cpc-vs-circle {
        animation: none;
    }
}
`;

// 自动注入样式到文档（避免重复注入）
if (!document.getElementById('confusing-pair-card-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'confusing-pair-card-styles';
    styleSheet.textContent = CONFUSING_PAIR_CARD_STYLES;
    document.head.appendChild(styleSheet);
}

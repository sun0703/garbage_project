/**
 * 分类指南页视图（Guide Page）
 *
 * 职责：展示4类垃圾分类的标准说明卡片（厨余/可回收/其他/有害）；
 *       每个卡片包含类别名称、颜色标识、图标、描述、常见示例列表；
 *       包含易错物品对比专题区域（F-2.4）；
 *       数据来源优先 API 接口，失败时使用本地静态数据兜底。
 * 容器：#page-guide
 */

// ==================== 模块依赖导入 ====================
import { api } from '../api.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { ConfusingPairCard } from '../components/confusing-pair-card.js';

// ==================== 本地静态兜底数据（API 不可用时使用） ====================

/** 四类垃圾标准分类数据 */
const FALLBACK_CATEGORIES = [
    {
        id: 0,
        name: '厨余垃圾',
        color: '#8B4513',
        bgGradient: 'linear-gradient(135deg, #8B4513, #A0522D)',
        icon: '🍎',
        description: '易腐烂的食物残渣和生物质废弃物',
        binColor: '棕色/绿色',
        tip: '投放时需沥干水分，去除包装后投入专用垃圾桶',
        examples: [
            { name: '剩饭剩菜', desc: '餐后剩余食物' },
            { name: '果皮果核', desc: '水果外皮及果核' },
            { name: '茶叶渣', desc: '泡过的茶叶残渣' },
            { name: '蛋壳', desc: '鸡蛋、鸭蛋等蛋壳' },
            { name: '过期食品', desc: '已过保质期的食物' }
        ]
    },
    {
        id: 1,
        name: '可回收物',
        color: '#007bff',
        bgGradient: 'linear-gradient(135deg, #007bff, #0056b3)',
        icon: '♻️',
        description: '可循环利用的废弃物，具有再生利用价值',
        binColor: '蓝色',
        tip: '投放前请清空内容物，简单清洗并压扁以节省空间',
        examples: [
            { name: '塑料瓶', desc: '饮料瓶、矿泉水瓶等' },
            { name: '废纸类', desc: '报纸、书本、纸箱等' },
            { name: '金属罐', desc: '易拉罐、铁罐、铝罐等' },
            { name: '玻璃制品', desc: '玻璃瓶、镜子碎片等' },
            { name: '旧衣物', desc: '干净的可再利用纺织品' }
        ]
    },
    {
        id: 2,
        name: '其他垃圾',
        color: '#333333',
        bgGradient: 'linear-gradient(135deg, #555555, #333333)',
        icon: '🗑️',
        description: '除以上三类之外的其他生活废弃物',
        binColor: '灰色/黑色',
        tip: '难以归类的物品通常属于此类，注意不要混入有害物质',
        examples: [
            { name: '污染纸张', desc: '已沾染油污的纸巾' },
            { name: '陶瓷碎片', desc: '破碎的碗碟瓷片' },
            { name: '烟蒂', desc: '吸烟后的烟头' },
            { name: '尘土', desc: '清扫的灰尘垃圾' },
            { name: '一次性餐具', desc: '污染的一次性筷子/饭盒' }
        ]
    },
    {
        id: 3,
        name: '有害垃圾',
        color: '#dc3545',
        bgGradient: 'linear-gradient(135deg, #dc3545, #c82333)',
        icon: '☠️',
        description: '对人体健康或自然环境造成直接或潜在危害的废弃物',
        binColor: '红色',
        tip: '需特殊安全处理，请勿与其他垃圾混合投放',
        examples: [
            { name: '废电池', desc: '各类充电电池、干电池' },
            { name: '废灯管', desc: '荧光灯管、节能灯管' },
            { name: '过期药品', desc: '已过期的药物及包装' },
            { name: '油漆桶', desc: '废弃的油漆涂料容器' },
            { name: '杀虫剂', desc: '废弃的农药/杀虫剂瓶子' }
        ]
    }
];

// ==================== 页面类定义 ====================
export class GuidePage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 分类数据（来自 API 或本地兜底） */
    _categories = [];

    /** 易错对比数据（来自 JSON 或 API） */
    _confusingPairs = [];

    /** 易错卡片组件实例集合 */
    _confusingCardInstances = [];

    /** 是否正在加载数据 */
    _loading = false;

    /** 绑定的事件处理器引用集合 */
    _boundHandlers = {};

    /**
     * 初始化分类指南页
     * 加载分类数据并渲染4类标准说明卡片 + 易错对比专题
     */
    init() {
        this.container = document.getElementById('page-guide');
        if (!this.container) {
            console.error('[GuidePage] 容器 #page-guide 不存在');
            return;
        }

        /* 渲染页面骨架（含易错专题区域） */
        this._render();
        /* 加载分类数据 */
        this._loadCategories();
        /* 加载易错对比数据 */
        this._loadConfusingPairs();

        console.log('[GuidePage] 分类指南页初始化完成');
    }

    /**
     * 销毁分类指南页
     * 清空容器、释放引用（含易错卡片组件）
     */
    destroy() {
        /* 销毁所有易错对比卡片实例 */
        this._confusingCardInstances.forEach(card => card.destroy());
        this._confusingCardInstances = [];

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 释放引用 */
        this.container = null;
        this._categories = [];
        this._confusingPairs = [];
        this._loading = false;
        this._boundHandlers = {};

        console.log('[GuidePage] 分类指南页已销毁');
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染页面 HTML 骨架结构
     * 包含标题区 + 分类卡片容器 + 易错对比专题区域
     * @private
     */
    _render() {
        this.container.innerHTML = `
            <!-- 导航栏 -->
            <div class="guide-nav">
                <button class="nav-back-btn" id="guideBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="guide-nav-title">分类指南</h2>
            </div>

            <!-- 页面简介 -->
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

            <!-- 分类卡片列表容器（动态填充） -->
            <div id="categoryCardsContainer" class="category-cards-list">
                <!-- 加载骨架屏 -->
                <div class="guide-loading-skeleton">
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                </div>
            </div>

            <!-- ========== 易错物品对比专题区域（F-2.4）========== -->
            <section class="confusing-section" id="confusingSection">
                <!-- 区域头部 -->
                <div class="confusing-section-header">
                    <div class="confusing-section-title-row">
                        <span class="confusing-section-icon">🎯</span>
                        <h3 class="confusing-section-title">易错物品对比专题</h3>
                    </div>
                    <p class="confusing-section-desc">这些物品最容易分错，左右滑动查看详细区别</p>
                </div>

                <!-- 对比卡片列表容器（动态填充） -->
                <div id="confusingPairsContainer" class="confusing-pairs-list">
                    <!-- 加载占位 -->
                    <div class="confusing-loading-placeholder">
                        <div class="confusing-skeleton-card"></div>
                        <div class="confusing-skeleton-card"></div>
                    </div>
                </div>
            </section>

            <!-- 底部提示 -->
            <div class="guide-footer">
                <p>数据来源：国家标准《生活垃圾分类标志》GB/T 19095-2019</p>
            </div>
        `;
    }

    // ==================== 私有方法：数据加载 ====================

    /**
     * 加载分类数据
     * 优先从 API 获取，失败时使用本地静态数据兜底
     * @private
     */
    async _loadCategories() {
        this._loading = true;

        try {
            /* 尝试从 API 获取最新分类数据 */
            const response = await api.getCategories();

            if (response.categories && response.categories.length > 0) {
                /* 使用 API 返回的数据 */
                this._categories = response.categories;
                console.log(`[GuidePage] 从 API 加载了 ${this._categories.length} 条分类数据`);
            } else {
                /* API 返回空数组，使用本地数据 */
                this._categories = FALLBACK_CATEGORIES;
                console.log('[GuidePage] API 返回空数据，使用本地兜底');
            }

        } catch (error) {
            /* API 请求失败，使用本地静态数据兜底 */
            console.warn('[GuidePage] API 加载失败，使用本地兜底数据:', error);
            this._categories = FALLBACK_CATEGORIES;

        } finally {
            this._loading = false;
            /* 渲染分类卡片 */
            this._renderCategoryCards();
        }
    }

    /**
     * 加载易错对比数据
     * 优先从 API 获取，失败时加载本地 JSON 文件兜底
     * @private
     */
    async _loadConfusingPairs() {
        try {
            /* 尝试从 API 获取易错数据（阶段二接口预留） */
            const response = await api.getConfusingPairs?.();

            if (response?.pairs && response.pairs.length > 0) {
                this._confusingPairs = response.pairs;
                console.log(`[GuidePage] 从 API 加载了 ${this._confusingPairs.length} 组易错数据`);
            } else {
                /* 加载本地 JSON 数据 */
                await this._loadLocalConfusingPairs();
            }
        } catch (error) {
            /* API 不可用，使用本地 JSON 兜底 */
            console.warn('[GuidePage] 易错API不可用，加载本地数据:', error);
            await this._loadLocalConfusingPairs();
        }

        /* 渲染易错对比卡片 */
        this._renderConfusingPairs();
    }

    /**
     * 加载本地 confusing-pairs.json 静态数据
     * @private
     */
    async _loadLocalConfusingPairs() {
        try {
            const res = await fetch('./data/confusing-pairs.json');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this._confusingPairs = data.pairs || [];
            console.log(`[GuidePage] 从本地JSON加载了 ${this._confusingPairs.length} 组易错数据`);
        } catch (error) {
            console.error('[GuidePage] 本地易错数据加载失败:', error);
            this._confusingPairs = [];
        }
    }

    // ==================== 私有方法：卡片渲染 ====================

    /**
     * 渲染所有分类说明卡片
     * 每个卡片包含：颜色标识 + 类别名称 + 图标 + 描述 + 常见示例列表
     * @private
     */
    _renderCategoryCards() {
        const container = document.getElementById('categoryCardsContainer');
        if (!container) return;

        /* 如果没有数据则显示提示 */
        if (!this._categories || this._categories.length === 0) {
            container.innerHTML = `
                <div class="card empty-categories">
                    <p>暂无分类数据</p>
                </div>
            `;
            return;
        }

        /* 为每个分类生成卡片 HTML */
        const cardsHTML = this._categories.map((category, index) => {
            return this._buildCategoryCard(category, index);
        }).join('');

        container.innerHTML = cardsHTML;

        /* 绑定返回按钮事件 */
        this._bindEvents();
    }

    /**
     * 渲染易错对比卡片列表
     * 使用 ConfusingPairCard 组件实例化每一条易错对数据
     * @private
     */
    _renderConfusingPairs() {
        const container = document.getElementById('confusingPairsContainer');
        if (!container) return;

        /* 清理旧实例 */
        this._confusingCardInstances.forEach(card => card.destroy());
        this._confusingCardInstances = [];

        /* 无数据时显示空状态 */
        if (!this._confusingPairs || this._confusingPairs.length === 0) {
            container.innerHTML = `
                <div class="card empty-confusing">
                    <p>暂无易错对比数据</p>
                </div>
            `;
            return;
        }

        /* 按频率排序：高频优先展示 */
        const sortedPairs = [...this._confusingPairs].sort((a, b) => {
            const order = { high: 0, medium: 1, low: 2 };
            return (order[a.frequency] || 1) - (order[b.frequency] || 1);
        });

        /* 清空容器并渲染卡片 */
        container.innerHTML = '';

        /* 取前8组展示（避免首屏过长，其余可滚动查看） */
        const displayPairs = sortedPairs.slice(0, 8);

        displayPairs.forEach((pairData, index) => {
            /* 创建组件实例 */
            const card = new ConfusingPairCard({
                showAnimation: true,
                expandable: true,
                showScene: true
            });

            /* 渲染到容器 */
            const cardEl = card.render(container);
            if (cardEl) {
                /* 设置动画延迟实现交错入场效果 */
                cardEl.style.animationDelay = `${index * 0.1}s`;
                /* 填充数据 */
                card.update(pairData);
                /* 保存实例引用 */
                this._confusingCardInstances.push(card);
            }
        });

        /* 数据量提示 */
        if (this._confusingPairs.length > 8) {
            const hintEl = document.createElement('div');
            hintEl.className = 'confusing-more-hint';
            hintEl.textContent = `共 ${this._confusingPairs.length} 组易错对比，已展示高频前8组`;
            container.appendChild(hintEl);
        }
    }

    /**
     * 构建单个分类说明卡片的 HTML
     *
     * @param {Object} category - 分类数据对象
     * @param {number} index - 分类索引（用于动画延迟）
     * @returns {string} 卡片 HTML 字符串
     * @private
     */
    _buildCategoryCard(category, index) {
        const color = category.color || '#666';
        const bgGradient = category.bgGradient || `linear-gradient(135deg, ${color}, ${color}dd)`;
        const icon = category.icon || '';
        const name = category.name || '未命名分类';
        const description = category.description || '';
        const binColor = category.binColor || '';
        const tip = category.tip || '';
        const examples = category.examples || [];

        /* 构建示例列表项 */
        const examplesHTML = examples.map(ex => `
            <li class="example-item">
                <span class="example-name">${ex.name}</span>
                <span class="example-desc">${ex.desc}</span>
            </li>
        `).join('');

        return `
            <div class="card category-card"
                 data-category-id="${category.id}"
                 style="animation-delay: ${index * 0.1}s">

                <!-- 卡片头部：颜色条 + 类别信息 -->
                <div class="category-card-header" style="background: ${bgGradient}">
                    <div class="category-color-bar" style="background: ${color}"></div>
                    <div class="category-header-info">
                        <span class="category-icon">${icon}</span>
                        <div class="category-title-group">
                            <h3 class="category-name">${name}</h3>
                            ${binColor ? `<span class="category-bin-label">🪣 ${binColor}桶</span>` : ''}
                        </div>
                    </div>
                </div>

                <!-- 卡片主体：描述 + 示例 -->
                <div class="category-card-body">
                    <!-- 类别描述 -->
                    <p class="category-description">${description}</p>

                    ${tip ? `
                    <!-- 投放提示 -->
                    <div class="category-tip-box">
                        <span class="tip-icon">💡</span>
                        <span class="tip-text">${tip}</span>
                    </div>
                    ` : ''}

                    <!-- 常见示例列表 -->
                    ${examples.length > 0 ? `
                    <div class="category-examples">
                        <h4 class="examples-title">常见示例</h4>
                        <ul class="examples-list">
                            ${examplesHTML}
                        </ul>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定交互事件
     * @private
     */
    _bindEvents() {
        /* 返回按钮 — 回到首页 */
        const backBtn = document.getElementById('guideBackBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }

        /* 可扩展：点击卡片展开详情（阶段二实现） */
        const cards = this.container?.querySelectorAll('.category-card');
        cards?.forEach(card => {
            card.addEventListener('click', () => {
                /* 阶段一仅做视觉反馈，阶段二可扩展为跳转详情 */
                card.classList.toggle('expanded');
            });
        });
    }
}

/**
 * 底部Tab栏组件 - TabBar
 * 
 * 功能说明：
 * - 固定底部显示，包含4个主要导航Tab
 * - 支持激活状态高亮和切换动画
 * - 点击自动切换路由（Hash路由）
 * - 仅移动端显示，PC端（>=768px）自动隐藏
 * - 适配安全区域（iPhone底部横条等）
 * 
 * @class TabBar
 * @example
 * import { TabBar } from './tab-bar.js';
 * const tabBar = new TabBar();
 * tabBar.render('#tabBar');
 * tabBar.setActiveTab(2); // 切换到指南页
 */

export class TabBar {
    /**
     * 构造函数 - 初始化Tab栏配置和数据
     * @param {Object} [options={}] - 配置选项
     * @param {number} [options.activeIndex=0] - 默认激活的Tab索引
     * @param {Function} [options.onTabChange] - Tab切换回调函数
     */
    constructor(options = {}) {
        /** @type {number} 当前激活的Tab索引 */
        this._activeIndex = options.activeIndex || 0;
        
        /** @type {Function|null} Tab切换回调 */
        this._onTabChange = options.onTabChange || null;
        
        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;
        
        /** @type {HTMLElement[]} 各Tab项元素引用数组 */
        this._tabItems = [];

        /**
         * Tab配置数据 - 定义4个主导航项
         * 每项包含：图标SVG、标签文字、路由路径
         * @type {Array<{icon: string, label: string, route: string}>}
         */
        this._tabs = [
            {
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>`,
                label: '首页',
                route: '#/home'
            },
            {
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>`,
                label: '搜索',
                route: '#/search'
            },
            {
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`,
                label: '地图',
                route: '#/map'
            },
            {
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>`,
                label: '社区',
                route: '#/community'
            },
            {
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>`,
                label: '我的',
                route: '#/profile'
            }
        ];
    }

    /**
     * 渲染Tab栏到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} Tab栏根元素引用
     */
    render(containerSelector) {
        // 获取容器元素
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[TabBar] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        // 创建Tab栏根元素
        const tabEl = document.createElement('nav');
        tabEl.className = 'tab-bar';
        tabEl.setAttribute('role', 'tablist');
        tabEl.setAttribute('aria-label', '底部导航');

        /* ========== 生成Tab项HTML ========== */
        const tabsHtml = this._tabs.map((tab, index) => `
            <button 
                class="tab-bar__item ${index === this._activeIndex ? 'tab-bar__item--active' : ''}"
                role="tab"
                aria-selected="${index === this._activeIndex}"
                aria-label="${tab.label}"
                data-index="${index}"
                data-route="${tab.route}"
            >
                <!-- 图标容器 -->
                <span class="tab-bar__icon">${tab.icon}</span>
                <!-- 标签文字 -->
                <span class="tab-bar__label">${tab.label}</span>
                <!-- 激活指示器（小圆点/短横线） -->
                <span class="tab-bar__indicator"></span>
            </button>
        `).join('');

        tabEl.innerHTML = tabsHtml;

        // 将Tab栏插入容器
        container.appendChild(tabEl);

        // 缓存根元素引用
        this._element = tabEl;

        // 获取所有Tab项并缓存
        this._tabItems = Array.from(tabEl.querySelectorAll('.tab-bar__item'));

        // 为每个Tab绑定点击事件
        this._bindTabEvents();

        return tabEl;
    }

    /**
     * 外部设置当前激活的Tab
     * 常用于路由变化时同步UI状态
     * @param {number} index - 目标Tab索引（0-3）
     * @returns {void}
     */
    setActiveTab(index) {
        // 边界检查：限制在有效范围内
        const safeIndex = Math.max(0, Math.min(index, this._tabs.length - 1));
        
        if (safeIndex === this._activeIndex) return; // 无变化则跳过

        const prevIndex = this._activeIndex;
        this._activeIndex = safeIndex;

        // 更新DOM样式
        this._updateTabStyles(prevIndex, safeIndex);
        
        // 触发回调通知外部
        this._emitChange(safeIndex);
    }

    /**
     * 获取当前激活的Tab索引
     * @returns {number} 当前激活索引
     */
    getActiveTab() {
        return this._activeIndex;
    }

    /**
     * 根据路由路径设置激活Tab
     * 便于路由监听器调用
     * @param {string} route - Hash路由路径（如 '#/search'）
     * @returns {boolean} 是否成功匹配并切换
     */
    setActiveByRoute(route) {
        const index = this._tabs.findIndex(tab => tab.route === route);
        if (index !== -1) {
            this.setActiveTab(index);
            return true;
        }
        return false;
    }

    /**
     * 绑定所有Tab点击事件
     * @private
     * @returns {void}
     */
    _bindTabEvents() {
        this._tabItems.forEach((item, index) => {
            item.addEventListener('click', () => {
                this._handleTabClick(index);
            });

            // 触摸反馈：按下时添加active效果
            item.addEventListener('touchstart', () => {
                item.classList.add('tab-bar__item--pressed');
            }, { passive: true });
            
            item.addEventListener('touchend', () => {
                item.classList.remove('tab-bar__item--pressed');
            }, { passive: true });
            
            item.addEventListener('touchcancel', () => {
                item.classList.remove('tab-bar__item--pressed');
            }, { passive: true });
        });
    }

    /**
     * 处理单个Tab点击事件
     * @private
     * @param {number} clickedIndex - 被点击的Tab索引
     * @returns {void}
     */
    _handleTabClick(clickedIndex) {
        if (clickedIndex === this._activeIndex) return; // 重复点击忽略

        const prevIndex = this._activeIndex;
        this._activeIndex = clickedIndex;

        // 更新视觉样式
        this._updateTabStyles(prevIndex, clickedIndex);

        // 执行路由跳转
        const targetRoute = this._tabs[clickedIndex].route;
        window.location.hash = targetRoute;

        // 触发变更事件
        this._emitChange(clickedIndex);
    }

    /**
     * 更新Tab项的视觉样式（激活态切换）
     * @private
     * @param {number} prevIndex - 之前的激活索引
     * @param {number} newIndex - 新的激活索引
     * @returns {void}
     */
    _updateTabStyles(prevIndex, newIndex) {
        // 移除旧激活态
        if (this._tabItems[prevIndex]) {
            this._tabItems[prevIndex].classList.remove('tab-bar__item--active');
            this._tabItems[prevIndex].setAttribute('aria-selected', 'false');
        }
        
        // 添加新激活态
        if (this._tabItems[newIndex]) {
            this._tabItems[newIndex].classList.add('tab-bar__item--active');
            this._tabItems[newIndex].setAttribute('aria-selected', 'true');
        }
    }

    /**
     * 触发Tab切换事件
     * @private
     * @param {number} newIndex - 当前激活索引
     * @returns {void}
     */
    _emitChange(newIndex) {
        // 调用外部回调
        if (typeof this._onTabChange === 'function') {
            this._onTabChange(newIndex, this._tabs[newIndex]);
        }

        // 触发DOM自定义事件（支持事件委托）
        if (this._element) {
            this._element.dispatchEvent(new CustomEvent('tab:change', {
                bubbles: true,
                detail: {
                    index: newIndex,
                    route: this._tabs[newIndex].route,
                    label: this._tabs[newIndex].label
                }
            }));
        }
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
        this._tabItems = [];
    }
}

/* ========== 组件内联样式 ========== */
const TAB_BAR_STYLES = `
/* ======== TabBar 底部导航栏样式 ======== */
.tab-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 64px;
    z-index: 100;
    
    /* 毛玻璃背景效果 */
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    /* 顶部边框分隔线 */
    border-top: 1px solid rgba(45, 155, 94, 0.10);
    
    /* 弹性布局：均分4个Tab */
    display: flex;
    align-items: center;
    justify-content: space-around;
    
    /* 底部安全区域适配（iPhone横条等） */
    padding-bottom: env(safe-area-inset-bottom, 0px);
    
    /* 仅移动端显示：PC端隐藏 */
    display: flex;
}

/* PC端（宽度>=768px）隐藏底部Tab栏 */
@media (min-width: 768px) {
    .tab-bar {
        display: none !important;
    }
}

/* 单个Tab项 */
.tab-bar__item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    
    padding: 6px 0;
    border: none;
    background: transparent;
    cursor: pointer;
    
    color: var(--text-muted, #95A0AA);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    
    position: relative;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
}

/* Tab图标 */
.tab-bar__icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    transition: transform 0.25s ease;
}

.tab-bar__icon svg {
    width: 22px;
    height: 22px;
    fill: currentColor;
    transition: fill 0.2s ease;
}

/* Tab文字标签 */
.tab-bar__label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.3px;
    line-height: 1.2;
    transition: all 0.2s ease;
}

/* 激活指示器（顶部短横线） */
.tab-bar__indicator {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%) scaleX(0);
    width: 20px;
    height: 3px;
    background: var(--primary, #2D9B5E);
    border-radius: 0 0 2px 2px;
    transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ========== 激活态样式 ========== */
.tab-bar__item--active {
    color: var(--primary, #2D9B5E);
}

.tab-bar__item--active .tab-bar__icon {
    transform: translateY(-1px);
}

.tab-bar__item--active .tab-bar__label {
    font-weight: 700;
    font-size: 10.5px;
}

.tab-bar__item--active .tab-bar__indicator {
    transform: translateX(-50%) scaleX(1);
}

/* ========== 交互态样式 ========== */
.tab-bar__item:hover:not(.tab-bar__item--active) {
    color: var(--text-secondary, #5A6776);
    background: rgba(45, 155, 94, 0.03);
}

.tab-bar__item:active,
.tab-bar__item--pressed {
    transform: scale(0.90);
    opacity: 0.75;
}

/* ========== 安全区域适配 ========== */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
    .tab-bar {
        height: calc(64px + env(safe-area-inset-bottom));
    }
}

/* ========== 减弱动效偏好支持 ========== */
@media (prefers-reduced-motion: reduce) {
    .tab-bar__item,
    .tab-bar__icon,
    .tab-bar__label,
    .tab-bar__indicator {
        transition-duration: 0.01ms !important;
    }
}
`;

// 自动注入样式到文档（避免重复注入）
if (!document.getElementById('tab-bar-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'tab-bar-styles';
    styleSheet.textContent = TAB_BAR_STYLES;
    document.head.appendChild(styleSheet);
}

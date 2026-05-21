/**
 * 顶部导航栏组件 - NavBar
 * 
 * 功能说明：
 * - 固定顶部显示，带毛玻璃效果
 * - 左侧回收图标 + 标题文字
 * - 右侧可选历史入口按钮
 * - 支持动态修改标题（如识别结果页显示物品名）
 * - 点击Logo区域返回首页
 * 
 * @class NavBar
 * @example
 * import { NavBar } from './nav-bar.js';
 * const navBar = new NavBar();
 * navBar.render('#navBar');
 * navBar.set_title('塑料瓶 - 识别结果');
 */

export class NavBar {
    /**
     * 构造函数 - 初始化导航栏配置
     * @param {Object} [options={}] - 配置选项
     * @param {string} [options.title='校园垃圾分类'] - 默认标题文字
     * @param {boolean} [options.showHistoryBtn=true] - 是否显示历史按钮
     * @param {Function} [options.onHistoryClick] - 历史按钮点击回调
     */
    constructor(options = {}) {
        /** @type {string} 当前标题 */
        this._title = options.title || '校园垃圾分类';
        
        /** @type {boolean} 是否显示历史按钮 */
        this._showHistoryBtn = options.showHistoryBtn !== false;
        
        /** @type {Function|null} 历史按钮点击回调 */
        this._onHistoryClick = options.onHistoryClick || null;
        
        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;
        
        /** @type {HTMLElement|null} 标题元素引用 */
        this._titleElement = null;
    }

    /**
     * 渲染导航栏到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} 导航栏根元素引用
     */
    render(containerSelector) {
        // 获取容器元素
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[NavBar] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        // 创建导航栏根元素
        const navEl = document.createElement('nav');
        navEl.className = 'nav-bar';
        navEl.setAttribute('role', 'navigation');
        navEl.setAttribute('aria-label', '主导航');

        /* ========== 导航栏内部结构 ========== */
        navEl.innerHTML = `
            <!-- 左侧：Logo + 标题区域 -->
            <div class="nav-bar__left" id="navLogoArea">
                <!-- 回收图标 SVG -->
                <div class="nav-bar__logo">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                    </svg>
                </div>
                <!-- 标题文字 -->
                <span class="nav-bar__title" id="navTitle">${this._escapeHtml(this._title)}</span>
            </div>

            <!-- 右侧：操作按钮区域 -->
            <div class="nav-bar__right">
                ${this._showHistoryBtn ? `
                <!-- 历史记录入口按钮 -->
                <button class="nav-bar__btn" id="navHistoryBtn" aria-label="查看历史记录" title="历史记录">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13 3a9 9 0 0 0-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0 0 13 21a9 9 0 0 0 0-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/>
                    </svg>
                </button>
                ` : ''}
            </div>
        `;

        // 将导航栏插入容器
        container.appendChild(navEl);

        // 缓存DOM引用
        this._element = navEl;
        this._titleElement = navEl.querySelector('#navTitle');

        // 绑定事件：点击Logo返回首页
        const logoArea = navEl.querySelector('#navLogoArea');
        logoArea.addEventListener('click', () => this._handleLogoClick());
        logoArea.style.cursor = 'pointer';

        // 绑定事件：历史按钮点击
        if (this._showHistoryBtn) {
            const historyBtn = navEl.querySelector('#navHistoryBtn');
            historyBtn.addEventListener('click', () => this._handleHistoryClick());
        }

        return navEl;
    }

    /**
     * 动态修改导航栏标题
     * 常用于识别结果页显示当前物品名称
     * @param {string} newTitle - 新的标题文字
     * @returns {void}
     */
    set_title(newTitle) {
        this._title = newTitle || '校园垃圾分类';
        
        if (this._titleElement) {
            this._titleElement.textContent = this._title;
            
            // 添加标题切换动画效果
            this._titleElement.style.animation = 'none';
            // 触发重排以重启动画
            void this._titleElement.offsetHeight;
            this._titleElement.style.animation = 'navTitleFade 0.3s ease';
        }
    }

    /**
     * 获取当前标题
     * @returns {string} 当前标题文字
     */
    get_title() {
        return this._title;
    }

    /**
     * 显示或隐藏历史按钮
     * @param {boolean} visible - 是否显示
     * @returns {void}
     */
    set_history_visible(visible) {
        if (this._element) {
            const btn = this._element.querySelector('#navHistoryBtn');
            if (btn) {
                btn.style.display = visible ? '' : 'none';
            }
        }
    }

    /**
     * 处理Logo点击事件 - 导航到首页
     * @private
     * @returns {void}
     */
    _handleLogoClick() {
        // 使用Hash路由跳转到首页
        window.location.hash = '#/home';
        
        // 同时触发自定义事件，便于外部监听
        this._element.dispatchEvent(new CustomEvent('nav:home', {
            bubbles: true,
            detail: { source: 'logo' }
        }));
    }

    /**
     * 处理历史按钮点击事件
     * @private
     * @returns {void}
     */
    _handleHistoryClick() {
        // 如果有外部回调则调用
        if (typeof this._onHistoryClick === 'function') {
            this._onHistoryClick();
        } else {
            // 默认行为：跳转到历史页面
            window.location.hash = '#/history';
        }

        // 触发自定义事件
        this._element.dispatchEvent(new CustomEvent('nav:history', {
            bubbles: true
        }));
    }

    /**
     * HTML转义 - 防止XSS注入
     * @private
     * @param {string} text - 需要转义的文本
     * @returns {string} 转义后的安全文本
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        this._titleElement = null;
    }
}

/* ========== 组件内联样式 ========== */
// 通过JavaScript注入组件专用样式，确保独立可用性
const NAV_BAR_STYLES = `
/* ======== NavBar 顶部导航栏样式 ======== */
.nav-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 56px;
    z-index: 100;
    
    /* 毛玻璃背景效果 */
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    /* 底部边框分隔线 */
    border-bottom: 1px solid rgba(45, 155, 94, 0.10);
    
    /* 弹性布局：左右分布 */
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    
    /* 平滑过渡动画 */
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 左侧区域：Logo + 标题 */
.nav-bar__left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0; /* 允许文本截断 */
}

/* Logo图标容器 */
.nav-bar__logo {
    width: 34px;
    height: 34px;
    background: linear-gradient(135deg, var(--primary, #2D9B5E), var(--primary-light, #3DB974));
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(45, 155, 94, 0.2);
    transition: transform 0.2s ease;
}

.nav-bar__logo:hover {
    transform: scale(1.05);
}

.nav-bar__logo svg {
    width: 20px;
    height: 20px;
    fill: white;
}

/* 标题文字 */
.nav-bar__title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary, #1A1A2E);
    letter-spacing: 0.3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
}

/* 标题切换动画 */
@keyframes navTitleFade {
    0% { opacity: 0.5; transform: translateX(-4px); }
    100% { opacity: 1; transform: translateX(0); }
}

/* 右侧操作区 */
.nav-bar__right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

/* 通用按钮样式 */
.nav-bar__btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-secondary, #5A6776);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.nav-bar__btn:hover {
    background: rgba(45, 155, 94, 0.08);
    color: var(--primary, #2D9B5E);
}

.nav-bar__btn:active {
    transform: scale(0.92);
    background: rgba(45, 155, 94, 0.12);
}

.nav-bar__btn svg {
    width: 20px;
    height: 20px;
    fill: currentColor;
}

/* 安全区域适配（刘海屏等） */
@supports (padding-top: env(safe-area-inset-top)) {
    .nav-bar {
        padding-top: env(safe-area-inset-top);
        height: calc(56px + env(safe-area-inset-top));
    }
}
`;

// 自动注入样式到文档（避免重复注入）
if (!document.getElementById('nav-bar-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'nav-bar-styles';
    styleSheet.textContent = NAV_BAR_STYLES;
    document.head.appendChild(styleSheet);
}

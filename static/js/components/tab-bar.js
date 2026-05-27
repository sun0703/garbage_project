/**
 * 底部Tab栏组件 - TabBar
 *
 * 功能说明：
 * - 固定底部显示，包含5个主要导航Tab
 * - 支持激活状态高亮和切换动画
 * - 点击自动切换路由（Hash路由）
 * - 仅移动端显示，PC端（>=768px）自动隐藏
 * - 适配安全区域（iPhone底部横条等）
 *
 * 继承自 BaseComponent，遵循标准化生命周期：
 * constructor → init() → render() → bindEvents() → afterInit()
 *
 * @class TabBar
 * @extends BaseComponent
 * @example
 * import { TabBar } from './tab-bar.js';
 *
 * // 新标准用法（推荐）
 * const tabBar = new TabBar({
 *   container: '#tabBar',
 *   props: { activeIndex: 0 },
 *   events: { tabChange: (index, tab) => console.log(index) }
 * });
 * tabBar.init();
 * tabBar.setActiveTab(2);
 *
 * // 向后兼容用法（仍支持）
 * const tabBar = new TabBar();
 * tabBar.render('#tabBar');
 */

import { BaseComponent } from './BaseComponent.js';

export class TabBar extends BaseComponent {
  /**
   * 构造函数 - 初始化Tab栏配置和数据
   * @param {Object} [options={}] - 配置选项
   * @param {HTMLElement|string} [options.container] - 挂载容器（用于init()方法）
   * @param {number} [options.activeIndex=0] - 默认激活的Tab索引
   * @param {Function} [options.onTabChange] - Tab切换回调函数
   */
  constructor(options = {}) {
    super({
      container: options.container,
      props: {
        onTabChange: options.onTabChange || null
      },
      state: {
        activeIndex: options.activeIndex || 0
      }
    });

    this._tabItems = [];

    /**
     * Tab配置数据 - 定义5个主导航项
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
   * 渲染Tab栏的DOM结构
   * 实现BaseComponent的抽象方法
   *
   * @returns {HTMLElement} Tab栏根元素引用
   */
  render() {
    const tabEl = document.createElement('nav');
    tabEl.className = 'tab-bar';
    tabEl.setAttribute('role', 'tablist');
    tabEl.setAttribute('aria-label', '底部导航');

    /* ========== 生成Tab项HTML ========== */
    const tabsHtml = this._tabs.map((tab, index) => `
            <button 
                class="tab-bar__item ${index === this.state.activeIndex ? 'tab-bar__item--active' : ''}"
                role="tab"
                aria-selected="${index === this.state.activeIndex}"
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

    return tabEl;
  }

  /**
   * 绑定所有Tab点击事件
   * 实现BaseComponent的可选重写方法
   *
   * @returns {void}
   */
  bindEvents() {
    if (!this.el) return;

    this._tabItems = Array.from(this.el.querySelectorAll('.tab-bar__item'));

    this._tabItems.forEach((item, index) => {
      this._bindEvent(item, 'click', () => {
        this._handleTabClick(index);
      });

      this._bindEvent(item, 'touchstart', () => {
        item.classList.add('tab-bar__item--pressed');
      }, { passive: true });

      this._bindEvent(item, 'touchend', () => {
        item.classList.remove('tab-bar__item--pressed');
      }, { passive: true });

      this._bindEvent(item, 'touchcancel', () => {
        item.classList.remove('tab-bar__item--pressed');
      }, { passive: true });
    });
  }

  /**
   * 向后兼容的渲染方法
   * 支持旧的调用方式：tabBar.render('#container')
   *
   * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
   * @returns {HTMLElement|null} Tab栏根元素引用
   */
  renderToContainer(containerSelector) {
    const container = typeof containerSelector === 'string'
      ? document.querySelector(containerSelector)
      : containerSelector;

    if (!container) {
      console.error('[TabBar] 渲染失败：未找到容器', containerSelector);
      return null;
    }

    this.options.container = container;
    return this.init().el;
  }

  /**
   * 外部设置当前激活的Tab
   * 常用于路由变化时同步UI状态
   * @param {number} index - 目标Tab索引（0-4）
   * @returns {void}
   */
  setActiveTab(index) {
    const safeIndex = Math.max(0, Math.min(index, this._tabs.length - 1));

    if (safeIndex === this.state.activeIndex) return;

    const prevIndex = this.state.activeIndex;
    this.state.activeIndex = safeIndex;

    this._updateTabStyles(prevIndex, safeIndex);

    this._emitChange(safeIndex);
  }

  /**
   * 获取当前激活的Tab索引
   * @returns {number} 当前激活索引
   */
  getActiveTab() {
    return this.state.activeIndex;
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
   * 处理单个Tab点击事件
   * @private
   * @param {number} clickedIndex - 被点击的Tab索引
   * @returns {void}
   */
  _handleTabClick(clickedIndex) {
    if (clickedIndex === this.state.activeIndex) return;

    const prevIndex = this.state.activeIndex;
    this.state.activeIndex = clickedIndex;

    this._updateTabStyles(prevIndex, clickedIndex);

    const targetRoute = this._tabs[clickedIndex].route;
    window.location.hash = targetRoute;

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
    if (this._tabItems[prevIndex]) {
      this._tabItems[prevIndex].classList.remove('tab-bar__item--active');
      this._tabItems[prevIndex].setAttribute('aria-selected', 'false');
    }

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
    if (typeof this.props.onTabChange === 'function') {
      this.props.onTabChange(newIndex, this._tabs[newIndex]);
    }

    if (this.el) {
      this.el.dispatchEvent(new CustomEvent('tab:change', {
        bubbles: true,
        detail: {
          index: newIndex,
          route: this._tabs[newIndex].route,
          label: this._tabs[newIndex].label
        }
      }));
    }
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
    
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    border-top: 1px solid rgba(45, 155, 94, 0.10);
    
    display: flex;
    align-items: center;
    justify-content: space-around;
    
    padding-bottom: env(safe-area-inset-bottom, 0px);
    
    display: flex;
}

@media (min-width: 768px) {
    .tab-bar {
        display: none !important;
    }
}

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

.tab-bar__label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.3px;
    line-height: 1.2;
    transition: all 0.2s ease;
}

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

.tab-bar__item:hover:not(.tab-bar__item--active) {
    color: var(--text-secondary, #5A6776);
    background: rgba(45, 155, 94, 0.03);
}

.tab-bar__item:active,
.tab-bar__item--pressed {
    transform: scale(0.90);
    opacity: 0.75;
}

@supports (padding-bottom: env(safe-area-inset-bottom)) {
    .tab-bar {
        height: calc(64px + env(safe-area-inset-bottom));
    }
}

@media (prefers-reduced-motion: reduce) {
    .tab-bar__item,
    .tab-bar__icon,
    .tab-bar__label,
    .tab-bar__indicator {
        transition-duration: 0.01ms !important;
    }
}
`;

if (!document.getElementById('tab-bar-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'tab-bar-styles';
    styleSheet.textContent = TAB_BAR_STYLES;
    document.head.appendChild(styleSheet);
}

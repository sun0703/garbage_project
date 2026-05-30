// 顶部导航栏 — 毛玻璃效果 + Logo + 历史入口

import { escapeHtml } from '../utils/escape.js';
import { BaseComponent } from './BaseComponent.js';

export class NavBar extends BaseComponent {
  /**
   * 构造函数 - 初始化导航栏配置
   * @param {Object} [options={}] - 配置选项
   * @param {HTMLElement|string} [options.container] - 挂载容器（用于init()方法）
   * @param {string} [options.title='垃圾分类'] - 默认标题文字
   * @param {boolean} [options.showHistoryBtn=true] - 是否显示历史按钮
   * @param {Function} [options.onHistoryClick] - 历史按钮点击回调
   */
  constructor(options = {}) {
    super({
      container: options.container,
      props: {
        title: options.title || '垃圾分类',
        showHistoryBtn: options.showHistoryBtn !== false,
        onHistoryClick: options.onHistoryClick || null
      },
      state: {}
    });

    this._titleElement = null;
  }

  /**
   * 渲染导航栏的DOM结构
   * 实现BaseComponent的抽象方法
   *
   * @returns {HTMLElement} 导航栏根元素引用
   */
  render() {
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
                <span class="nav-bar__title" id="navTitle">${escapeHtml(this.props.title)}</span>
            </div>

            <!-- 右侧：操作按钮区域 -->
            <div class="nav-bar__right">
                ${this.props.showHistoryBtn ? `
                <!-- 历史记录入口按钮 -->
                <button class="nav-bar__btn" id="navHistoryBtn" aria-label="查看历史记录" title="历史记录">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13 3a9 9 0 0 0-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0 0 13 21a9 9 0 0 0 0-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/>
                    </svg>
                </button>
                ` : ''}
            </div>
        `;

    return navEl;
  }

  /**
   * 绑定导航栏的所有事件监听器
   * 实现BaseComponent的可选重写方法
   *
   * @returns {void}
   */
  bindEvents() {
    if (!this.el) return;

    const logoArea = this.el.querySelector('#navLogoArea');
    if (logoArea) {
      logoArea.style.cursor = 'pointer';
      this._bindEvent(logoArea, 'click', () => this._goHome());
    }

    if (this.props.showHistoryBtn) {
      const historyBtn = this.el.querySelector('#navHistoryBtn');
      if (historyBtn) {
        this._bindEvent(historyBtn, 'click', () => this._openHistory());
      }
    }
  }

  /**
   * 初始化后钩子
   * 缓存DOM引用以便后续操作
   *
   * @returns {void}
   */
  afterInit() {
    if (this.el) {
      this._titleElement = this.el.querySelector('#navTitle');
    }
  }

  /**
   * 向后兼容的渲染方法
   * 支持旧的调用方式：navBar.render('#container')
   *
   * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
   * @returns {HTMLElement|null} 导航栏根元素引用
   */
  renderToContainer(containerSelector) {
    const container = typeof containerSelector === 'string'
      ? document.querySelector(containerSelector)
      : containerSelector;

    if (!container) {
      console.error('[NavBar] 渲染失败：未找到容器', containerSelector);
      return null;
    }

    this.options.container = container;
    return this.init().el;
  }

  /**
   * 动态修改导航栏标题
   * 常用于识别结果页显示当前物品名称
   * @param {string} newTitle - 新的标题文字
   * @returns {void}
   */
  set_title(newTitle) {
    this.props.title = newTitle || '垃圾分类';

    if (this._titleElement) {
      this._titleElement.textContent = this.props.title;

      this._titleElement.style.animation = 'none';
      void this._titleElement.offsetHeight;
      this._titleElement.style.animation = 'navTitleFade 0.3s ease';
    }
  }

  /**
   * 获取当前标题
   * @returns {string} 当前标题文字
   */
  get_title() {
    return this.props.title;
  }

  /**
   * 显示或隐藏历史按钮
   * @param {boolean} visible - 是否显示
   * @returns {void}
   */
  set_history_visible(visible) {
    if (this.el) {
      const btn = this.el.querySelector('#navHistoryBtn');
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
  _goHome() {
    window.location.hash = '#/home';

    this.el.dispatchEvent(new CustomEvent('nav:home', {
      bubbles: true,
      detail: { source: 'logo' }
    }));
  }

  /**
   * 处理历史按钮点击事件
   * @private
   * @returns {void}
   */
  _openHistory() {
    if (typeof this.props.onHistoryClick === 'function') {
      this.props.onHistoryClick();
    } else {
      window.location.hash = '#/history';
    }

    this.el.dispatchEvent(new CustomEvent('nav:history', {
      bubbles: true
    }));
  }
}

/* ========== 组件内联样式 ========== */
const NAV_BAR_STYLES = `
/* ======== NavBar 顶部导航栏样式 ======== */
.nav-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 56px;
    z-index: 100;
    
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    border-bottom: 1px solid rgba(45, 155, 94, 0.10);
    
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-bar__left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

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

@keyframes navTitleFade {
    0% { opacity: 0.5; transform: translateX(-4px); }
    100% { opacity: 1; transform: translateX(0); }
}

.nav-bar__right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

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

@supports (padding-top: env(safe-area-inset-top)) {
    .nav-bar {
        padding-top: env(safe-area-inset-top);
        height: calc(56px + env(safe-area-inset-top));
    }
}
`;

if (!document.getElementById('nav-bar-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'nav-bar-styles';
    styleSheet.textContent = NAV_BAR_STYLES;
    document.head.appendChild(styleSheet);
}

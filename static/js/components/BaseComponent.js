/**
 * UI组件基类
 * 提供统一的初始化、渲染、更新、销毁生命周期管理
 *
 * 设计目标：
 * - 统一所有UI组件的接口规范
 * - 提供标准化的生命周期钩子
 * - 自动管理事件监听器的注册与清理
 * - 支持渐进式迁移现有组件
 *
 * @class BaseComponent
 * @example
 * import { BaseComponent } from './BaseComponent.js';
 *
 * class MyComponent extends BaseComponent {
 *   constructor(options = {}) {
 *     super({
 *       container: options.container,
 *       props: { title: options.title },
 *       state: { count: 0 }
 *     });
 *   }
 *
 *   render() {
 *     const el = document.createElement('div');
 *     el.className = 'my-component';
 *     el.innerHTML = `<h1>${this.props.title}</h1>`;
 *     return el;
 *   }
 * }
 */
export class BaseComponent {
  /**
   * 构造函数 - 初始化组件配置
   * @param {Object} options - 组件配置项
   * @param {HTMLElement|string} options.container - 挂载容器元素或选择器
   * @param {Object} [options.props={}] - 初始属性（静态配置）
   * @param {Object} [options.state={}] - 初始状态（动态数据）
   * @param {Object} [options.events={}] - 事件回调映射 {eventName: handler}
   */
  constructor(options = {}) {
    this.options = options;
    this.props = options.props || {};
    this.state = options.state || {};
    this.events = options.events || {};

    this.el = null;
    this._eventListeners = [];
    this._isDestroyed = false;
  }

  /**
   * 初始化组件
   * 创建DOM、绑定事件、设置初始状态
   *
   * 生命周期流程：
   * 1. 检查销毁状态（防止重复初始化）
   * 2. 获取挂载容器
   * 3. 调用render()生成DOM
   * 4. 将DOM插入容器
   * 5. 调用bindEvents()绑定事件
   * 6. 调用afterInit()执行后续逻辑
   *
   * @returns {this} 组件实例（支持链式调用）
   */
  init() {
    if (this._isDestroyed) {
      console.warn('[BaseComponent] 组件已销毁，无法重复初始化');
      return this;
    }

    const container = this._getContainer();
    if (!container) {
      console.error('[BaseComponent] 找不到挂载容器', this.options.container);
      return this;
    }

    this.el = this.render();
    if (this.el && container) {
      container.appendChild(this.el);
    }

    this.bindEvents();
    this.afterInit();

    return this;
  }

  /**
   * 渲染DOM结构（子类必须实现）
   *
   * 子类应在此方法中：
   * - 创建根DOM元素
   * - 构建内部HTML结构
   * - 返回根元素引用
   *
   * @abstract
   * @returns {HTMLElement} 组件根DOM元素
   * @throws {Error} 如果子类未实现此方法
   */
  render() {
    throw new Error('子类必须实现 render() 方法');
  }

  /**
   * 绑定事件（子类可选重写）
   *
   * 在此方法中绑定所有DOM事件监听器。
   * 推荐使用 _bindEvent() 辅助方法进行绑定，
   * 以便destroy()时自动清理。
   *
   * @returns {void}
   */
  bindEvents() {}

  /**
   * 初始化后钩子（子类可选重写）
   *
   * 在init()完成后调用，可用于：
   * - 执行额外的初始化逻辑
   * - 触发初始动画
   * - 发送分析数据等
   *
   * @returns {void}
   */
  afterInit() {}

  /**
   * 更新组件数据并重新渲染
   *
   * 合并新的state和props到当前实例，
   * 然后重新调用render()替换旧DOM。
   *
   * @param {Object} [newState={}] - 需要更新的状态字段
   * @param {Object} [newProps={}] - 需要更新的属性字段
   * @returns {this} 组件实例（支持链式调用）
   */
  update(newState = {}, newProps = {}) {
    if (this._isDestroyed) return this;

    Object.assign(this.state, newState);
    Object.assign(this.props, newProps);

    const newEl = this.render();
    if (newEl && this.el && this.el.parentNode) {
      this.el.parentNode.replaceChild(newEl, this.el);
      this.el = newEl;
      this.bindEvents();
    }

    return this;
  }

  /**
   * 销毁组件
   *
   * 清理顺序：
   * 1. 设置销毁标记（防止重复操作）
   * 2. 移除所有通过_bindEvent()注册的事件监听器
   * 3. 从DOM中移除元素
   * 4. 释放所有引用（防止内存泄漏）
   *
   * @returns {void}
   */
  destroy() {
    if (this._isDestroyed) return;

    this._isDestroyed = true;

    this._eventListeners.forEach(({ el, event, handler }) => {
      el.removeEventListener(event, handler);
    });
    this._eventListeners = [];

    if (this.el && this.el.parentNode) {
      this.el.parentNode.removeChild(this.el);
    }

    this.el = null;
    this.props = null;
    this.state = null;
    this.options = null;
  }

  /**
   * 安全地绑定事件（自动记录以便destroy时清理）
   *
   * 所有在此方法中注册的事件监听器都会被自动追踪，
   * 当调用destroy()时会统一移除，避免内存泄漏。
   *
   * @param {HTMLElement} el - 目标DOM元素
   * @param {string} event - 事件名称（如'click', 'input'）
   * @param {Function} handler - 事件处理函数
   * @returns {void}
   *
   * @example
   * // 在 bindEvents() 中使用
   * bindEvents() {
   *   const btn = this.el.querySelector('.my-btn');
   *   this._bindEvent(btn, 'click', () => this.handleClick());
   * }
   */
  _bindEvent(el, event, handler) {
    el.addEventListener(event, handler);
    this._eventListeners.push({ el, event, handler });
  }

  /**
   * 获取挂载容器元素
   *
   * 支持两种传入方式：
   * - 字符串选择器（会自动查询DOM）
   * - HTMLElement元素（直接返回）
   *
   * @private
   * @returns {HTMLElement|null} 容器元素或null
   */
  _getContainer() {
    const container = this.options.container;
    if (!container) return null;

    if (typeof container === 'string') {
      return document.querySelector(container);
    }

    if (container instanceof HTMLElement) {
      return container;
    }

    return null;
  }
}

/**
 * @fileoverview UI工具函数模块
 * @description 封装Toast提示、Loading遮罩、模态弹窗等通用UI交互组件
 *              适用于校园垃圾分类SPA前端的全局反馈交互场景
 * @module utils/ui
 */

// ==================== 内部状态与常量 ====================

/** Toast队列：存储待显示的消息，实现排队机制 */
let _toastQueue = [];

/** 当前正在显示的Toast定时器引用 */
let _toastTimer = null;

/** 当前是否已有Toast正在展示 */
let _isToastShowing = false;

/** Toast默认显示时长（毫秒） */
const TOAST_DEFAULT_DURATION = 2500;

/** Modal当前Promise的resolve引用，用于外部关闭时传递结果 */
let _modalResolve = null;

/**
 * 获取或创建DOM元素的工具函数
 *
 * @param {string} id - 元素ID（不含#前缀）
 * @param {string} tag - 若元素不存在则创建的标签名
 * @param {string} [appendTo='body'] - 新建元素的挂载父节点选择器
 * @returns {HTMLElement} 目标DOM元素
 * @description 内部辅助函数，用于懒初始化UI容器元素。
 *              若DOM中已存在该ID元素则直接返回，否则创建并插入文档
 */
function _getOrCreateElement(id, tag, appendTo = 'body') {
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement(tag);
    el.id = id;
    document.querySelector(appendTo).appendChild(el);
  }
  return el;
}

/**
 * 消费Toast队列中的下一条消息
 *
 * @description 内部函数：从队列头部取出消息并渲染显示，
 *              显示完毕后自动触发下一条。若队列为空则重置状态
 */
function _processToastQueue() {
  if (_toastQueue.length === 0 || _isToastShowing) return;

  _isToastShowing = true;
  const { msg, type, duration } = _toastQueue.shift();

  const containerEl = _getOrCreateElement('toastContainer', 'div');
  containerEl.classList.add('toast-container');

  const toastEl = document.createElement('div');
  toastEl.textContent = msg;
  toastEl.className = `toast toast--${type}`;
  containerEl.appendChild(toastEl);

  _toastTimer = setTimeout(() => {
    toastEl.classList.add('exiting');
    setTimeout(() => {
      if (toastEl.parentNode) {
        toastEl.parentNode.removeChild(toastEl);
      }
      _isToastShowing = false;
      _processToastQueue();
    }, 300);
  }, duration);
}

// ==================== 公开API ====================

/**
 * 显示轻量提示消息（Toast）
 *
 * @param {string} msg - 提示文本内容
 * @param {'success'|'error'|'warning'|'info'} [type='info'] - 提示类型，对应不同颜色主题
 * @param {number} [duration=2500] - 显示持续时间（毫秒）
 * @returns {void}
 *
 * @description 行为特性：
 *   - 动态创建/复用 #toast DOM元素
 *   - 支持连续调用队列机制：若当前有Toast未消失，新消息自动排队等待
 *   - 到达duration后自动淡出消失
 *   - 需配合CSS定义 .toast / .toast--visible / .toast--{type} 样式
 *
 * @example
 * import { showToast } from './utils/ui.js';
 *
 * showToast('识别成功！', 'success');
 * showToast('图片格式不支持', 'error', 3000);
 * showToast('正在处理...', 'warning'); // 前一条未消时会排队
 */
export function showToast(msg, type = 'info', duration = TOAST_DEFAULT_DURATION) {
  // 参数校验：确保type在允许范围内
  const validTypes = ['success', 'error', 'warning', 'info'];
  const safeType = validTypes.includes(type) ? type : 'info';

  // 将消息推入队列
  _toastQueue.push({ msg, type: safeType, duration });

  // 尝试消费队列（若当前空闲则立即显示）
  _processToastQueue();
}

/**
 * 立即隐藏当前正在显示的Toast
 *
 * @returns {void}
 * @description 清除当前Toast的定时器、移除可见样式类、清空队列。
 *              用于页面切换、路由跳转等需要立即清除所有提示的场景
 *
 * @example
 * import { hideToast } from './utils/ui.js';
 * router.beforeEach(() => hideToast());
 */
export function hideToast() {
  // 清除当前定时器防止延迟触发
  if (_toastTimer) {
    clearTimeout(_toastTimer);
    _toastTimer = null;
  }

  // 清空等待队列
  _toastQueue = [];
  _isToastShowing = false;

  // 移除所有Toast元素
  const container = document.getElementById('toastContainer');
  if (container) {
    container.innerHTML = '';
  }
}

/**
 * 显示全局Loading加载遮罩
 *
 * @param {string} [text='正在识别中...'] - 加载提示文字
 * @returns {void}
 *
 * @description 操作 #loadingOverlay 元素：
 *   - 设置/更新提示文本内容
 *   - 添加 .show 类触发CSS显示动画
 *   - 支持多阶段状态文字切换（如压缩→上传→识别流程）
 *   - 需配合CSS定义 #loadingOverlay / #loadingOverlay.show 样式
 *
 * 状态机文字切换示例流程：
 *   idle → showLoading('压缩中...') → setLoadingText('上传中...') → setLoadingText('识别中...') → hideLoading()
 *
 * @example
 * import { showLoading, setLoadingText, hideLoading } from './utils/ui.js';
 *
 * showLoading('正在压缩图片...');
 * // ...压缩完成后...
 * setLoadingText('正在上传...');
 * // ...上传完成后...
 * setLoadingText('AI识别中...');
 * // ...全部完成...
 * hideLoading();
 */
export function showLoading(text = '正在识别中...') {
  const overlay = _getOrCreateElement('loadingOverlay', 'div');
  overlay.className = 'loading-overlay';
  overlay.querySelector('.loading-overlay__text')
    ? (overlay.querySelector('.loading-overlay__text').textContent = text)
    : (overlay.innerHTML = `<div class="spinner"></div><span class="loading-overlay__text">${text}</span>`);
  overlay.classList.remove('hidden');
}

/**
 * 隐藏全局Loading遮罩
 *
 * @returns {void}
 * @description 移除 #loadingOverlay 的 .show 类触发隐藏动画。
 *              不影响内部文字内容，下次showLoading可复用
 *
 * @example
 * hideLoading(); // 识别完成或出错时调用
 */
export function hideLoading() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) {
    overlay.classList.add('hidden');
  }
}

/**
 * 更新Loading遮罩的文字内容（不改变显示/隐藏状态）
 *
 * @param {string} text - 新的提示文字
 * @returns {void}
 * @description 仅修改文字，用于长流程中的阶段提示切换。
 *              若Loading当前处于隐藏状态则仅更新文字不显示
 *
 * @example
 * setLoadingText('图像分析中...'); // 在异步流程各阶段调用
 */
export function setLoadingText(text) {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) {
    const textEl = overlay.querySelector('.loading-overlay__text');
    if (textEl) {
      textEl.textContent = text;
    }
  }
}

/**
 * 显示确认模态弹窗
 *
 * @async
 * @param {Object} options - 弹窗配置选项
 * @param {string} [options.title='提示'] - 弹窗标题
 * @param {string} options.content - 弹窗正文内容（支持HTML字符串）
 * @param {string} [options.confirmText='确定'] - 确认按钮文字
 * @param {string} [options.cancelText='取消'] - 取消按钮文字
 * @param {Function} [options.onConfirm] - 确认回调（可选，额外逻辑）
 * @param {Function} [options.onCancel] - 取消回调（可选，额外逻辑）
 * @returns {Promise<boolean>} 用户操作结果：确认返回true，取消返回false
 *
 * @description 操作 #modalOverlay 元素：
 *   - 动态渲染标题、内容区域、确认/取消按钮
 *   - 返回Promise，用户点击按钮后resolve对应布尔值
 *   - 支持通过onConfirm/onCancel绑定额外业务逻辑
 *   - 需配合CSS定义 #modalOverlay / #modalOverlay.show 及内部结构样式
 *
 * @example
 * import { showModal } from './utils/ui.js';
 *
 * const confirmed = await showModal({
 *   title: '删除确认',
 *   content: '确定要删除这条识别记录吗？此操作不可恢复。',
 *   confirmText: '删除',
 *   cancelText: '再想想',
 *   onConfirm: () => console.log('用户确认了删除')
 * });
 *
 * if (confirmed) {
 *   // 执行删除操作
 * }
 */
export async function showModal({
  title = '提示',
  content,
  confirmText = '确定',
  cancelText = '取消',
  onConfirm,
  onCancel
}) {
  const overlay = _getOrCreateElement('modalOverlay', 'div');

  // 构建弹窗HTML结构并设置样式类
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal__header">
        <h3 class="modal__title">${title}</h3>
        <button class="modal__close" id="modalCloseBtn" aria-label="关闭">&times;</button>
      </div>
      <div class="modal__body">${content}</div>
      <div class="modal__footer">
        <button class="btn btn-secondary modal__btn-cancel">${cancelText}</button>
        <button class="btn btn-primary modal__btn-confirm">${confirmText}</button>
      </div>
    </div>
  `;

  // 移除隐藏类触发入场动画
  overlay.classList.remove('hidden');

  // 创建Promise用于等待用户操作
  const result = new Promise((resolve) => {
    _modalResolve = resolve;

    // 绑定确认按钮事件
    const confirmBtn = overlay.querySelector('.modal__btn-confirm');
    confirmBtn.addEventListener('click', () => {
      if (typeof onConfirm === 'function') onConfirm();
      closeModal();
      resolve(true);
    });

    // 绑定取消按钮事件
    const cancelBtn = overlay.querySelector('.modal__btn-cancel');
    cancelBtn.addEventListener('click', () => {
      if (typeof onCancel === 'function') onCancel();
      closeModal();
      resolve(false);
    });

    // 点击背景遮罩层也视为取消
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        if (typeof onCancel === 'function') onCancel();
        closeModal();
        resolve(false);
      }
    });
  });

  return result;
}

/**
 * 关闭当前模态弹窗
 *
 * @returns {void}
 * @description 移除 #modalOverlay 的 .show 类触发退场动画，
 *              并清理内部HTML释放事件监听引用
 *
 * @example
 * closeModal(); // 手动关闭（通常由showModal内部自动调用）
 */
export function closeModal() {
  const overlay = document.getElementById('modalOverlay');
  if (overlay) {
    overlay.classList.add('hidden');
    // 清理内容以移除事件监听器引用
    setTimeout(() => {
      overlay.innerHTML = '';
    }, 300); // 等待CSS过渡动画完成
  }
  _modalResolve = null;
}

/**
 * 二次确认快捷方法
 *
 * @async
 * @param {string} text - 确认提示文本
 * @param {Object} [extraOptions={}] - 额外传给showModal的配置项
 * @returns {Promise<boolean>} 用户点击确认返回true，取消返回false
 *
 * @description 对showModal的简化封装，适用于仅需一行代码弹出确认框的场景。
 *              默认标题为"确认操作"，仅传入正文文本即可使用
 *
 * @example
 * import { confirm } from './utils/ui.js';
 *
 * if (await confirm('确定要清空所有历史记录吗？')) {
 *   storage.clearHistory();
 * }
 */
export async function confirm(text, extraOptions = {}) {
  return showModal({
    title: '确认操作',
    content: text,
    ...extraOptions
  });
}

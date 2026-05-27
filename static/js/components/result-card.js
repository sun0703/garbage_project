/**
 * 结果卡片组件 - ResultCard（核心组件）
 *
 * 功能说明：
 * - 展示AI识别结果的完整信息卡片
 * - 包含：类别名称、颜色标识、置信度进度条、投放指引、处理建议、推理依据
 * - 支持演示模式标签显示
 * - 置信度区间颜色映射：绿(>80%) / 黄(60-80%) / 红(<60%)
 * - 丰富的入场和交互动画效果
 * - 支持生成分享文本模板
 *
 * 继承自 BaseComponent，遵循标准化生命周期：
 * constructor → init() → render() → bindEvents() → afterInit()
 *
 * 数据来源：/api/predict 接口响应的 result 字段
 *
 * @class ResultCard
 * @extends BaseComponent
 * @example
 * import { ResultCard } from './result-card.js';
 *
 * // 新标准用法（推荐）
 * const card = new ResultCard({
 *   container: '#resultContainer',
 *   props: { showAnimation: true, showReasoning: true }
 * });
 * card.init();
 * card.updateData({
 *   category: '可回收物',
 *   category_id: 1,
 *   confidence: 0.92,
 *   ...
 * });
 *
 * // 向后兼容用法（仍支持）
 * const card = new ResultCard();
 * card.render('#resultContainer');
 */

import { escapeHtml } from '../utils/escape.js';
import { BaseComponent } from './BaseComponent.js';

export class ResultCard extends BaseComponent {
  /**
   * 构造函数 - 初始化结果卡片配置
   * @param {Object} [options={}] - 配置选项
   * @param {HTMLElement|string} [options.container] - 挂载容器（用于init()方法）
   * @param {boolean} [options.showAnimation=true] - 是否启用入场动画
   * @param {boolean} [options.showReasoning=true] - 是否显示推理依据区域
   */
  constructor(options = {}) {
    super({
      container: options.container,
      props: {
        showAnimation: options.showAnimation !== false,
        showReasoning: options.showReasoning !== false
      },
      state: {}
    });

    this._currentData = null;

    /**
     * 垃圾分类ID到名称的映射表
     * @type {Object<number, string>}
     */
    this._categoryMap = {
      0: '其他垃圾',
      1: '可回收物',
      2: '厨余垃圾',
      3: '有害垃圾'
    };

    /**
     * 垃圾桶图标映射（按分类ID）
     * @type {Object<number, string>}
     */
    this._binIconMap = {
      0: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`,
      1: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>`,
      2: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/><path d="M15 13h-2v2h-2v2h2v2h2v-2h2v-2h-2z"/></svg>`,
      3: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 16h2v2h-2zm0-6h2v4h-2z"/></svg>`
    };
  }

  /**
   * 渲染结果卡片的DOM结构
   * 实现BaseComponent的抽象方法
   *
   * @returns {HTMLElement} 卡片根元素引用
   */
  render() {
    const cardEl = document.createElement('div');
    cardEl.className = 'result-card';
    cardEl.setAttribute('role', 'article');
    cardEl.setAttribute('aria-label', '识别结果');

    /* ========== 卡片内部结构 ========== */
    cardEl.innerHTML = `
            <!-- 顶部区域：分类图标 + 类别名称 -->
            <div class="result-card__header">
                <div class="result-card__bin-icon" id="rcBinIcon">
                    ${this._binIconMap[1]}
                </div>
                <h2 class="result-card__category" id="rcCategory">等待识别...</h2>
            </div>

            <!-- 分类颜色条 -->
            <div class="result-card__color-bar" id="rcColorBar"></div>

            <!-- 置信度展示区 -->
            <div class="result-card__confidence">
                <div class="result-card__confidence-label">
                    <span>置信度</span>
                    <span class="result-card__confidence-value" id="rcConfValue">--</span>
                </div>
                <!-- 进度条外框 -->
                <div class="result-card__progress-track">
                    <!-- 进度条填充层（带动画） -->
                    <div class="result-card__progress-fill" id="rcProgressFill"></div>
                </div>
            </div>

            <!-- 投放指引区域 -->
            <div class="result-card__section result-card__guidance">
                <div class="result-card__section-title">
                    <span class="result-card__emoji">📋</span>
                    <span>投放指引</span>
                </div>
                <p class="result-card__section-text" id="rcGuidance">
                    请上传图片进行识别...
                </p>
            </div>

            <!-- 处理建议区域（P1功能预留） -->
            <div class="result-card__section result-card__tips" id="rcTipsSection" style="display:none;">
                <div class="result-card__section-title">
                    <span class="result-card__emoji">💡</span>
                    <span>处理建议</span>
                </div>
                <p class="result-card__section-text" id="rcTips"></p>
            </div>

            <!-- 演示模式标签（条件显示） -->
            <div class="result-card__demo-badge" id="rcDemoBadge" style="display:none;">
                <span class="result-card__emoji">⚠️</span>
                <span>演示模式</span>
                <span class="result-card__demo-hint">当前为模拟数据，非真实AI识别</span>
            </div>

            <!-- 推理依据区域 -->
            <div class="result-card__section result-card__reasoning" id="rcReasoningSection" style="display:none;">
                <div class="result-card__section-title">
                    <span class="result-card__emoji">📊</span>
                    <span>分类依据</span>
                </div>
                <p class="result-card__section-text" id="rcReasoning"></p>
            </div>
        `;

    return cardEl;
  }

  /**
   * 向后兼容的渲染方法
   * 支持旧的调用方式：card.render('#container')
   *
   * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
   * @returns {HTMLElement|null} 卡片根元素引用
   */
  renderToContainer(containerSelector) {
    const container = typeof containerSelector === 'string'
      ? document.querySelector(containerSelector)
      : containerSelector;

    if (!container) {
      console.error('[ResultCard] 渲染失败：未找到容器', containerSelector);
      return null;
    }

    this.options.container = container;
    return this.init().el;
  }

  /**
   * 更新卡片数据并触发动画
   * 核心方法：接收API返回的result对象并渲染完整卡片
   *
   * @param {Object} resultData - 识别结果数据
   * @param {string} resultData.category - 分类名称（如'可回收物'）
   * @param {number} resultData.category_id - 分类ID（0-3）
   * @param {string} resultData.bin_color - 对应垃圾桶颜色（CSS色值）
   * @param {string} resultData.bin_icon - 垃圾桶图标（emoji或SVG）
   * @param {string} resultData.label_cn - 物品中文名称
   * @param {number} resultData.confidence - 置信度（0-1之间的小数）
   * @param {string} resultData.guidance - 投放指引文案
   * @param {boolean} [resultData.is_demo_mode=false] - 是否为演示模式
   * @param {string} [resultData.reasoning=''] - 推理依据说明
   * @returns {void}
   */
  update(resultData) {
    if (!this.el || !resultData) {
      console.warn('[ResultCard] update调用失败：组件未渲染或数据为空');
      return;
    }

    this._currentData = resultData;

    const {
      category = '未知分类',
      category_id = 0,
      bin_color = '#666666',
      bin_icon = null,
      label_cn = '未知物品',
      confidence = 0,
      guidance = '暂无投放指引',
      is_demo_mode = false,
      reasoning = '',
      tips = null
    } = resultData;

    /* ======== 1. 更新分类头部（带动画）======== */
    this._updateHeader(category, category_id, bin_icon);

    /* ======== 2. 更新颜色条 ======== */
    this._updateColorBar(bin_color);

    /* ======== 3. 更新置信度进度条（带动画）======== */
    this._updateConfidence(confidence);

    /* ======== 4. 更新投放指引 ======== */
    this._updateGuidance(guidance);

    /* ======== 5. 更新处理建议（P1功能）======== */
    this._updateTips(tips);

    /* ======== 6. 更新演示模式标签 ======== */
    this._updateDemoBadge(is_demo_mode);

    /* ======== 7. 更新推理依据 ======== */
    this._updateReasoning(reasoning);

    /* ======== 8. 触发入场动画 ======== */
    if (this.props.showAnimation) {
      this._playEnterAnimation();
    }
  }

  /**
   * 生成分享文本模板（F-1.3.5功能预留）
   * 用于分享到社交平台或复制到剪贴板
   *
   * @param {Object} [customData=null] - 自定义数据（不传则使用当前数据）
   * @returns {string} 格式化的分享文本
   */
  getShareText(customData = null) {
    const data = customData || this._currentData;

    if (!data) {
      return '我正在使用「校园垃圾分类AI助手」进行智能垃圾分类！';
    }

    const confPercent = Math.round((data.confidence || 0) * 100);

    const lines = [
      `🗑 【校园垃圾分类AI助手】识别结果`,
      ``,
      `📦 物品名称：${data.label_cn || '未知物品'}`,
      `📂 垃圾分类：${data.category || '未知分类'}`,
      `🎯 置信度：${confPercent}%`,
      ``,
      `💬 ${data.guidance || '暂无投放指引'}`
    ];

    if (Array.isArray(data.tips) && data.tips.length > 0) {
      lines.push('', '📝 处理建议：');
      data.tips.forEach((step, i) => {
        lines.push(`   ${i + 1}. ${step}`);
      });
    }

    if (data.reasoning) {
      lines.push(``, `🔍 ${data.reasoning}`);
    }

    lines.push(``, `—— 来自校园垃圾分类AI助手 ——`);

    return lines.join('\n');
  }

  /**
   * 显示卡片（用于从隐藏状态切换到可见）
   * @returns {void}
   */
  show() {
    if (this.el) {
      this.el.classList.add('result-card--visible');

      if (this.props.showAnimation) {
        this._playEnterAnimation();
      }
    }
  }

  /**
   * 隐藏卡片
   * @returns {void}
   */
  hide() {
    if (this.el) {
      this.el.classList.remove('result-card--visible');
    }
  }

  /**
   * 重置卡片到初始状态
   * @returns {void}
   */
  reset() {
    if (!this.el) return;

    this._setText('#rcCategory', '等待识别...');
    this._setHtml('#rcBinIcon', this._binIconMap[1]);
    this._setStyle('#rcColorBar', { background: '#cccccc' });
    this._setStyle('#rcProgressFill', { width: '0%' });
    this._setText('#rcConfValue', '--');
    this._setText('#rcGuidance', '请上传图片进行识别...');
    this._hideElement('#rcTipsSection');
    this._hideElement('#rcDemoBadge');
    this._hideElement('#rcReasoningSection');

    this.el.classList.remove('result-card--animated');

    this._currentData = null;
  }

  /* ---- 各区域更新逻辑 ---- */

  /**
   * 更新卡片头部分类信息
   * @private
   * @param {string} category - 分类名称
   * @param {number} categoryId - 分类ID
   * @param {string|null} binIcon - 自定义图标（优先使用）
   * @returns {void}
   */
  _updateHeader(category, categoryId, binIcon) {
    this._setText('#rcCategory', category || '未知分类');

    const iconContainer = this.el.querySelector('#rcBinIcon');
    if (iconContainer) {
      if (binIcon && typeof binIcon === 'string') {
        if (binIcon.length <= 2) {
          iconContainer.textContent = binIcon;
          iconContainer.innerHTML = '';
          iconContainer.style.fontSize = '32px';
        } else {
          iconContainer.innerHTML = binIcon;
          iconContainer.style.fontSize = '';
        }
      } else if (this._binIconMap[categoryId]) {
        iconContainer.innerHTML = this._binIconMap[categoryId];
        iconContainer.style.fontSize = '';
      }
    }
  }

  /**
   * 更新分类颜色条
   * @private
   * @param {string} color - CSS颜色值
   * @returns {void}
   */
  _updateColorBar(color) {
    const colorBar = this.el.querySelector('#rcColorBar');
    if (colorBar) {
      colorBar.style.background = color || '#666666';

      colorBar.style.animation = 'none';
      void colorBar.offsetHeight;
      colorBar.style.animation = 'rcColorSlide 0.5s ease-out';
    }
  }

  /**
   * 更新置信度进度条（含动画）
   * @private
   * @param {number} confidence - 置信度值（0-1）
   * @returns {void}
   */
  _updateConfidence(confidence) {
    const fillEl = this.el.querySelector('#rcProgressFill');
    const valueEl = this.el.querySelector('#rcConfValue');

    if (!fillEl || !valueEl) return;

    const percent = Math.max(0, Math.min(1, confidence || 0));
    const displayPercent = Math.round(percent * 100);

    fillEl.style.width = '0%';

    fillEl.className = 'result-card__progress-fill';

    let levelClass = '';
    if (percent >= 0.80) {
      levelClass = 'result-card__progress-fill--high';
    } else if (percent >= 0.60) {
      levelClass = 'result-card__progress-fill--medium';
    } else {
      levelClass = 'result-card__progress-fill--low';
    }
    fillEl.classList.add(levelClass);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        fillEl.style.width = `${displayPercent}%`;
      });
    });

    valueEl.textContent = `${displayPercent}%`;
  }

  /**
   * 更新投放指引文案
   * @private
   * @param {string} guidance - 指引文案
   * @returns {void}
   */
  _updateGuidance(guidance) {
    this._setText('#rcGuidance', guidance || '暂无投放指引');
  }

  /**
   * 更新处理建议（v2.3 支持步骤数组）
   * @private
   * @param {string[]|string|null} tips - 处理建议：字符串数组(步骤列表)或纯文本
   * @returns {void}
   */
  _updateTips(tips) {
    const section = this.el.querySelector('#rcTipsSection');
    const textEl = this.el.querySelector('#rcTips');

    if (!section || !textEl) return;

    if (Array.isArray(tips) && tips.length > 0) {
      const html = tips
        .map((step, i) => `<div class="result-card__tip-step"><span class="result-card__tip-num">${i + 1}</span><span>${escapeHtml(step)}</span></div>`)
        .join('');
      textEl.innerHTML = html;
      this._showElement('#rcTipsSection');
      return;
    }

    if (typeof tips === 'string' && tips.trim()) {
      textEl.textContent = tips;
      this._showElement('#rcTipsSection');
      return;
    }

    this._hideElement('#rcTipsSection');
  }

  /**
   * 更新演示模式标签显示状态
   * @private
   * @param {boolean} isDemo - 是否演示模式
   * @returns {void}
   */
  _updateDemoBadge(isDemo) {
    if (isDemo) {
      this._showElement('#rcDemoBadge');
    } else {
      this._hideElement('#rcDemoBadge');
    }
  }

  /**
   * 更新推理依据区域
   * @private
   * @param {string} reasoning - 推理依据文本
   * @returns {void}
   */
  _updateReasoning(reasoning) {
    if (!this.props.showReasoning) return;

    if (reasoning && reasoning.trim()) {
      this._setText('#rcReasoning', reasoning);
      this._showElement('#rcReasoningSection');
    } else {
      this._hideElement('#rcReasoningSection');
    }
  }

  /**
   * 播放入场动画组合（fadeInUp + scale微弹）
   * @private
   * @returns {void}
   */
  _playEnterAnimation() {
    const card = this.el;

    card.classList.remove('result-card--animated');

    void card.offsetHeight;

    card.classList.add('result-card--animated');

    card.addEventListener('animationend', function handler() {
      card.removeEventListener('animationend', handler);
    }, { once: true });
  }

  /* ---- DOM工具方法 ---- */

  /**
   * 设置元素文本内容（安全转义）
   * @private
   * @param {string} selector - CSS选择器
   * @param {string} text - 文本内容
   * @returns {void}
   */
  _setText(selector, text) {
    const el = this.el.querySelector(selector);
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
    const el = this.el.querySelector(selector);
    if (el) el.innerHTML = html;
  }

  /**
   * 设置元素内联样式
   * @private
   * @param {string} selector - CSS选择器
   * @param {Object} styles - 样式对象
   * @returns {void}
   */
  _setStyle(selector, styles) {
    const el = this.el.querySelector(selector);
    if (el) Object.assign(el.style, styles);
  }

  /**
   * 显示指定元素
   * @private
   * @param {string} selector - CSS选择器
   * @returns {void}
   */
  _showElement(selector) {
    const el = this.el.querySelector(selector);
    if (el) el.style.display = '';
  }

  /**
   * 隐藏指定元素
   * @private
   * @param {string} selector - CSS选择器
   * @returns {void}
   */
  _hideElement(selector) {
    const el = this.el.querySelector(selector);
    if (el) el.style.display = 'none';
  }
}

/* ========== 组件内联样式 ========== */
const RESULT_CARD_STYLES = `
/* ======== ResultCard 结果卡片样式 ======== */
.result-card {
    background: var(--bg-card, rgba(255, 255, 255, 0.88));
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    border-radius: var(--radius-lg, 24px);
    padding: 24px;
    
    box-shadow: var(--shadow-lg, 0 8px 40px rgba(45, 155, 94, 0.10));
    border: 1px solid rgba(255, 255, 255, 0.6);
    
    opacity: 0;
    transform: translateY(20px) scale(0.98);
    transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.result-card--visible {
    opacity: 1;
    transform: translateY(0) scale(1);
}

.result-card--animated {
    animation: rcFadeInUpBounce 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes rcFadeInUpBounce {
    0% {
        opacity: 0;
        transform: translateY(24px) scale(0.96);
    }
    50% {
        opacity: 1;
        transform: translateY(-4px) scale(1.01);
    }
    75% {
        transform: translateY(2px) scale(0.995);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

@keyframes rcColorSlide {
    0% { transform: scaleX(0); opacity: 0.5; }
    100% { transform: scaleX(1); opacity: 1; }
}

.result-card__header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
}

.result-card__bin-icon {
    width: 48px;
    height: 48px;
    border-radius: var(--radius-sm, 10px);
    background: linear-gradient(135deg, rgba(45, 155, 94, 0.08), rgba(78, 205, 196, 0.12));
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    
    transition: transform 0.25s ease;
}

.result-card__bin-icon svg {
    width: 26px;
    height: 26px;
    fill: var(--primary, #2D9B5E);
}

.result-card:hover .result-card__bin-icon {
    transform: rotate(-5deg) scale(1.05);
}

.result-card__category {
    font-size: 22px;
    font-weight: 800;
    color: var(--text-primary, #1A1A2E);
    letter-spacing: 0.5px;
    line-height: 1.3;
    margin: 0;
}

.result-card__color-bar {
    height: 4px;
    border-radius: 2px;
    background: #cccccc;
    margin-bottom: 18px;
    transform-origin: left center;
    overflow: hidden;
}

.result-card__confidence {
    margin-bottom: 18px;
}

.result-card__confidence-label {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-secondary, #5A6776);
    font-weight: 500;
}

.result-card__confidence-value {
    font-size: 16px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}

.result-card__progress-track {
    width: 100%;
    height: 10px;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 5px;
    overflow: hidden;
}

.result-card__progress-fill {
    height: 100%;
    border-radius: 5px;
    
    width: 0%;
    transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
    
    position: relative;
}

.result-card__progress-fill::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(255, 255, 255, 0.3) 50%,
        transparent 100%
    );
    animation: rcShine 2s infinite;
}

@keyframes rcShine {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.result-card__progress-fill--high {
    background: linear-gradient(90deg, #27AE60, #58D68D);
    box-shadow: 0 2px 8px rgba(39, 174, 96, 0.25);
}

.result-card__progress-fill--medium {
    background: linear-gradient(90deg, #F39C12, #F7DC6F);
    box-shadow: 0 2px 8px rgba(243, 156, 18, 0.25);
}

.result-card__progress-fill--low {
    background: linear-gradient(90deg, #E74C3C, #F1948A);
    box-shadow: 0 2px 8px rgba(231, 76, 60, 0.25);
}

.result-card__section {
    padding: 14px 16px;
    margin-top: 12px;
    border-radius: var(--radius-sm, 10px);
    background: linear-gradient(
        135deg,
        rgba(45, 155, 94, 0.03),
        rgba(78, 205, 196, 0.04)
    );
}

.result-card__section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--primary, #2D9B5E);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

.result-card__emoji {
    font-style: normal;
    font-size: 14px;
}

.result-card__section-text {
    font-size: 14px;
    color: var(--text-primary, #1A1A2E);
    line-height: 1.65;
    margin: 0;
}

.result-card__guidance {
    border-left: 4px solid var(--primary, #2D9B5E);
    background: linear-gradient(
        135deg,
        rgba(45, 155, 94, 0.04),
        rgba(78, 205, 196, 0.05)
    );
}

.result-card__tips {
    border-left: 4px solid var(--accent, #FF9F43);
    background: linear-gradient(
        135deg,
        rgba(255, 159, 67, 0.03),
        rgba(255, 190, 118, 0.05)
    );
}

.result-card__tip-step {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 6px 0;
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--text-primary, #1A1A2E);
}

.result-card__tip-step:not(:last-child) {
    border-bottom: 1px dashed rgba(0, 0, 0, 0.06);
}

.result-card__tip-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent, #FF9F43), #F7B731);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 1px;
}

.result-card__demo-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    
    margin-top: 14px;
    padding: 10px 14px;
    
    background: linear-gradient(135deg, rgba(255, 159, 67, 0.08), rgba(255, 190, 118, 0.10));
    border: 1px dashed rgba(255, 159, 67, 0.3);
    border-radius: var(--radius-sm, 10px);
    
    font-size: 12px;
    color: var(--accent, #FF9F43);
    font-weight: 600;
}

.result-card__demo-hint {
    font-weight: 400;
    color: var(--text-muted, #95A0AA);
    font-size: 11px;
}

@media (prefers-reduced-motion: reduce) {
    .result-card,
    .result-card__progress-fill,
    .result-card__bin-icon,
    .result-card__color-bar {
        animation-duration: 0.01ms !important;
        transition-duration: 0.2s !important;
    }
    
    .result-card__progress-fill::after {
        animation: none;
    }
}
`;

if (!document.getElementById('result-card-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'result-card-styles';
    styleSheet.textContent = RESULT_CARD_STYLES;
    document.head.appendChild(styleSheet);
}

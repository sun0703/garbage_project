// 积分徽章 — 小圆形 + 数字 + 滚动动画
// TODO: 迁移到BaseComponent基类

export class PointBadge {
    /**
     * 构造函数 - 初始化积分徽章配置
     * @param {Object} [options={}] - 配置选项
     * @param {number} [options.initialPoints=0] - 初始积分值
     * @param {'small'|'medium'|'large'} [options.size='medium'] - 徽章尺寸规格
     * @param {boolean} [options.showIcon=true] - 是否显示星星图标
     * @param {boolean} [options.showLabel=false] - 是否显示"积分"文字
     * @param {Function} [options.onClick] - 点击回调（阶段二使用）
     */
    constructor(options = {}) {
        /** @type {number} 当前显示的积分值 */
        this._points = options.initialPoints || 0;
        
        /** @type {string} 徽章尺寸规格 */
        this._size = options.size || 'medium';
        
        /** @type {boolean} 是否显示图标 */
        this._showIcon = options.showIcon !== false;
        
        /** @type {boolean} 是否显示"积分"标签文字 */
        this._showLabel = options.showLabel || false;
        
        /** @type {Function|null} 点击回调函数 */
        this._onClickCallback = options.onClick || null;

        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;
        
        /** @type {HTMLElement|null} 积分数值元素引用 */
        this._valueElement = null;

        /**
         * 积分等级配置表
         * @type {Array<{min: number, max: number, label: string, color: string}>}
         */
        this._levelConfig = [
            { min: 0, max: 99, label: '新手', color: '#95A0AA' },
            { min: 100, max: 499, label: '入门', color: '#007bff' },
            { min: 500, max: 1999, label: '熟练', color: '#2D9B5E' },
            { min: 2000, max: Infinity, label: '专家', color: '#FF9F43' }
        ];
    }

    /**
     * 渲染积分徽章到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} 徽章根元素引用
     */
    render(containerSelector) {
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[PointBadge] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        /* ========== 创建徽章根元素 ========== */
        const badgeEl = document.createElement('div');
        badgeEl.className = `point-badge point-badge--${this._size}`;
        badgeEl.setAttribute('role', 'status');
        badgeEl.setAttribute('aria-label', `当前积分：${this._points}`);
        badgeEl.setAttribute('title', `${this._points} 积分 · ${this._getCurrentLevel().label}`);

        /* ========== 内部结构 ========== */
        badgeEl.innerHTML = `
            ${this._showIcon ? `
            <span class="point-badge__icon">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                </svg>
            </span>
            ` : ''}
            <span class="point-badge__value" id="pbValue">${this._formatNumber(this._points)}</span>
            ${this._showLabel ? `
            <span class="point-badge__label">积分</span>
            ` : ''}
        `;

        container.appendChild(badgeEl);

        this._element = badgeEl;
        this._valueElement = badgeEl.querySelector('#pbValue');

        /* ======== 绑定点击事件 ======== */
        if (this._onClickCallback) {
            badgeEl.style.cursor = 'pointer';
            badgeEl.addEventListener('click', () => {
                this._onBadgeClick();
            });
        }

        this._applyLevelStyle();

        return badgeEl;
    }

    /**
     * 更新积分数值
     * @param {number} newPoints - 新的积分值
     * @param {Object} [animationOptions={}] - 动画配置
     * @param {boolean} [animationOptions.animate=true] - 是否启用数字滚动动画
     * @param {number} [animationOptions.duration=600] - 动画时长(毫秒)
     * @returns {void}
     */
    update(newPoints, animationOptions = {}) {
        if (!this._element) {
            console.warn('[PointBadge] update调用失败：组件未渲染');
            return;
        }

        const safePoints = Math.max(0, Math.floor(newPoints) || 0);
        const oldPoints = this._points;
        this._points = safePoints;

        const shouldAnimate = animationOptions.animate !== false 
                           && animationOptions.animate !== undefined 
                           ? animationOptions.animate 
                           : true;

        if (shouldAnimate && oldPoints !== safePoints) {
            this._animateValue(oldPoints, safePoints, animationOptions.duration || 600);
        } else {
            this._updateDisplay(safePoints);
        }

        this._applyLevelStyle();

        this._element.setAttribute('aria-label', `当前积分：${safePoints}`);
        this._element.setAttribute('title', `${safePoints} 积分 · ${this._getCurrentLevel().label}`);
    }

    /**
     * 获取当前积分值
     * @returns {number} 当前积分
     */
    getPoints() {
        return this._points;
    }

    /**
     * 增加积分（便捷方法）
     * @param {number} delta - 增加量（正数）
     * @returns {void}
     */
    addPoints(delta) {
        if (delta > 0) {
            this.update(this._points + delta);
        }
    }

    /**
     * 获取当前等级信息
     * @returns {{min: number, max: number, label: string, color: string}} 等级对象
     */
    getCurrentLevel() {
        return this._getCurrentLevel();
    }

    /**
     * 设置点击回调
     * @param {Function} callback - 点击回调函数
     * @returns {void}
     */
    setOnClick(callback) {
        this._onClickCallback = callback;
        
        if (this._element) {
            this._element.style.cursor = typeof callback === 'function' ? 'pointer' : 'default';
            
            this._element.removeEventListener('click', this._boundClickHandler);
            
            if (typeof callback === 'function') {
                this._boundClickHandler = () => this._onBadgeClick();
                this._element.addEventListener('click', this._boundClickHandler);
            }
        }
    }

    /**
     * 设置是否可交互
     * @param {boolean} interactive - 是否可点击交互
     * @returns {void}
     */
    setInteractive(interactive) {
        if (!this._element) return;

        this._element.classList.toggle('point-badge--interactive', interactive);
        this._element.setAttribute('tabindex', interactive ? '0' : '-1');
        this._element.setAttribute('role', interactive ? 'button' : 'status');
    }

    /**
     * 数字滚动动画实现
     * @private
     * @param {number} from - 起始值
     * @param {number} to - 目标值
     * @param {number} duration - 动画时长(毫秒)
     * @returns {void}
     */
    _animateValue(from, to, duration) {
        if (!this._valueElement) return;

        const startTime = performance.now();

        const step = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeProgress = 1 - Math.pow(1 - progress, 4);
            const currentValue = Math.round(from + (to - from) * easeProgress);

            this._updateDisplay(currentValue);

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                this._updateDisplay(to);
                this._triggerUpdateEffect();
            }
        };

        requestAnimationFrame(step);
    }

    /**
     * 更新显示内容（无动画版本）
     * @private
     * @param {number} value - 要显示的数值
     * @returns {void}
     */
    _updateDisplay(value) {
        if (this._valueElement) {
            this._valueElement.textContent = this._formatNumber(value);
        }
    }

    /**
     * 格式化数字显示（添加千位分隔符）
     * @private
     * @param {number} num - 数值
     * @returns {string} 格式化后的字符串
     */
    _formatNumber(num) {
        return num.toLocaleString('zh-CN');
    }

    /**
     * 获取当前积分对应的等级信息
     * @private
     * @returns {Object} 等级配置对象
     */
    _getCurrentLevel() {
        for (const level of this._levelConfig) {
            if (this._points >= level.min && this._points <= level.max) {
                return level;
            }
        }
        return this._levelConfig[this._levelConfig.length - 1];
    }

    /**
     * 根据当前等级应用视觉样式
     * @private
     * @returns {void}
     */
    _applyLevelStyle() {
        if (!this._element) return;

        const level = this._getCurrentLevel();

        this._element.style.setProperty('--badge-color', level.color);

        this._levelConfig.forEach((config, index) => {
            this._element.classList.toggle(`point-badge--level-${index}`, config.label === level.label);
        });
    }

    /**
     * 触发更新后的视觉效果
     * @private
     * @returns {void}
     */
    _triggerUpdateEffect() {
        if (!this._element) return;

        this._element.classList.add('point-badge--updated');

        setTimeout(() => {
            this._element?.classList.remove('point-badge--updated');
        }, 400);
    }

    /**
     * 处理点击事件
     * @private
     * @returns {void}
     */
    _onBadgeClick() {
        this._element?.dispatchEvent(new CustomEvent('badge:click', {
            bubbles: true,
            detail: {
                points: this._points,
                level: this._getCurrentLevel()
            }
        }));

        if (typeof this._onClickCallback === 'function') {
            this._onClickCallback(this._points, this._getCurrentLevel());
        }
    }

    /**
     * 销毁组件 - 移除DOM和事件绑定
     * @returns {void}
     */
    destroy() {
        if (this._element) {
            if (this._boundClickHandler) {
                this._element.removeEventListener('click', this._boundClickHandler);
            }
            
            if (this._element.parentNode) {
                this._element.parentNode.removeChild(this._element);
            }
        }
        
        this._element = null;
        this._valueElement = null;
        this._onClickCallback = null;
        this._boundClickHandler = null;
    }
}

/* ========== 组件内联样式 ========== */
const POINT_BADGE_STYLES = `
.point-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border-radius: 9999px;
    padding: 6px 14px;
    background: linear-gradient(
        135deg,
        var(--badge-color, #95A0AA),
        color-mix(in srgb, var(--badge-color, #95A0AA) 80%, white)
    );
    color: #FFFFFF;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    box-shadow:
        0 2px 8px rgba(0, 0, 0, 0.10),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    user-select: none;
}

.point-badge--small {
    padding: 3px 8px;
    font-size: 11px;
    gap: 2px;
    border-radius: 12px;
}

.point-badge--small .point-badge__icon svg {
    width: 12px;
    height: 12px;
}

.point-badge--medium {
    padding: 6px 14px;
    font-size: 13px;
    gap: 4px;
}

.point-badge--medium .point-badge__icon svg {
    width: 15px;
    height: 15px;
}

.point-badge--large {
    padding: 10px 20px;
    font-size: 16px;
    gap: 7px;
    border-radius: 20px;
}

.point-badge--large .point-badge__icon svg {
    width: 20px;
    height: 20px;
}

.point-badge__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.point-badge__icon svg {
    fill: currentColor;
    transition: transform 0.3s ease;
    filter: drop-shadow(0 0 2px rgba(255, 255, 255, 0.3));
}

.point-badge:hover .point-badge__icon svg {
    transform: rotate(15deg) scale(1.1);
}

.point-badge__value {
    line-height: 1.2;
    letter-spacing: 0.3px;
    min-width: 2ch;
    text-align: center;
}

.point-badge__label {
    font-size: 0.75em;
    font-weight: 500;
    opacity: 0.85;
    line-height: 1;
}

.point-badge--level-0 {
    --badge-color: #95A0AA;
}

.point-badge--level-1 {
    --badge-color: #007bff;
}

.point-badge--level-2 {
    --badge-color: #2D9B5E;
}

.point-badge--level-3 {
    --badge-color: #FF9F43;
}

.point-badge--interactive {
    cursor: pointer;
}

.point-badge--interactive::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(
        135deg,
        transparent 40%,
        rgba(255, 255, 255, 0.15) 50%,
        transparent 60%
    );
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
}

.point-badge--interactive:hover::after {
    opacity: 1;
}

.point-badge:hover:not(.point-badge--interactive) {
    transform: translateY(-1px);
    box-shadow:
        0 4px 14px rgba(0, 0, 0, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.point-badge--interactive:hover {
    transform: translateY(-2px) scale(1.03);
    box-shadow:
        0 6px 20px rgba(0, 0, 0, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.point-badge:active {
    transform: scale(0.95);
}

@keyframes pointBadgeShine {
    0% { 
        opacity: 0; 
        transform: translateX(-100%) skewX(-15deg); 
    }
    50% { 
        opacity: 1; 
    }
    100% { 
        opacity: 0; 
        transform: translateX(100%) skewX(-15deg); 
    }
}

.point-badge--updated::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.4),
        transparent
    );
    animation: pointBadgeShine 0.4s ease-out;
    pointer-events: none;
    border-radius: inherit;
}

@media (prefers-reduced-motion: reduce) {
    .point-badge {
        transition-duration: 0.01ms !important;
    }
    
    .point-badge__icon svg {
        transition: none !important;
    }
    
    .point-badge--updated::before {
        animation: none !important;
        display: none;
    }
    
    .point-badge:hover {
        transform: none !important;
    }
}
`;

if (!document.getElementById('point-badge-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'point-badge-styles';
    styleSheet.textContent = POINT_BADGE_STYLES;
    document.head.appendChild(styleSheet);
}

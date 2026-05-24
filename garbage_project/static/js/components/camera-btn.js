/**
 * 拍照按钮组件 - CameraBtn
 * 
 * 功能说明：
 * - 大尺寸圆形拍照按钮，带渐变背景和相机SVG图标
 * - 点击触发隐藏的文件选择器（支持相机拍摄）
 * - 支持normal/active两种状态切换（按下效果）
 * - 移动端显眼设计，PC端适中尺寸
 * - 可通过onClick设置外部回调处理文件选择结果
 * 
 * 技术实现：
 * - 使用隐藏的 <input type="file" accept="image/*" capture="environment">
 * - capture="environment" 属性调用后置摄像头（移动端）
 * - 通过onChange事件获取选中的图片文件
 * 
 * @class CameraBtn
 * @example
 * import { CameraBtn } from './camera-btn.js';
 * const btn = new CameraBtn();
 * btn.render('#cameraContainer');
 * btn.onClick((file) => {
 *     console.log('选中文件:', file.name);
 * });
 */

export class CameraBtn {
    /**
     * 构造函数 - 初始化按钮配置
     * @param {Object} [options={}] - 配置选项
     * @param {'small'|'medium'|'large'} [options.size='large'] - 按钮尺寸规格
     * @param {string} [options.text=''] - 按钮下方文字（可选）
     * @param {boolean} [options.showText=false] - 是否显示下方文字
     * @param {Function} [options.onFileSelect] - 文件选择回调（快捷方式）
     */
    constructor(options = {}) {
        /** @type {string} 按钮尺寸规格 */
        this._size = options.size || 'large';
        
        /** @type {string} 按钮下方辅助文字 */
        this._text = options.text || '拍照识别';
        
        /** @type {boolean} 是否显示下方文字 */
        this._showText = options.showText !== false;
        
        /** @type {Function|null} 外部点击回调（通过onClick设置） */
        this._clickCallback = null;
        
        /** @type {Function|null} 构造时传入的文件选择回调 */
        this._onFileSelect = options.onFileSelect || null;

        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;
        
        /** @type {HTMLInputElement|null} 隐藏的文件输入框引用 */
        this._fileInput = null;
        
        /** @type {string} 当前状态：normal / active */
        this._state = 'normal';
    }

    /**
     * 渲染拍照按钮到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} 按钮根元素引用
     */
    render(containerSelector) {
        // 获取容器元素
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[CameraBtn] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        /* ========== 创建组件根容器 ========== */
        const wrapperEl = document.createElement('div');
        wrapperEl.className = `camera-btn-wrapper camera-btn-wrapper--${this._size}`;

        /* ========== 内部结构 ========== */
        wrapperEl.innerHTML = `
            <!-- 隐藏的文件输入框（核心交互元素） -->
            <input 
                type="file" 
                class="camera-btn__input"
                accept="image/*"
                capture="environment"
                aria-label="选择或拍摄图片"
            />

            <!-- 可见的圆形按钮 -->
            <button 
                type="button"
                class="camera-btn camera-btn--${this._state}"
                aria-label="拍照或选择图片"
            >
                <!-- 外圈装饰环 -->
                <span class="camera-btn__ring"></span>
                
                <!-- 内圈图标容器 -->
                <span class="camera-btn__inner">
                    <!-- 相机SVG图标 -->
                    <svg class="camera-btn__icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z"/>
                        <path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/>
                    </svg>
                </span>
            </button>

            ${this._showText ? `
            <!-- 按钮下方辅助文字 -->
            <span class="camera-btn__text">${this._escapeHtml(this._text)}</span>
            ` : ''}
        `;

        // 将组件插入容器
        container.appendChild(wrapperEl);

        // 缓存DOM引用
        this._element = wrapperEl;
        this._fileInput = wrapperEl.querySelector('.camera-btn__input');
        const visibleBtn = wrapperEl.querySelector('.camera-btn');

        /* ======== 绑定事件 ======== */

        // 1. 点击可见按钮 → 触发隐藏的文件选择器
        visibleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this._handleButtonClick();
        });

        // 2. 文件选择变化事件
        this._fileInput.addEventListener('change', (e) => {
            this._handleFileChange(e);
        });

        // 3. 触摸/鼠标按下效果
        visibleBtn.addEventListener('mousedown', () => this._setActive());
        visibleBtn.addEventListener('mouseup', () => this._setNormal());
        visibleBtn.addEventListener('mouseleave', () => this._setNormal());

        // 触摸事件支持（移动端）
        visibleBtn.addEventListener('touchstart', (e) => {
            this._setActive();
        }, { passive: true });
        
        visibleBtn.addEventListener('touchend', () => {
            this._setNormal();
        }, { passive: true });
        
        visibleBtn.addEventListener('touchcancel', () => {
            this._setNormal();
        }, { passive: true });

        return wrapperEl;
    }

    /**
     * 设置点击回调函数
     * 回调参数为选中的File对象，若取消选择则为null
     * 
     * @param {Function} callback - 回调函数 (file: File|null) => void
     * @returns {void}
     */
    onClick(callback) {
        if (typeof callback === 'function') {
            this._clickCallback = callback;
        } else {
            console.warn('[CameraBtn] onClick需要传入函数类型参数');
        }
    }

    /**
     * 手动触发文件选择（程序化调用）
     * 用于外部按钮或其他事件触发拍照
     * @returns {void}
     */
    trigger() {
        if (this._fileInput) {
            this._fileInput.click();
        }
    }

    /**
     * 设置按钮状态
     * @param {'normal'|'active'} state - 目标状态
     * @returns {void}
     */
    setState(state) {
        if (state === 'active') {
            this._setActive();
        } else {
            this._setNormal();
        }
    }

    /**
     * 获取当前状态
     * @returns {string} 当前状态 ('normal' | 'active')
     */
    getState() {
        return this._state;
    }

    /**
     * 禁用/启用按钮
     * @param {boolean} disabled - 是否禁用
     * @returns {void}
     */
    setDisabled(disabled) {
        if (!this._element) return;

        const btn = this._element.querySelector('.camera-btn');
        if (btn) {
            btn.disabled = disabled;
            btn.classList.toggle('camera-btn--disabled', disabled);
        }

        if (this._fileInput) {
            this._fileInput.disabled = disabled;
        }
    }

    /**
     * 更新按钮下方文字
     * @param {string} newText - 新文字内容
     * @returns {void}
     */
    setText(newText) {
        this._text = newText;
        
        const textEl = this._element?.querySelector('.camera-btn__text');
        if (textEl) {
            textEl.textContent = newText;
        }
    }

    // ==================== 私有方法 ====================

    /**
     * 处理按钮点击事件
     * @private
     * @returns {void}
     */
    _handleButtonClick() {
        // 如果已禁用则不响应
        if (this._fileInput?.disabled) return;

        // 触发隐藏的文件选择器
        this._fileInput?.click();

        // 触发自定义事件（便于外部监听）
        this._element?.dispatchEvent(new CustomEvent('camera:click', {
            bubbles: true
        }));
    }

    /**
     * 处理文件选择变化事件
     * @private
     * @param {Event} event - change事件对象
     * @returns {void}
     */
    _handleFileChange(event) {
        const file = event.target.files[0] || null;

        // 调用构造时传入的回调
        if (typeof this._onFileSelect === 'function') {
            this._onFileSelect(file);
        }

        // 调用通过onClick设置的回调
        if (typeof this._clickCallback === 'function') {
            this._clickCallback(file);
        }

        // 触发DOM自定义事件（携带文件信息）
        this._element?.dispatchEvent(new CustomEvent('camera:fileselect', {
            bubbles: true,
            detail: { file }
        }));

        // 重置input值，允许重复选择同一文件
        if (this._fileInput) {
            this._fileInput.value = '';
        }
    }

    /**
     * 切换到激活态（按下效果）
     * @private
     * @returns {void}
     */
    _setActive() {
        this._state = 'active';
        const btn = this._element?.querySelector('.camera-btn');
        if (btn) {
            btn.classList.remove('camera-btn--normal');
            btn.classList.add('camera-btn--active');
        }
    }

    /**
     * 切换到普通态
     * @private
     * @returns {void}
     */
    _setNormal() {
        this._state = 'normal';
        const btn = this._element?.querySelector('.camera-btn');
        if (btn) {
            btn.classList.remove('camera-btn--active');
            btn.classList.add('camera-btn--normal');
        }
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
        this._fileInput = null;
        this._clickCallback = null;
    }
}

/* ========== 组件内联样式 ========== */
const CAMERA_BTN_STYLES = `
/* ======== CameraBtn 拍照按钮样式 ======== */

/* 按钮外层包装容器 */
.camera-btn-wrapper {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    
    position: relative;
}

/* ========== 尺寸变体 ========== */

/* 小号：用于工具栏内嵌等紧凑场景 */
.camera-btn-wrapper--small .camera-btn {
    width: 48px;
    height: 48px;
}

.camera-btn-wrapper--small .camera-btn__icon {
    width: 20px;
    height: 20px;
}

.camera-btn-wrapper--small .camera-btn__ring {
    width: 54px;
    height: 54px;
}

.camera-btn-wrapper--small .camera-btn__text {
    font-size: 10px;
}

/* 中号：用于常规页面 */
.camera-btn-wrapper--medium .camera-btn {
    width: 64px;
    height: 64px;
}

.camera-btn-wrapper--medium .camera-btn__icon {
    width: 26px;
    height: 26px;
}

.camera-btn-wrapper--medium .camera-btn__ring {
    width: 72px;
    height: 72px;
}

.camera-btn-wrapper--medium .camera-btn__text {
    font-size: 12px;
}

/* 大号（默认）：移动端主操作按钮，显眼设计 */
.camera-btn-wrapper--large .camera-btn {
    width: 80px;
    height: 80px;
}

.camera-btn-wrapper--large .camera-btn__icon {
    width: 32px;
    height: 32px;
}

.camera-btn-wrapper--large .camera-btn__ring {
    width: 90px;
    height: 90px;
}

.camera-btn-wrapper--large .camera-btn__text {
    font-size: 13px;
}

/* ========== 隐藏的文件输入框 ========== */
.camera-btn__input {
    display: none !important;
    position: absolute;
    width: 0;
    height: 0;
    opacity: 0;
    pointer-events: none;
}

/* ========== 可见圆形按钮 ========== */
.camera-btn {
    position: relative;
    
    /* 圆形形状 */
    width: 80px;
    height: 80px;
    border-radius: 50%;
    
    /* 移除默认按钮样式 */
    border: none;
    outline: none;
    
    cursor: pointer;
    
    /* 渐变背景色（使用CSS变量，与主题一致） */
    background: linear-gradient(
        135deg,
        var(--primary, #2D9B5E),
        var(--primary-light, #3DB974)
    );
    
    /* 多层阴影营造立体感 */
    box-shadow:
        0 4px 16px rgba(45, 155, 94, 0.30),
        0 2px 6px rgba(45, 155, 94, 0.18),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
    
    /* 布局：居中显示图标 */
    display: flex;
    align-items: center;
    justify-content: center;
    
    /* 过渡动画 */
    transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
    
    /* 禁止触摸高亮 */
    -webkit-tap-highlight-color: transparent;
    
    z-index: 1;
}

/* ========== 外圈装饰环（脉冲动画）========== */
.camera-btn__ring {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    
    width: 90px;
    height: 90px;
    border-radius: 50%;
    
    border: 2.5px solid var(--primary-light, #3DB974);
    opacity: 0;
    
    /* 脉冲扩散动画 */
    animation: cameraPulseRing 2.5s ease-out infinite;
    
    pointer-events: none;
    z-index: 0;
}

@keyframes cameraPulseRing {
    0% {
        transform: translate(-50%, -50%) scale(0.95);
        opacity: 0.5;
    }
    50% {
        opacity: 0.2;
    }
    100% {
        transform: translate(-50%, -50%) scale(1.15);
        opacity: 0;
    }
}

/* ========== 内圈图标容器 ========== */
.camera-btn__inner {
    position: relative;
    z-index: 2;
    
    display: flex;
    align-items: center;
    justify-content: center;
    
    transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 相机图标SVG */
.camera-btn__icon {
    width: 32px;
    height: 32px;
    fill: white;
    
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.15));
    
    transition: transform 0.25s ease;
}

/* ========== 交互态样式 ========== */

/* 悬停态（PC端主要交互方式） */
.camera-btn:hover:not(:disabled):not(.camera-btn--disabled) {
    transform: scale(1.06) translateY(-2px);
    box-shadow:
        0 8px 28px rgba(45, 155, 94, 0.38),
        0 4px 12px rgba(45, 155, 94, 0.22),
        inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.camera-btn:hover .camera-btn__icon {
    transform: scale(1.08) rotate(-3deg);
}

.camera-btn:hover .camera-btn__ring {
    animation-duration: 1.8s; /* 加快脉冲 */
}

/* 激活态（按下的效果） */
.camera-btn--active,
.camera-btn:active:not(:disabled) {
    transform: scale(0.92);
    box-shadow:
        0 2px 8px rgba(45, 155, 94, 0.25),
        inset 0 2px 6px rgba(0, 0, 0, 0.12);
}

.camera-btn--active .camera-btn__inner {
    transform: scale(0.95);
}

/* 禁用态 */
.camera-btn--disabled,
.camera-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: linear-gradient(135deg, #B8D8C8, #A0CCA0);
    box-shadow: none;
    transform: none;
}

.camera-btn--disabled .camera-btn__ring,
.camera-btn:disabled + .camera-btn__ring {
    animation: none;
    opacity: 0;
}

/* ========== 辅助文字 ========== */
.camera-btn__text {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary, #5A6776);
    text-align: center;
    letter-spacing: 0.3px;
    
    transition: color 0.2s ease;
}

.camera-btn:hover ~ .camera-btn__text {
    color: var(--primary, #2D9B5E);
}

/* ========== PC端适配：尺寸稍小 ========== */
@media (min-width: 768px) {
    .camera-btn-wrapper--large .camera-btn {
        width: 68px;
        height: 68px;
    }
    
    .camera-btn-wrapper--large .camera-btn__icon {
        width: 28px;
        height: 28px;
    }
    
    .camera-btn-wrapper--large .camera-btn__ring {
        width: 78px;
        height: 78px;
    }
    
    .camera-btn-wrapper--large .camera-btn__text {
        font-size: 12px;
    }
}

/* ========== 减弱动效偏好支持 ========== */
@media (prefers-reduced-motion: reduce) {
    .camera-btn,
    .camera-btn__inner,
    .camera-btn__icon,
    .camera-btn__ring {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
    
    .camera-btn:hover {
        transform: none;
    }
}
`;

// 自动注入样式到文档（避免重复注入）
if (!document.getElementById('camera-btn-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'camera-btn-styles';
    styleSheet.textContent = CAMERA_BTN_STYLES;
    document.head.appendChild(styleSheet);
}

// 分类标签组件 — 胶囊形状，四种颜色对应四类垃圾
// TODO: 迁移到BaseComponent基类

export class CategoryTag {
    /**
     * 构造函数 - 初始化配置和颜色映射表
     * @param {Object} [options={}] - 配置选项
     * @param {'small'|'medium'|'large'} [options.size='medium'] - 标签尺寸规格
     * @param {boolean} [options.showIcon=true] - 是否显示图标
     */
    constructor(options = {}) {
        /** @type {string} 标签尺寸规格 */
        this._size = options.size || 'medium';
        
        /** @type {boolean} 是否显示图标 */
        this._showIcon = options.showIcon !== false;
        
        /** @type {HTMLElement|null} 组件根元素引用 */
        this._element = null;

        /**
         * 四种垃圾分类的颜色与图标映射配置
         * 每种分类包含：ID、名称、背景色、文字色、图标SVG
         * 
         * @type {Array<Object>}
         */
        this._categoryConfig = [
            {
                id: 0,
                name: '其他垃圾',
                bgColor: '#8B4513',
                textColor: '#FFFFFF',
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`
            },
            {
                id: 1,
                name: '可回收物',
                bgColor: '#007bff',
                textColor: '#FFFFFF',
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>`
            },
            {
                id: 2,
                name: '厨余垃圾',
                bgColor: '#333333',
                textColor: '#FFFFFF',
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/><path d="M15 13h-2v2h-2v2h2v2h2v-2h2v-2h-2z"/></svg>`
            },
            {
                id: 3,
                name: '有害垃圾',
                bgColor: '#dc3545',
                textColor: '#FFFFFF',
                icon: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 16h2v2h-2zm0-6h2v4h-2z"/></svg>`
            }
        ];
    }

    /**
     * 渲染分类标签到指定容器
     * @param {string|HTMLElement} containerSelector - 容器选择器或DOM元素
     * @returns {HTMLElement} 标签根元素引用
     */
    render(containerSelector) {
        // 获取容器元素
        const container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;

        if (!container) {
            console.error('[CategoryTag] 渲染失败：未找到容器', containerSelector);
            return null;
        }

        // 创建标签根元素（胶囊形状span）
        const tagEl = document.createElement('span');
        tagEl.className = `category-tag category-tag--${this._size}`;
        tagEl.setAttribute('role', 'badge');
        tagEl.setAttribute('data-category-id', '-1'); // 初始无分类

        /* ========== 标签内部结构 ========== */
        // 图标占位 + 文字占位
        tagEl.innerHTML = `
            ${this._showIcon ? '<span class="category-tag__icon"></span>' : ''}
            <span class="category-tag__text">未分类</span>
        `;

        // 将标签插入容器
        container.appendChild(tagEl);

        // 缓存根元素引用
        this._element = tagEl;

        return tagEl;
    }

    /**
     * 更新标签的分类信息和样式
     * 核心方法：根据categoryId切换颜色、图标、文字
     * 
     * @param {number} categoryId - 分类ID（0-3）
     * @param {string} categoryName - 分类名称（可选，不传则使用默认映射名）
     * @returns {void}
     */
    update(categoryId, categoryName) {
        if (!this._element) {
            console.warn('[CategoryTag] update调用失败：组件未渲染');
            return;
        }

        // 边界检查：限制在有效范围
        const safeId = Math.max(0, Math.min(Math.floor(categoryId), 3));

        // 查找对应配置
        const config = this._categoryConfig[safeId];
        
        if (!config) {
            console.warn(`[CategoryTag] 未找到ID=${safeId}的分类配置`);
            return;
        }

        // 确定最终显示的文字（优先使用传入参数）
        const displayName = categoryName || config.name;

        /* ======== 更新data属性（供CSS选择器使用）======== */
        this._element.setAttribute('data-category-id', String(safeId));

        /* ======== 更新背景色和文字色 ======== */
        this._element.style.background = config.bgColor;
        this._element.style.color = config.textColor;

        /* ======== 更新图标内容 ======== */
        if (this._showIcon) {
            const iconEl = this._element.querySelector('.category-tag__icon');
            if (iconEl) {
                iconEl.innerHTML = config.icon;
            }
        }

        /* ======== 更新文字内容 ======== */
        const textEl = this._element.querySelector('.category-tag__text');
        if (textEl) {
            textEl.textContent = displayName;
        }

        /* ======== 触发微动画效果 ======== */
        this._playUpdateAnimation();
    }

    /**
     * 通过分类名称更新（模糊匹配模式）
     * 当只有名称没有ID时可用此方法自动查找对应ID
     * 
     * @param {string} name - 分类名称（如'可回收物'、'有害垃圾'等）
     * @returns {boolean} 是否成功匹配并更新
     */
    updateByName(name) {
        if (!name || typeof name !== 'string') return false;

        // 在配置表中查找匹配项
        const config = this._categoryConfig.find(
            c => c.name === name.trim() || c.name.includes(name.trim())
        );

        if (config) {
            this.update(config.id, config.name);
            return true;
        }

        console.warn(`[CategoryTag] 未找到名称"${name}"对应的分类`);
        return false;
    }

    /**
     * 获取当前分类ID
     * @returns {number} 当前分类ID（未设置返回-1）
     */
    getCategoryId() {
        if (!this._element) return -1;
        const id = this._element.getAttribute('data-category-id');
        return id !== null ? parseInt(id, 10) : -1;
    }

    /**
     * 获取当前分类名称
     * @returns {string} 当前分类名称
     */
    getCategoryName() {
        const id = this.getCategoryId();
        if (id >= 0 && id < this._categoryConfig.length) {
            return this._categoryConfig[id].name;
        }
        return '未分类';
    }

    /**
     * 设置标签尺寸
     * @param {'small'|'medium'|'large'} size - 目标尺寸
     * @returns {void}
     */
    setSize(size) {
        if (!this._element) return;

        // 移除所有尺寸class
        this._element.classList.remove(
            'category-tag--small',
            'category-tag--medium',
            'category-tag--large'
        );

        // 添加新的尺寸class
        this._size = size || 'medium';
        this._element.classList.add(`category-tag--${this._size}`);
    }

    /**
     * 播放更新时的微动画效果
     * @private
     * @returns {void}
     */
    _playUpdateAnimation() {
        if (!this._element) return;

        // 移除旧动画类
        this._element.classList.remove('category-tag--updated');

        // 触发重排以重新启动动画
        void this._element.offsetHeight;

        // 添加动画类
        this._element.classList.add('category-tag--updated');

        // 动画结束后清理
        const handler = () => {
            this._element.removeEventListener('animationend', handler);
            this._element.classList.remove('category-tag--updated');
        };
        this._element.addEventListener('animationend', handler);
    }

    /**
     * 销毁组件 - 移除DOM
     * @returns {void}
     */
    destroy() {
        if (this._element && this._element.parentNode) {
            this._element.parentNode.removeChild(this._element);
        }
        this._element = null;
    }
}

/* ========== 组件内联样式 ========== */
const CATEGORY_TAG_STYLES = `
/* ======== CategoryTag 分类标签样式 ======== */
.category-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    
    border-radius: 9999px; /* 完全圆角胶囊形 */
    padding: 5px 14px;
    
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.3px;
    
    white-space: nowrap;
    user-select: none;
    vertical-align: middle;
    
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.10);
    
    /* 默认灰色状态（未设置分类时） */
    background: #95A0AA;
    color: #FFFFFF;
}

/* ========== 尺寸变体 ========== */

/* 小号标签：用于列表内嵌等紧凑场景 */
.category-tag--small {
    padding: 3px 10px;
    font-size: 10px;
    gap: 3px;
}

.category-tag--small .category-tag__icon svg {
    width: 12px;
    height: 12px;
}

/* 中号标签（默认）：用于卡片标题旁 */
.category-tag--medium {
    padding: 5px 14px;
    font-size: 12px;
    gap: 5px;
}

.category-tag--medium .category-tag__icon svg {
    width: 14px;
    height: 14px;
}

/* 大号标签：用于页面主标题区域 */
.category-tag--large {
    padding: 8px 20px;
    font-size: 14px;
    gap: 7px;
}

.category-tag--large .category-tag__icon svg {
    width: 18px;
    height: 18px;
}

/* ========== 图标容器 ========== */
.category-tag__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    
    flex-shrink: 0;
}

.category-tag__icon svg {
    width: 14px;
    height: 14px;
    fill: currentColor;
    
    transition: transform 0.25s ease;
}

/* 悬停时图标轻微旋转 */
.category-tag:hover .category-tag__icon svg {
    transform: rotate(-8deg) scale(1.1);
}

/* ========== 文字部分 ========== */
.category-tag__text {
    line-height: 1.2;
}

/* ========== 分类特定样式（通过data属性选择器）======== */

/* ID=0 其他垃圾 - 棕色系 */
.category-tag[data-category-id="0"] {
    background: #8B4513;
    color: #FFFFFF;
}

/* ID=1 可回收物 - 蓝色系 */
.category-tag[data-category-id="1"] {
    background: #007bff;
    color: #FFFFFF;
}

/* ID=2 厨余垃圾 - 灰黑色系 */
.category-tag[data-category-id="2"] {
    background: #333333;
    color: #FFFFFF;
}

/* ID=3 有害垃圾 - 红色系 */
.category-tag[data-category-id="3"] {
    background: #dc3545;
    color: #FFFFFF;
}

/* ========== 交互态 ========== */
.category-tag:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
}

.category-tag:active {
    transform: scale(0.95);
}

/* ========== 更新动画 ========== */
@keyframes categoryTagPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.08); }
    100% { transform: scale(1); }
}

.category-tag--updated {
    animation: categoryTagPulse 0.35s ease;
}

/* ========== 减弱动效偏好支持 ========== */
@media (prefers-reduced-motion: reduce) {
    .category-tag {
        transition-duration: 0.01ms !important;
    }
    
    .category-tag--updated {
        animation: none !important;
    }
    
    .category-tag:hover .category-tag__icon svg {
        transform: none;
    }
}
`;

// 自动注入样式到文档（避免重复注入）
if (!document.getElementById('category-tag-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'category-tag-styles';
    styleSheet.textContent = CATEGORY_TAG_STYLES;
    document.head.appendChild(styleSheet);
}

/**
 * SearchSuggest - 搜索联想下拉组件
 *
 * 功能说明：
 * - 输入时实时请求 /api/search/suggest 接口获取联想结果
 * - 输入1个字符即触发联想（拼音1字母也可匹配）
 * - 防抖处理：300ms 内不重复请求
 * - 点击联想项自动填充搜索框并执行搜索
 * - 点击外部区域自动关闭下拉
 * - 支持拼音匹配高亮显示
 *
 * @class SearchSuggest
 */

export class SearchSuggest {
    constructor(options = {}) {
        this._input = typeof options.input === 'string'
            ? document.querySelector(options.input)
            : options.input;
        this._apiBase = options.apiBase || '';
        this._onSelect = options.onSelect || null;
        this._minChars = options.minChars || 1;
        this._debounceMs = options.debounceMs || 300;

        this._dropdown = null;
        this._debounceTimer = null;
        this._currentQuery = '';
        this._isVisible = false;
        this._boundHandlers = {};
    }

    init() {
        if (!this._input) {
            console.error('[SearchSuggest] 输入框元素不存在');
            return;
        }

        this._createDropdown();
        this._bindEvents();

        console.log('[SearchSuggest] 初始化完成');
    }

    destroy() {
        clearTimeout(this._debounceTimer);

        if (this._dropdown && this._dropdown.parentNode) {
            this._dropdown.parentNode.removeChild(this._dropdown);
        }

        if (this._input) {
            this._input.removeEventListener('input', this._boundHandlers.input);
            this._input.removeEventListener('focus', this._boundHandlers.focus);
            this._input.removeEventListener('keydown', this._boundHandlers.keydown);
        }

        document.removeEventListener('click', this._boundHandlers.documentClick);

        this._dropdown = null;
        this._boundHandlers = {};

        console.log('[SearchSuggest] 已销毁');
    }

    show() {
        if (this._dropdown) {
            this._dropdown.classList.add('search-suggest--visible');
            this._isVisible = true;
        }
    }

    hide() {
        if (this._dropdown) {
            this._dropdown.classList.remove('search-suggest--visible');
            this._isVisible = false;
        }
    }

    isVisible() {
        return this._isVisible;
    }

    _createDropdown() {
        this._dropdown = document.createElement('div');
        this._dropdown.className = 'search-suggest';
        this._dropdown.setAttribute('role', 'listbox');
        this._dropdown.setAttribute('aria-label', '搜索建议');

        const parent = this._input.parentNode;
        if (parent) {
            parent.style.position = 'relative';
            parent.appendChild(this._dropdown);
        }
    }

    _bindEvents() {
        this._boundHandlers.input = () => this._handleInput();
        this._boundHandlers.focus = () => this._handleFocus();
        this._boundHandlers.keydown = (e) => this._handleKeydown(e);
        this._boundHandlers.documentClick = (e) => this._handleDocumentClick(e);

        this._input.addEventListener('input', this._boundHandlers.input);
        this._input.addEventListener('focus', this._boundHandlers.focus);
        this._input.addEventListener('keydown', this._boundHandlers.keydown);
        document.addEventListener('click', this._boundHandlers.documentClick);
    }

    _handleInput() {
        const query = this._input.value.trim();
        this._currentQuery = query;

        clearTimeout(this._debounceTimer);

        if (!query || query.length < this._minChars) {
            this.hide();
            return;
        }

        this._debounceTimer = setTimeout(() => {
            this._fetchSuggestions(query);
        }, this._debounceMs);
    }

    _handleFocus() {
        const query = this._input.value.trim();
        if (query && query.length >= this._minChars && !this._isVisible) {
            this._fetchSuggestions(query);
        }
    }

    _handleKeydown(e) {
        if (!this._isVisible || !this._dropdown) return;

        const items = this._dropdown.querySelectorAll('.search-suggest__item');
        const activeItem = this._dropdown.querySelector('.search-suggest__item--active');
        let index = -1;

        items.forEach((item, i) => {
            if (item === activeItem) index = i;
        });

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                if (activeItem) activeItem.classList.remove('search-suggest__item--active');
                index = (index + 1) % items.length;
                items[index]?.classList.add('search-suggest__item--active');
                items[index]?.scrollIntoView({ block: 'nearest' });
                break;

            case 'ArrowUp':
                e.preventDefault();
                if (activeItem) activeItem.classList.remove('search-suggest__item--active');
                index = index <= 0 ? items.length - 1 : index - 1;
                items[index]?.classList.add('search-suggest__item--active');
                items[index]?.scrollIntoView({ block: 'nearest' });
                break;

            case 'Enter':
                if (activeItem) {
                    e.preventDefault();
                    activeItem.click();
                }
                break;

            case 'Escape':
                e.preventDefault();
                this.hide();
                this._input.blur();
                break;
        }
    }

    _handleDocumentClick(e) {
        if (!this._isVisible) return;

        const parent = this._input.parentNode;
        if (parent && !parent.contains(e.target)) {
            this.hide();
        }
    }

    async _fetchSuggestions(query) {
        try {
            const url = `${this._apiBase}/api/search/suggest?query=${encodeURIComponent(query)}&top_k=8`;
            const response = await fetch(url);

            if (!response.ok) return;

            const data = await response.json();
            const suggestions = data.suggestions || [];

            if (suggestions.length > 0 && this._currentQuery === query) {
                this._renderSuggestions(suggestions, query);
                this.show();
            } else {
                this.hide();
            }
        } catch (err) {
            console.warn('[SearchSuggest] 获取联想失败:', err);
        }
    }

    _renderSuggestions(suggestions, query) {
        if (!this._dropdown) return;

        const html = suggestions.map((item, index) => {
            const label = item.label || '';
            const category = item.category_name || '';
            const matchType = item.match_type || 'text';
            const typeBadge = matchType === 'pinyin' ? '<span class="search-suggest__pinyin-badge">拼音</span>' : '';

            return `
                <div class="search-suggest__item"
                     data-index="${index}"
                     data-label="${label}"
                     role="option"
                     tabindex="-1">
                    <span class="search-suggest__label">${this._highlightMatch(label, query)}</span>
                    <span class="search-suggest__category">${category}</span>
                    ${typeBadge}
                </div>
            `;
        }).join('');

        this._dropdown.innerHTML = html;

        this._dropdown.querySelectorAll('.search-suggest__item').forEach((itemEl) => {
            itemEl.addEventListener('click', () => {
                const label = itemEl.dataset.label;
                if (this._input) {
                    this._input.value = label;
                }
                this.hide();

                if (typeof this._onSelect === 'function') {
                    this._onSelect(label);
                }
            });
        });
    }

    _highlightMatch(text, query) {
        if (!query) return text;

        const isPinyin = /^[a-z]+$/.test(query);
        if (isPinyin) return text;

        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escaped})`, 'gi');
        return text.replace(regex, '<mark class="search-suggest__highlight">$1</mark>');
    }
}

const SEARCH_SUGGEST_STYLES = `
.search-suggest {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    background: var(--card-bg, #fff);
    border-radius: 0 0 var(--radius-lg, 12px) var(--radius-lg, 12px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    max-height: 320px;
    overflow-y: auto;
    opacity: 0;
    visibility: hidden;
    transform: translateY(-4px);
    transition: all 0.2s ease;
    border-top: 1px solid var(--border, #e8ecf0);
}

.search-suggest--visible {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}

.search-suggest__item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    cursor: pointer;
    transition: background 0.15s ease;
    border-bottom: 1px solid var(--border-light, #f0f2f5);
}

.search-suggest__item:last-child {
    border-bottom: none;
}

.search-suggest__item:hover,
.search-suggest__item--active {
    background: var(--primary-light-bg, rgba(45, 155, 94, 0.08));
}

.search-suggest__label {
    flex: 1;
    font-size: 0.9rem;
    color: var(--text-primary, #1a2332);
}

.search-suggest__highlight {
    background: rgba(45, 155, 94, 0.2);
    color: var(--primary, #2D9B5E);
    padding: 0 1px;
    border-radius: 2px;
}

.search-suggest__category {
    font-size: 0.75rem;
    color: var(--text-secondary, #5A6776);
    white-space: nowrap;
}

.search-suggest__pinyin-badge {
    font-size: 0.65rem;
    padding: 1px 5px;
    border-radius: 3px;
    background: rgba(45, 155, 94, 0.12);
    color: var(--primary, #2D9B5E);
    white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
    .search-suggest {
        transition-duration: 0.01ms !important;
    }
}
`;

if (!document.getElementById('search-suggest-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'search-suggest-styles';
    styleSheet.textContent = SEARCH_SUGGEST_STYLES;
    document.head.appendChild(styleSheet);
}

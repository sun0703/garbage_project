// 搜索建议下拉组件
// TODO: 迁移到BaseComponent基类

import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';

const DEBOUNCE_MS = 300;   // 防抖间隔
const MIN_CHARS = 2;       // 最少输入几个字才触发联想
const MAX_ITEMS = 8;       // 下拉最多显示几条
const SEARCH_HISTORY_KEY = 'ecosort_search_history';
const MAX_SEARCH_HISTORY = 20;
const MAX_DISPLAY_HISTORY = 5;

export class SearchSuggest {
    constructor(options = {}) {
        this.inputEl = options.inputEl || null;
        this.onSelect = options.onSelect || null;
        this._dropdown = null;
        this._items = [];
        this._highlightIndex = -1;
        this._debounceTimer = null;
        this._boundHandlers = {};
        this._visible = false;
        this._styleInjected = false;
        /* F-2.2.4 搜索历史缓存 */
        this._historyCache = [];

        if (this.inputEl) {
            this._init();
        }
    }

    _init() {
        if (!this.inputEl) return;
        this._injectStyle();
        this._createDropdown();
        this._bindEvents();
        /* 初始化时预加载搜索历史 */
        this._loadSearchHistory();
    }

    _injectStyle() {
        if (this._styleInjected) return;
        const styleId = 'search-suggest-style';
        if (document.getElementById(styleId)) {
            this._styleInjected = true;
            return;
        }
        const styleEl = document.createElement('style');
        styleEl.id = styleId;
        styleEl.textContent = [
            '.search-suggest {',
            '  position: absolute;',
            '  top: 100%;',
            '  left: 0;',
            '  right: 0;',
            '  z-index: 1000;',
            '  margin-top: 4px;',
            '  background: #fff;',
            '  border-radius: 12px;',
            '  box-shadow: 0 4px 20px rgba(45, 155, 94, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06);',
            '  overflow: hidden;',
            '  opacity: 0;',
            '  transform: translateY(-8px);',
            '  transition: opacity 0.2s ease, transform 0.2s ease;',
            '  pointer-events: none;',
            '}',
            '.search-suggest.visible {',
            '  opacity: 1;',
            '  transform: translateY(0);',
            '  pointer-events: auto;',
            '}',
            '.search-suggest__item {',
            '  display: flex;',
            '  align-items: center;',
            '  padding: 10px 16px;',
            '  cursor: pointer;',
            '  transition: background-color 0.15s ease;',
            '  border-bottom: 1px solid #f0f2f5;',
            '  gap: 12px;',
            '}',
            '.search-suggest__item:last-child {',
            '  border-bottom: none;',
            '}',
            '.search-suggest__item:hover,',
            '.search-suggest__item.highlighted {',
            '  background: linear-gradient(135deg, rgba(45, 155, 94, 0.06), rgba(78, 205, 196, 0.04));',
            '}',
            '.search-suggest__item-icon {',
            '  flex-shrink: 0;',
            '  width: 32px;',
            '  height: 32px;',
            '  border-radius: 8px;',
            '  display: flex;',
            '  align-items: center;',
            '  justify-content: center;',
            '  font-size: 14px;',
            '  background: linear-gradient(135deg, rgba(45, 155, 94, 0.08), rgba(78, 205, 196, 0.06));',
            '  color: var(--primary, #2D9B5E);',
            '}',
            '.search-suggest__item-info {',
            '  flex: 1;',
            '  min-width: 0;',
            '}',
            '.search-suggest__item-label {',
            '  font-size: 14px;',
            '  font-weight: 500;',
            '  color: #1a1a2e;',
            '  white-space: nowrap;',
            '  overflow: hidden;',
            '  text-overflow: ellipsis;',
            '}',
            '.search-suggest__item-category {',
            '  font-size: 12px;',
            '  color: #8896a4;',
            '  margin-top: 2px;',
            '}',
            '.search-suggest__item-score {',
            '  flex-shrink: 0;',
            '  font-size: 13px;',
            '  font-weight: 600;',
            '  color: var(--primary, #2D9B5E);',
            '  background: rgba(45, 155, 94, 0.08);',
            '  padding: 2px 8px;',
            '  border-radius: 10px;',
            '}',
            '.search-suggest__empty {',
            '  padding: 20px 16px;',
            '  text-align: center;',
            '  color: #95A0AA;',
            '  font-size: 13px;',
            '}',

            /* ====== F-2.2.4 搜索历史区域样式 ====== */

            /* 搜索历史区域容器 - 与建议列表用分割线区分 */
            '.suggest-history-section {',
            '  border-bottom: 2px solid #f0f2f5;',
            '  background: linear-gradient(135deg, rgba(250, 252, 250, 0.95), rgba(248, 250, 248, 0.9));',
            '}',

            /* 历史区域头部 */
            '.suggest-history-header {',
            '  display: flex;',
            '  align-items: center;',
            '  justify-content: space-between;',
            '  padding: 10px 16px 6px;',
            '  gap: 8px;',
            '}',

            /* 历史标题文字 */
            '.suggest-history-title {',
            '  font-size: 12px;',
            '  font-weight: 600;',
            '  color: #8896a4;',
            '  letter-spacing: 0.02em;',
            '}',

            /* 清空历史按钮 */
            '.suggest-history-clear-btn {',
            '  font-size: 11px;',
            '  color: #C0C8D0;',
            '  background: none;',
            '  border: none;',
            '  padding: 3px 8px;',
            '  border-radius: 4px;',
            '  cursor: pointer;',
            '  transition: color 0.15s, background 0.15s;',
            '}',

            '.suggest-history-clear-btn:hover {',
            '  color: #E74C3C;',
            '  background: rgba(231, 76, 60, 0.08);',
            '}',

            /* 搜索历史列表项 - 移动端触摸友好（≥44px高度） */
            '.suggest-history-item {',
            '  display: flex;',
            '  align-items: center;',
            '  gap: 10px;',
            '  padding: 11px 16px;',           /* 确保最小44px点击区域 */
            '  border-bottom: 1px solid #f7f8fa;',
            '  cursor: pointer;',
            '  transition: background-color 0.15s ease;',
            '}',

            '.suggest-history-item:last-child {',
            '  border-bottom: none;',
            '}',

            '.suggest-history-item:hover {',
            '  background: rgba(45, 155, 94, 0.04);',
            '}',

            /* 历史记录图标（时钟图标） */
            '.suggest-history-icon {',
            '  flex-shrink: 0;',
            '  width: 28px;',
            '  height: 28px;',
            '  border-radius: 6px;',
            '  display: flex;',
            '  align-items: center;',
            '  justify-content: center;',
            '  font-size: 13px;',
            '  background: rgba(149, 160, 170, 0.08);',
            '  color: #95A0AA;',
            '}',

            /* 历史记录文本 */
            '.suggest-history-text {',
            '  flex: 1;',
            '  font-size: 13px;',
            '  color: #333;',
            '  overflow: hidden;',
            '  text-overflow: ellipsis;',
            '  white-space: nowrap;',
            '}',

            /* 删除单条历史按钮（×） */
            '.suggest-history-del {',
            '  flex-shrink: 0;',
            '  width: 22px;',
            '  height: 22px;',
            '  border: none;',
            '  border-radius: 50%;',
            '  background: transparent;',
            '  color: #C0C8D0;',
            '  font-size: 14px;',
            '  cursor: pointer;',
            '  display: flex;',
            '  align-items: center;',
            '  justify-content: center;',
            '  opacity: 0;                    /* 默认隐藏，hover时显示 */',
            '  transition: opacity 0.15s, color 0.15s, background 0.15s;',
            '}',

            /* hover历史项时显示删除按钮 */
            '.suggest-history-item:hover .suggest-history-del {',
            '  opacity: 1;',
            '}',

            '.suggest-history-del:hover {',
            '  color: #E74C3C;',
            '  background: rgba(231, 76, 60, 0.1);',
            '}',

            /* 分割线（历史与建议之间） */
            '.suggest-divider {',
            '  height: 2px;',
            '  background: linear-gradient(90deg, transparent, #e8ecf0, transparent);',
            '}',
        ].join('\n');
        document.head.appendChild(styleEl);
        this._styleInjected = true;
    }

    _createDropdown() {
        this._dropdown = document.createElement('div');
        this._dropdown.className = 'search-suggest';
        this._dropdown.setAttribute('role', 'listbox');
        this._dropdown.setAttribute('aria-label', '搜索建议');
        const parent = this.inputEl.parentElement;
        if (parent) {
            parent.style.position = 'relative';
            parent.appendChild(this._dropdown);
        }
    }

    _bindEvents() {
        this._boundHandlers.input = () => this._onInput();
        this._boundHandlers.keydown = (e) => this._onKeydown(e);
        this._boundHandlers.focus = () => this._onFocus();
        this._boundHandlers.blur = (e) => {
            setTimeout(() => this._close(), 150);
        };
        this.inputEl.addEventListener('input', this._boundHandlers.input);
        this.inputEl.addEventListener('keydown', this._boundHandlers.keydown);
        this.inputEl.addEventListener('focus', this._boundHandlers.focus);
        this.inputEl.addEventListener('blur', this._boundHandlers.blur);

        this._boundHandlers.documentClick = (e) => {
            if (!this._dropdown?.contains(e.target) && e.target !== this.inputEl) {
                this._close();
            }
        };
        document.addEventListener('click', this._boundHandlers.documentClick);
    }

    /**
     * 输入事件处理（防抖）
     * 当输入内容达到最小字符数时触发联想请求
     * @private
     */
    _onInput() {
        const value = this.inputEl.value.trim();

        /* 输入为空时显示搜索历史（而非关闭下拉框） */
        if (value.length === 0) {
            this._showHistoryOnly();
            return;
        }

        if (value.length < MIN_CHARS) {
            this._close();
            return;
        }
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => this._fetchSuggestions(value), DEBOUNCE_MS);
    }

    async _fetchSuggestions(query) {
        try {
            const response = await api.search(query);
            const results = response.results || [];
            this._items = results.slice(0, MAX_ITEMS);

            /* F-2.2.4 渲染结果时在顶部附加搜索历史 */
            if (this._items.length > 0 || this._historyCache.length > 0) {
                this._renderItemsWithHistory();
                this._open();
            } else {
                this._renderEmpty();
                this._open();
            }
        } catch (_err) {
            this._close();
        }
    }

    /**
     * 渲染建议列表 + 搜索历史区域（F-2.2.4增强）
     * 在API返回的建议列表顶部展示最近搜索历史
     * @private
     */
    _renderItemsWithHistory() {
        let html = '';

        /* 如果有搜索历史，先渲染历史区域 */
        if (this._historyCache.length > 0) {
            html += this._buildHistoryHTML();
            html += '<div class="suggest-divider"></div>';
        }

        /* 渲染API返回的搜索建议 */
        if (this._items.length > 0) {
            html += this._items.map((item, idx) => {
                const label = item.match_label || item.label || '';
                const category = item.category || '';
                const score = item.similarity_score != null ? Math.round(item.similarity_score) : '';
                const icon = item.bin_icon || '🗑';
                return `<div class="search-suggest__item" role="option" data-index="${idx}" tabindex="-1">
                    <div class="search-suggest__item-icon">${icon}</div>
                    <div class="search-suggest__item-info">
                        <div class="search-suggest__item-label">${escapeHtml(label)}</div>
                        <div class="search-suggest__item-category">${escapeHtml(category)}</div>
                    </div>
                    ${score ? `<div class="search-suggest__item-score">${score}%</div>` : ''}
                </div>`;
            }).join('');
        } else {
            /* 无建议结果时显示提示 */
            html += '<div class="search-suggest__empty">未找到相关建议</div>';
        }

        this._dropdown.innerHTML = html;
        this._bindItemEvents();
        this._bindHistoryEvents();          /* 绑定历史区域事件 */
    }

    /**
     * 构建搜索历史区域的HTML结构
     *
     * @returns {string} 历史区域的HTML字符串
     * @private
     */
    _buildHistoryHTML() {
        /* 限制显示数量 */
        const displayItems = this._historyCache.slice(0, MAX_DISPLAY_HISTORY);

        const itemsHTML = displayItems.map(q => `
            <div class="suggest-history-item" data-query="${escapeHtml(q)}" role="button" tabindex="0">
                <span class="suggest-history-icon">🕐</span>
                <span class="suggest-history-text">${escapeHtml(q)}</span>
                <button class="suggest-history-del" data-del="${escapeHtml(q)}" aria-label="删除此条历史">✕</button>
            </div>
        `).join('');

        return `
            <div class="suggest-history-section">
                <div class="suggest-history-header">
                    <span class="suggest-history-title">🕐 最近搜索</span>
                    <button class="suggest-history-clear-btn" id="suggestClearHistoryBtn">清空</button>
                </div>
                <div class="suggest-history-list">${itemsHTML}</div>
            </div>
        `;
    }

    /**
     * 仅显示搜索历史（输入框聚焦但未输入内容时）
     * @private
     */
    _showHistoryOnly() {
        if (this._historyCache.length === 0) {
            this._close();
            return;
        }
        this._dropdown.innerHTML = this._buildHistoryHTML();
        this._bindHistoryEvents();
        this._open();
    }

    /**
     * 绑定搜索历史区域的事件监听
     * 包括：点击历史项执行搜索、删除单条、清空全部
     * @private
     */
    _bindHistoryEvents() {
        if (!this._dropdown) return;

        /* 使用事件委托处理所有历史相关点击 */
        this._dropdown.addEventListener('click', (e) => {
            /* 删除单条历史 */
            const delBtn = e.target.closest('.suggest-history-del');
            if (delBtn) {
                e.stopPropagation();
                const q = delBtn.dataset.del;
                this._removeHistoryItem(q);
                return;
            }

            /* 点击历史项 */
            const historyItem = e.target.closest('.suggest-history-item');
            if (historyItem) {
                e.stopPropagation();
                const q = historyItem.dataset.query;
                if (q && this.inputEl) {
                    this.inputEl.value = q;
                    this._close();
                    if (typeof this.onSelect === 'function') {
                        this.onSelect(q);
                    }
                }
                return;
            }

            /* 清空全部历史 */
            const clearBtn = e.target.closest('#suggestClearHistoryBtn');
            if (clearBtn) {
                e.stopPropagation();
                this._clearAllHistory();
                return;
            }
        });
    }

    /* ---- 搜索历史数据操作 ---- */

    /**
     * 从localStorage加载搜索历史到内存缓存
     * @private
     */
    _loadSearchHistory() {
        try {
            const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
            this._historyCache = raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.warn('[SearchSuggest] 加载搜索历史失败:', e);
            this._historyCache = [];
        }
    }

    /**
     * 保存搜索词到历史记录（供外部调用）
     * 自动去重，最新在前，最多保留MAX_SEARCH_HISTORY条
     *
     * @param {string} query - 搜索关键词
     */
    saveToHistory(query) {
        if (!query || !query.trim()) return;
        const q = query.trim();

        /* 去重：移除已存在的相同关键词 */
        this._historyCache = this._historyCache.filter(item => item !== q);

        /* 新记录插入到数组头部 */
        this._historyCache.unshift(q);

        /* 容量控制：超出上限时截断尾部 */
        if (this._historyCache.length > MAX_SEARCH_HISTORY) {
            this._historyCache = this._historyCache.slice(0, MAX_SEARCH_HISTORY);
        }

        /* 持久化写入localStorage */
        try {
            localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(this._historyCache));
        } catch (e) {
            console.warn('[SearchSuggest] 保存搜索历史失败:', e);
        }
    }

    /**
     * 删除单条搜索历史
     *
     * @param {string} query - 要删除的关键词
     * @private
     */
    _removeHistoryItem(query) {
        this._historyCache = this._historyCache.filter(item => item !== query);

        try {
            localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(this._historyCache));
        } catch (e) {
            console.warn('[SearchSuggest] 删除搜索历史失败:', e);
        }

        /* 重新渲染当前视图 */
        if (this._visible) {
            const value = this.inputEl?.value.trim() || '';
            if (value.length === 0) {
                this._showHistoryOnly();
            } else if (value.length >= MIN_CHARS) {
                this._renderItemsWithHistory();
            } else {
                this._close();
            }
        }
    }

    /**
     * 清空全部搜索历史
     * @private
     */
    _clearAllHistory() {
        this._historyCache = [];

        try {
            localStorage.removeItem(SEARCH_HISTORY_KEY);
        } catch (e) {
            console.warn('[SearchSuggest] 清空搜索历史失败:', e);
        }

        /* 关闭或重新渲染 */
        if (this._visible) {
            const value = this.inputEl?.value.trim() || '';
            if (value.length >= MIN_CHARS) {
                /* 有输入内容时仅移除历史区，保留建议列表 */
                this._renderItems();
            } else {
                this._close();
            }
        }
    }

    _renderItems() {
        const html = this._items.map((item, idx) => {
            const label = item.match_label || item.label || '';
            const category = item.category || '';
            const score = item.similarity_score != null ? Math.round(item.similarity_score) : '';
            const icon = item.bin_icon || '🗑';
            return `<div class="search-suggest__item" role="option" data-index="${idx}" tabindex="-1">
                <div class="search-suggest__item-icon">${icon}</div>
                <div class="search-suggest__item-info">
                    <div class="search-suggest__item-label">${escapeHtml(label)}</div>
                    <div class="search-suggest__item-category">${escapeHtml(category)}</div>
                </div>
                ${score ? `<div class="search-suggest__item-score">${score}%</div>` : ''}
            </div>`;
        }).join('');
        this._dropdown.innerHTML = html;
        this._bindItemEvents();
    }

    _renderEmpty() {
        this._dropdown.innerHTML = '<div class="search-suggest__empty">未找到相关建议</div>';
    }

    _bindItemEvents() {
        const items = this._dropdown.querySelectorAll('.search-suggest__item');
        items.forEach((el) => {
            el.addEventListener('click', () => {
                const idx = parseInt(el.dataset.index, 10);
                this._selectItem(idx);
            });
            el.addEventListener('mouseenter', () => {
                this._setHighlight(parseInt(el.dataset.index, 10));
            });
        });
    }

    _onKeydown(e) {
        if (!this._visible) return;
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this._moveHighlight(1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this._moveHighlight(-1);
                break;
            case 'Enter':
                e.preventDefault();
                if (this._highlightIndex >= 0 && this._highlightIndex < this._items.length) {
                    this._selectItem(this._highlightIndex);
                } else {
                    this._close();
                }
                break;
            case 'Escape':
                e.preventDefault();
                this._close();
                this.inputEl.blur();
                break;
        }
    }

    _moveHighlight(delta) {
        const maxIndex = this._items.length - 1;
        let newIndex = this._highlightIndex + delta;
        if (newIndex < 0) newIndex = maxIndex;
        if (newIndex > maxIndex) newIndex = 0;
        this._setHighlight(newIndex);
    }

    _setHighlight(index) {
        this._highlightIndex = index;
        const items = this._dropdown?.querySelectorAll('.search-suggest__item');
        items?.forEach((el, i) => {
            el.classList.toggle('highlighted', i === index);
            if (i === index) {
                el.scrollIntoView({ block: 'nearest' });
            }
        });
    }

    _selectItem(index) {
        const item = this._items[index];
        if (!item) return;
        const keyword = item.match_label || item.label || '';
        this.inputEl.value = keyword;
        this._close();
        if (typeof this.onSelect === 'function') {
            this.onSelect(keyword);
        }
    }

    _open() {
        if (!this._dropdown) return;
        this._visible = true;
        this._highlightIndex = -1;
        this._dropdown.classList.add('visible');
    }

    _close() {
        if (!this._dropdown) return;
        this._visible = false;
        this._highlightIndex = -1;
        this._dropdown.classList.remove('visible');
    }

    /**
     * 聚焦事件处理（F-2.2.4增强）
     * 聚焦时如果有缓存的历史记录则立即显示
     * @private
     */
    _onFocus() {
        const value = this.inputEl.value.trim();

        /* 无输入内容时显示搜索历史 */
        if (value.length === 0 && this._historyCache.length > 0) {
            this._showHistoryOnly();
            return;
        }

        /* 有足够输入且有缓存建议时恢复显示 */
        if (value.length >= MIN_CHARS && this._items.length > 0) {
            this._open();
        }
    }

    destroy() {
        clearTimeout(this._debounceTimer);
        if (this.inputEl) {
            this.inputEl.removeEventListener('input', this._boundHandlers.input);
            this.inputEl.removeEventListener('keydown', this._boundHandlers.keydown);
            this.inputEl.removeEventListener('focus', this._boundHandlers.focus);
            this.inputEl.removeEventListener('blur', this._boundHandlers.blur);
        }
        document.removeEventListener('click', this._boundHandlers.documentClick);
        if (this._dropdown && this._dropdown.parentNode) {
            this._dropdown.parentNode.removeChild(this._dropdown);
        }
        this._dropdown = null;
        this._items = [];
        this._historyCache = [];
        this._visible = false;
        this._debounceTimer = null;
        this._boundHandlers = {};
    }
}

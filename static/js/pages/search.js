// 搜索结果页 — 搜索框 + 结果列表 + 搜索历史

import { store } from '../store.js';
import { api } from '../api.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { escapeHtml } from '../utils/escape.js';
import { ConfusingPairCard } from '../components/confusing-pair-card.js';
import { SearchSuggest } from '../components/search-suggest.js';

export class SearchPage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 搜索输入框 */
    searchInput = null;

    /** 结果列表容器 */
    resultsContainer = null;

    /** 空状态提示容器 */
    emptyState = null;

    /** 当前搜索关键词 */
    _currentQuery = '';

    /** 搜索中标志位（防止重复提交） */
    _searching = false;

    /** 绑定的事件处理器引用集合 */
    _boundHandlers = {};

    /** 搜索联想下拉组件实例 */
    _suggest = null;

    /** 搜索历史相关 */
    static SEARCH_HISTORY_KEY = 'ecosort_search_history';
    static MAX_SEARCH_HISTORY = 20;

    /**
     * 初始化搜索结果页
     * 解析 URL 参数、渲染界面、自动聚焦搜索框
     */
    init() {
        this.container = document.getElementById('page-search');
        if (!this.container) {
            console.error('[SearchPage] 容器 #page-search 不存在');
            return;
        }

        /* 从 URL hash 解析查询参数 ?q=keyword */
        this._parseQueryParams();

        /* 渲染页面结构 */
        this._render();
        /* 缓存 DOM 引用 */
        this._cacheDOM();
        /* 填充搜索词并聚焦 */
        this._initSearchInput();
        /* F-2.2.4 渲染搜索历史（无预设关键词时显示） */
        if (!this._currentQuery) {
            this._renderSearchHistory();
        }
        /* 绑定事件 */
        this._bindEvents();

        /* 如果有预设关键词则自动执行搜索 */
        if (this._currentQuery) {
            this._doSearch(this._currentQuery);
        }

        console.log(`[SearchPage] 搜索页初始化完成, 关键词: "${this._currentQuery}"`);
    }

    /**
     * 销毁搜索结果页
     * 移除事件监听、清空容器、释放引用
     */
    destroy() {
        /* 移除搜索回车事件 */
        if (this.searchInput) {
            this.searchInput.removeEventListener('keydown', this._boundHandlers.keydown);
            this.searchInput.removeEventListener('input', this._boundHandlers.input);
        }

        /* 移除返回按钮事件 */
        const backBtn = document.getElementById('searchBackBtn');
        if (backBtn && this._boundHandlers.backClick) {
            backBtn.removeEventListener('click', this._boundHandlers.backClick);
        }

        /* 移除语音按钮事件 */
        const voiceBtn = document.getElementById('searchVoiceBtn');
        if (voiceBtn && this._boundHandlers.voiceClick) {
            voiceBtn.removeEventListener('click', this._boundHandlers.voiceClick);
        }

        /* 销毁搜索联想组件 */
        if (this._suggest) {
            this._suggest.destroy();
            this._suggest = null;
        }

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 释放引用 */
        this.container = null;
        this.searchInput = null;
        this.resultsContainer = null;
        this.emptyState = null;
        this._historyArea = null;
        this._currentQuery = '';
        this._searching = false;
        this._boundHandlers = {};

        console.log('[SearchPage] 搜索页已销毁');
    }

    
    _parseQueryParams() {
        /* 优先从 URL hash 解析 */
        const hash = window.location.hash || '';
        const match = hash.match(/[?&]q=([^&]*)/);

        if (match) {
            /* URL 解码关键词 */
            this._currentQuery = decodeURIComponent(match[1]) || '';
        } else {
            /* 其次尝试从 store 获取（首页搜索跳转时存储） */
            this._currentQuery = store.getState('searchQuery') || '';
        }
    }

    
    _render() {
        this.container.innerHTML = `
            <!-- 导航栏 -->
            <div class="search-nav">
                <button class="nav-back-btn" id="searchBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="search-nav-title">搜索</h2>
            </div>

            <!-- 搜索卡片 -->
            <div class="card search-card">
                <!-- 搜索输入框（支持 autofocus） -->
                <div class="search-box">
                    <input type="text"
                           id="searchPageInput"
                           class="search-input"
                           placeholder="输入垃圾名称搜索..."
                           autocomplete="off"
                           autofocus>
                    <button class="voice-btn" id="searchVoiceBtn" title="语音输入" aria-label="语音输入">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </button>
                </div>
            </div>

            <!-- 搜索结果列表区域 -->
            <div id="searchResultsArea">
                <!-- F-2.2.4 搜索历史区域（初始展示，搜索后隐藏） -->
                <div id="searchHistoryArea" class="search-history-area"></div>
            </div>
        `;
    }

    
    _cacheDOM() {
        this.searchInput = document.getElementById('searchPageInput');
        this.resultsContainer = document.getElementById('searchResultsArea');
        this._historyArea = document.getElementById('searchHistoryArea');
    }

    /* ---- 搜索初始化 ---- */

    /**
     * 初始化搜索输入框状态
     * 填充预设关键词并设置焦点
     * @private
     */
    _initSearchInput() {
        if (!this.searchInput) return;

        /* 填充已有的搜索词 */
        if (this._currentQuery) {
            this.searchInput.value = this._currentQuery;
        }

        /* 自动聚焦搜索框（延迟执行确保 DOM 已就绪） */
        setTimeout(() => {
            this.searchInput?.focus();
            /* 将光标移到末尾 */
            const len = this.searchInput?.value?.length || 0;
            this.searchInput?.setSelectionRange(len, len);
        }, 100);
    }

    
    _bindEvents() {
        /* Enter 键触发搜索 */
        this._boundHandlers.keydown = (e) => {
            if (e.key === 'Enter') {
                const query = this.searchInput?.value.trim();
                if (query) {
                    this._doSearch(query);
                }
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', this._boundHandlers.keydown);
        }

        /* 搜索联想下拉 (F-2.2.3) */
        this._suggest = new SearchSuggest({
            inputEl: this.searchInput,
            onSelect: (keyword) => {
                this._doSearch(keyword);
            }
        });

        /* 输入时隐藏空状态（如有） */
        this._boundHandlers.input = () => {
            if (this.emptyState) {
                this.emptyState.style.display = 'none';
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('input', this._boundHandlers.input);
        }

        /* 返回按钮 */
        const backBtn = document.getElementById('searchBackBtn');
        this._boundHandlers.backClick = () => {
            window.location.hash = '#/';
        };
        if (backBtn) {
            backBtn.addEventListener('click', this._boundHandlers.backClick);
        }

        /* 语音按钮占位（阶段二实现） */
        const voiceBtn = document.getElementById('searchVoiceBtn');
        this._boundHandlers.voiceClick = () => {
            showToast('语音识别功能即将上线，敬请期待');
        };
        if (voiceBtn) {
            voiceBtn.addEventListener('click', this._boundHandlers.voiceClick);
        }
    }

    
    async _doSearch(query) {
        /* 防止重复搜索和空查询 */
        if (this._searching || !query || !query.trim()) return;

        this._searching = true;
        this._currentQuery = query.trim();

        /* 更新 URL hash（不含 # 前缀，避免触发路由重载） */
        const newHash = '#/search?q=' + encodeURIComponent(this._currentQuery);
        window.history.replaceState(null, '', newHash);

        /* 显示加载状态 */
        showLoading('搜索中...');

        try {
            /* 调用搜索 API */
            const response = await api.search(this._currentQuery);

            hideLoading();

            /* 判断是否有结果 */
            if (response.results && response.results.length > 0) {
                this._renderResults(response.results);
            } else {
                this._renderEmptyState(this._currentQuery);
            }

            /* F-2.2.4 保存搜索词到历史记录 */
            this._saveSearchHistory(this._currentQuery);

            /* F-2.2.4 同步更新SearchSuggest组件的历史缓存（保持数据一致性） */
            if (this._suggest && typeof this._suggest.saveToHistory === 'function') {
                this._suggest.saveToHistory(this._currentQuery);
            }

        } catch (error) {
            hideLoading();
            console.error('[SearchPage] 搜索失败:', error);

            /* 网络异常友好提示 */
            let errorMsg = '搜索失败，请重试';
            if (!navigator.onLine) {
                errorMsg = '网络连接不可用，请检查网络后重试';
            }

            showToast(errorMsg, 'error');
            this._renderErrorState(errorMsg);

        } finally {
            this._searching = false;
        }
    }

    
    _renderResults(results) {
        if (!this.resultsContainer) return;
        /* 隐藏搜索历史区域 */
        if (this._historyArea) {
            this._historyArea.style.display = 'none';
        }

        /* 检查结果相似度，判断是否为低质量匹配 */
        const avgSimilarity = results.reduce((sum, item) => sum + (Number(item.similarity_score) || 0), 0) / results.length;
        const maxSimilarity = Math.max(...results.map(item => Number(item.similarity_score) || 0));
        const isLowQualityMatch = maxSimilarity < 50; // 最高相似度低于50%视为低质量匹配

        /* 构建结果列表 HTML（所有动态内容均经过转义） */
        const listHTML = results.map((item, index) => `
            <div class="card search-result-item"
                 data-index="${index}"
                 role="button"
                 tabindex="0"
                 aria-label="查看 ${escapeHtml(item.match_label || item.label || '未知')} 详情">
                <div class="search-item-left">
                    <div class="search-item-icon">${escapeHtml(item.bin_icon || '')}</div>
                    <div class="search-item-info">
                        <div class="search-item-label">${escapeHtml(item.match_label || item.label || '未知')}</div>
                        <div class="search-item-category">${escapeHtml(item.category_name || item.category || '未知类别')}</div>
                    </div>
                </div>
                <div class="search-score">
                    <span class="score-value">${Number(item.similarity_score) || 0}%</span>
                    <span class="score-label">相似度</span>
                </div>
            </div>
        `).join('');

        /* 构建低质量匹配提示 */
        const lowQualityHint = isLowQualityMatch ? `
            <div class="search-low-quality-hint" style="
                padding: 12px;
                margin: 12px 0;
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 8px;
                color: #856404;
                font-size: 14px;
            ">
                💡 未找到精确匹配项，以上为模糊推荐结果。建议尝试：
                <ul style="margin: 8px 0 0 20px; padding: 0;">
                    <li>使用更具体的关键词（如"塑料瓶"而非"塑料"）</li>
                    <li>检查输入是否有错别字</li>
                    <li>使用拼音首字母搜索（如"suliaoping"）</li>
                </ul>
            </div>
        ` : '';

        this.resultsContainer.innerHTML = `
            <div class="search-results-header">
                <span class="results-count">找到 ${results.length} 条${isLowQualityMatch ? '模糊' : '相关'}结果</span>
                <span class="results-query">"${escapeHtml(this._currentQuery)}"</span>
            </div>
            ${lowQualityHint}
            <div class="search-results-list">
                ${listHTML}
            </div>
            <div id="searchConfusingHint" class="search-confusing-hint"></div>
        `;

        this._bindResultItemEvents(results);
        this._loadConfusingHint(this._currentQuery);
    }

    async _loadConfusingHint(query) {
        const container = document.getElementById('searchConfusingHint');
        if (!container || !query) return;

        try {
            const response = await api.getGuideItem(query);
            const pairs = response.confusing_pairs || [];
            if (pairs.length === 0) return;

            const pairCard = new ConfusingPairCard();
            container.innerHTML = `<h4 class="confusing-hint-title">⚠️ 易混淆提醒</h4>`;

            pairs.slice(0, 3).forEach(pair => {
                const compactEl = pairCard.renderCompact(pair);
                container.appendChild(compactEl);
            });

            pairCard.destroy();
        } catch (error) {
            /* 静默失败，不影响搜索结果展示 */
        }
    }

    // 点击结果项跳转详情
    _bindResultItemEvents(results) {
        const items = this.resultsContainer?.querySelectorAll('.search-result-item');
        if (!items) return;

        items.forEach((itemEl, index) => {
            itemEl.addEventListener('click', () => {
                const resultData = results[index];
                const keyword = resultData.match_label || resultData.label || '';
                if (keyword) {
                    store.setState('currentItemKeyword', keyword);
                    window.location.hash = '#/item/' + encodeURIComponent(keyword);
                }
            });

            itemEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    itemEl.click();
                }
            });
        });
    }

    // 没搜到东西的提示
    _renderEmptyState(query) {
        if (!this.resultsContainer) return;

        this.emptyState = document.createElement('div');
        this.emptyState.className = 'card empty-state-card';
        this.emptyState.innerHTML = `
            <div class="empty-state-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" stroke="#95A0AA" stroke-width="1.5" fill="none">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                    <line x1="8" y1="11" x2="14" y2="11"/>
                </svg>
            </div>
            <div class="empty-state-text">未找到相关结果</div>
            <div class="empty-state-hint">未找到「${escapeHtml(query)}」相关结果，请尝试其他关键词</div>
            <div class="empty-state-suggestions">
                <p>推荐尝试：</p>
                <ul>
                    <li>检查输入是否有错别字</li>
                    <li>使用更简短的关键词</li>
                    <li>使用同义词或近义词</li>
                </ul>
            </div>
        `;

        this.resultsContainer.innerHTML = '';
        this.resultsContainer.appendChild(this.emptyState);
    }

    // 搜索出错了
    _renderErrorState(errorMsg) {
        if (!this.resultsContainer) return;

        this.resultsContainer.innerHTML = `
            <div class="card error-state-card">
                <div class="error-state-text">${escapeHtml(errorMsg)}</div>
                <button class="btn btn-secondary btn-retry" id="retrySearchBtn">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="1 4 1 10 7 10"/>
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                    </svg>
                    重试
                </button>
            </div>
        `;

        /* 绑定重试按钮 */
        const retryBtn = document.getElementById('retrySearchBtn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                if (this._currentQuery) {
                    this._doSearch(this._currentQuery);
                }
            });
        }
    }

    /* ---- 搜索历史 ---- */

    _getSearchHistory() {
        try {
            const raw = localStorage.getItem(SearchPage.SEARCH_HISTORY_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch { return []; }
    }

    _saveSearchHistory(query) {
        if (!query || !query.trim()) return;
        const q = query.trim();
        try {
            let history = this._getSearchHistory();
            history = history.filter(item => item !== q);
            history.unshift(q);
            if (history.length > SearchPage.MAX_SEARCH_HISTORY) {
                history = history.slice(0, SearchPage.MAX_SEARCH_HISTORY);
            }
            localStorage.setItem(SearchPage.SEARCH_HISTORY_KEY, JSON.stringify(history));
        } catch (e) {
            console.warn('[SearchPage] 保存搜索历史失败:', e);
        }
    }

    _renderSearchHistory() {
        if (!this._historyArea) return;
        const history = this._getSearchHistory();
        if (history.length === 0) {
            this._historyArea.innerHTML = '';
            this._historyArea.style.display = 'none';
            return;
        }
        this._historyArea.style.display = '';
        const itemsHTML = history.map(q => `
            <div class="search-history-item" data-query="${escapeHtml(q)}" role="button" tabindex="0">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="#95A0AA" stroke-width="2" fill="none">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span class="search-history-text">${escapeHtml(q)}</span>
                <svg class="search-history-del" viewBox="0 0 24 24" width="14" height="14" stroke="#C0C8D0" stroke-width="2" fill="none" data-del="${escapeHtml(q)}">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </div>
        `).join('');
        this._historyArea.innerHTML = `
            <div class="card search-history-card">
                <div class="search-history-header">
                    <span class="search-history-title">🕐 最近搜索</span>
                    <button class="search-history-clear-btn" id="clearHistoryBtn">清空</button>
                </div>
                <div class="search-history-list">${itemsHTML}</div>
            </div>
        `;
        this._bindSearchHistoryEvents();
    }

    _bindSearchHistoryEvents() {
        if (!this._historyArea) return;
        this._historyArea.addEventListener('click', (e) => {
            const delBtn = e.target.closest('.search-history-del');
            if (delBtn) {
                const q = delBtn.dataset.del;
                this._removeSearchHistoryItem(q);
                return;
            }
            const item = e.target.closest('.search-history-item');
            if (item) {
                const q = item.dataset.query;
                if (q && this.searchInput) {
                    this.searchInput.value = q;
                    this._doSearch(q);
                }
            }
        });
        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                try {
                    localStorage.removeItem(SearchPage.SEARCH_HISTORY_KEY);
                    this._renderSearchHistory();
                    showToast('已清空搜索历史', 'success');
                } catch (e) {
                    console.warn('[SearchPage] 清空搜索历史失败:', e);
                }
            });
        }
    }

    _removeSearchHistoryItem(query) {
        try {
            let history = this._getSearchHistory().filter(item => item !== query);
            localStorage.setItem(SearchPage.SEARCH_HISTORY_KEY, JSON.stringify(history));
            this._renderSearchHistory();
        } catch (e) {
            console.warn('[SearchPage] 删除搜索历史失败:', e);
        }
    }
}

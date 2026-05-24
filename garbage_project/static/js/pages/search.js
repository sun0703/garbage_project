/**
 * 搜索结果页视图（Search Page）
 *
 * 职责：提供搜索框（autofocus）、语音输入、搜索联想、搜索历史、
 *       从 URL hash 解析查询参数、执行搜索请求并渲染结果列表，
 *       支持点击结果项跳转详情。
 * 容器：#page-search
 */

import { store } from '../store.js';
import { api } from '../api.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { VoiceButton } from '../components/voice-btn.js';
import { SearchSuggest } from '../components/search-suggest.js';
import { SearchHistory } from '../utils/search-history.js';

export class SearchPage {
    container = null;
    searchInput = null;
    resultsContainer = null;
    emptyState = null;
    voiceBtnContainer = null;
    voiceButton = null;
    searchSuggest = null;
    _currentQuery = '';
    _searching = false;
    _boundHandlers = {};

    init() {
        this.container = document.getElementById('page-search');
        if (!this.container) {
            console.error('[SearchPage] 容器 #page-search 不存在');
            return;
        }

        this._parseQueryParams();
        this._render();
        this._cacheDOM();
        this._initSearchInput();
        this._bindEvents();
        this._initVoiceButton();
        this._initSearchSuggest();

        if (this._currentQuery) {
            SearchHistory.add(this._currentQuery);
            this._doSearch(this._currentQuery);
        }

        console.log(`[SearchPage] 搜索页初始化完成, 关键词: "${this._currentQuery}"`);
    }

    destroy() {
        if (this.searchInput) {
            this.searchInput.removeEventListener('keydown', this._boundHandlers.keydown);
            this.searchInput.removeEventListener('input', this._boundHandlers.input);
        }

        if (this.voiceButton) {
            this.voiceButton.destroy();
            this.voiceButton = null;
        }

        if (this.searchSuggest) {
            this.searchSuggest.destroy();
            this.searchSuggest = null;
        }

        if (this.container) {
            this.container.innerHTML = '';
        }

        this.container = null;
        this.searchInput = null;
        this.resultsContainer = null;
        this.emptyState = null;
        this.voiceBtnContainer = null;
        this._currentQuery = '';
        this._searching = false;
        this._boundHandlers = {};

        console.log('[SearchPage] 搜索页已销毁');
    }

    _parseQueryParams() {
        const hash = window.location.hash || '';
        const match = hash.match(/[?&]q=([^&]*)/);

        if (match) {
            this._currentQuery = decodeURIComponent(match[1]) || '';
        } else {
            this._currentQuery = store.get('searchQuery') || '';
        }
    }

    _render() {
        this.container.innerHTML = `
            <div class="search-nav">
                <button class="nav-back-btn" id="searchBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="search-nav-title">搜索</h2>
            </div>

            <div class="card search-card">
                <div class="search-box">
                    <input type="text"
                           id="searchPageInput"
                           class="search-input"
                           placeholder="输入垃圾名称或拼音搜索..."
                           autocomplete="off"
                           autofocus>
                    <div id="searchVoiceBtnContainer" class="voice-btn-slot"></div>
                </div>
            </div>

            <div id="searchResultsArea">
            </div>
        `;
    }

    _cacheDOM() {
        this.searchInput = document.getElementById('searchPageInput');
        this.resultsContainer = document.getElementById('searchResultsArea');
        this.voiceBtnContainer = document.getElementById('searchVoiceBtnContainer');
    }

    _initVoiceButton() {
        if (!this.voiceBtnContainer) return;

        this.voiceButton = new VoiceButton({
            container: this.voiceBtnContainer,
            onResult: (text) => this._handleVoiceResult(text),
            onError: (code, message) => this._handleVoiceError(code, message)
        });
        this.voiceButton.init();
    }

    _initSearchSuggest() {
        if (!this.searchInput) return;

        this.searchSuggest = new SearchSuggest({
            input: this.searchInput,
            onSelect: (label) => this._handleSuggestSelect(label)
        });
        this.searchSuggest.init();
    }

    _handleSuggestSelect(label) {
        SearchHistory.add(label);
        this._doSearch(label);
    }

    _handleVoiceResult(text) {
        if (!text || !text.trim()) return;

        const query = text.trim();

        if (this.searchInput) {
            this.searchInput.value = query;
        }

        SearchHistory.add(query);
        showToast(`识别到: ${query}`, 'success');
        this._doSearch(query);
    }

    _handleVoiceError(code, message) {
        if (code === 'unsupported') {
            showToast(message, 'warning', 4000);
        } else if (code !== 'aborted') {
            showToast(message, 'error');
        }
    }

    _initSearchInput() {
        if (!this.searchInput) return;

        if (this._currentQuery) {
            this.searchInput.value = this._currentQuery;
        }

        setTimeout(() => {
            this.searchInput?.focus();
            const len = this.searchInput?.value?.length || 0;
            this.searchInput?.setSelectionRange(len, len);
        }, 100);
    }

    _bindEvents() {
        this._boundHandlers.keydown = (e) => {
            if (e.key === 'Enter') {
                const query = this.searchInput?.value.trim();
                if (query) {
                    SearchHistory.add(query);
                    this._doSearch(query);
                }
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', this._boundHandlers.keydown);
        }

        this._boundHandlers.input = () => {
            if (this.emptyState) {
                this.emptyState.style.display = 'none';
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('input', this._boundHandlers.input);
        }

        const backBtn = document.getElementById('searchBackBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }
    }

    async _doSearch(query) {
        if (this._searching || !query || !query.trim()) return;

        this._searching = true;
        this._currentQuery = query.trim();

        const newHash = '#/search?q=' + encodeURIComponent(this._currentQuery);
        window.history.replaceState(null, '', newHash);

        if (this.searchSuggest) {
            this.searchSuggest.hide();
        }

        showLoading('搜索中...');

        try {
            const response = await api.search(this._currentQuery);

            hideLoading();

            if (response.results && response.results.length > 0) {
                this._renderResults(response.results);
            } else {
                this._renderEmptyState(this._currentQuery);
            }

        } catch (error) {
            hideLoading();
            console.error('[SearchPage] 搜索失败:', error);

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

        const listHTML = results.map((item, index) => {
            const matchType = item.match_type || 'fuzzy';
            const matchBadge = matchType === 'pinyin'
                ? '<span class="match-badge match-badge--pinyin">拼音</span>'
                : matchType === 'alias'
                    ? '<span class="match-badge match-badge--alias">同义词</span>'
                    : '';

            return `
                <div class="card search-result-item"
                     data-index="${index}"
                     role="button"
                     tabindex="0"
                     aria-label="查看 ${item.match_label || item.label || '未知'} 详情">
                    <div class="search-item-left">
                        <div class="search-item-icon">${item.bin_icon || ''}</div>
                        <div class="search-item-info">
                            <div class="search-item-label">${item.match_label || item.label || '未知'} ${matchBadge}</div>
                            <div class="search-item-category">${item.category || '未知类别'}</div>
                        </div>
                    </div>
                    <div class="search-score">
                        <span class="score-value">${item.similarity_score || 0}%</span>
                        <span class="score-label">相似度</span>
                    </div>
                </div>
            `;
        }).join('');

        this.resultsContainer.innerHTML = `
            <div class="search-results-header">
                <span class="results-count">找到 ${results.length} 条相关结果</span>
                <span class="results-query">"${this._currentQuery}"</span>
            </div>
            <div class="search-results-list">
                ${listHTML}
            </div>
        `;

        this._bindResultItemEvents(results);
    }

    _bindResultItemEvents(results) {
        const items = this.resultsContainer?.querySelectorAll('.search-result-item');
        if (!items) return;

        items.forEach((itemEl, index) => {
            itemEl.addEventListener('click', () => {
                const resultData = results[index];
                store.set('predictResult', {
                    label_en: resultData.yolo_label || '',
                    label_cn: resultData.match_label || resultData.label || '',
                    category: resultData.category || '',
                    category_id: resultData.category_id,
                    confidence: (resultData.similarity_score || 0) / 100,
                    bin_color: resultData.bin_color || '#666',
                    bin_icon: resultData.bin_icon || '',
                    guidance: resultData.guidance || ''
                });

                window.location.hash = '#/result';
            });

            itemEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    itemEl.click();
                }
            });
        });
    }

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
            <div class="empty-state-hint">未找到「${query}」相关结果，请尝试其他关键词</div>
            <div class="empty-state-suggestions">
                <p>推荐尝试：</p>
                <ul>
                    <li>检查输入是否有错别字</li>
                    <li>使用更简短的关键词</li>
                    <li>使用同义词或近义词</li>
                    <li>试试拼音首字母搜索（如"slp"→塑料瓶）</li>
                </ul>
            </div>
        `;

        this.resultsContainer.innerHTML = '';
        this.resultsContainer.appendChild(this.emptyState);
    }

    _renderErrorState(errorMsg) {
        if (!this.resultsContainer) return;

        this.resultsContainer.innerHTML = `
            <div class="card error-state-card">
                <div class="error-state-text">${errorMsg}</div>
                <button class="btn btn-secondary btn-retry" id="retrySearchBtn">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="1 4 1 10 7 10"/>
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                    </svg>
                    重试
                </button>
            </div>
        `;

        const retryBtn = document.getElementById('retrySearchBtn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                if (this._currentQuery) {
                    this._doSearch(this._currentQuery);
                }
            });
        }
    }
}

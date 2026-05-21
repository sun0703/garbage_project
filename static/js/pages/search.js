/**
 * 搜索结果页视图（Search Page）
 *
 * 职责：提供搜索框（autofocus）、从 URL hash 解析查询参数、
 *       执行搜索请求并渲染结果列表，支持点击结果项跳转详情。
 * 容器：#page-search
 */

// ==================== 模块依赖导入 ====================
import { store } from '../store.js';
import { api } from '../api.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';

// ==================== 页面类定义 ====================
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

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 释放引用 */
        this.container = null;
        this.searchInput = null;
        this.resultsContainer = null;
        this.emptyState = null;
        this._currentQuery = '';
        this._searching = false;
        this._boundHandlers = {};

        console.log('[SearchPage] 搜索页已销毁');
    }

    // ==================== 私有方法：URL 参数解析 ====================

    /**
     * 从 URL hash 中解析查询参数
     * 支持格式：#/search?q=关键词 或从 store 读取 searchQuery
     * @private
     */
    _parseQueryParams() {
        /* 优先从 URL hash 解析 */
        const hash = window.location.hash || '';
        const match = hash.match(/[?&]q=([^&]*)/);

        if (match) {
            /* URL 解码关键词 */
            this._currentQuery = decodeURIComponent(match[1]) || '';
        } else {
            /* 其次尝试从 store 获取（首页搜索跳转时存储） */
            this._currentQuery = store.get('searchQuery') || '';
        }
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染搜索页面 HTML 结构
     * 包含导航栏、搜索框、结果列表区、空状态提示
     * @private
     */
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
                <!-- 动态内容：结果列表或空状态提示 -->
            </div>
        `;
    }

    // ==================== 私有方法：DOM 缓存 ====================

    /**
     * 缓存高频使用的 DOM 元素引用
     * @private
     */
    _cacheDOM() {
        this.searchInput = document.getElementById('searchPageInput');
        this.resultsContainer = document.getElementById('searchResultsArea');
    }

    // ==================== 私有方法：搜索初始化 ====================

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

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定全部交互事件
     * @private
     */
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
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }

        /* 语音按钮占位（阶段二实现） */
        const voiceBtn = document.getElementById('searchVoiceBtn');
        if (voiceBtn) {
            voiceBtn.addEventListener('click', () => {
                showToast('语音识别功能即将上线，敬请期待');
            });
        }
    }

    // ==================== 私有方法：搜索核心逻辑 ====================

    /**
     * 执行搜索请求
     * 流程：加载状态 → API调用 → 渲染结果/显示空状态
     *
     * @param {string} query - 搜索关键词
     * @private
     */
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

    // ==================== 私有方法：结果渲染 ====================

    /**
     * 渲染搜索结果列表
     * 每项显示：图标 + 名称 + 类别 + 相似度分数
     *
     * @param {Array<Object>} results - 搜索结果数组
     * @private
     */
    _renderResults(results) {
        if (!this.resultsContainer) return;

        /* 构建结果列表 HTML */
        const listHTML = results.map((item, index) => `
            <div class="card search-result-item"
                 data-index="${index}"
                 role="button"
                 tabindex="0"
                 aria-label="查看 ${item.match_label || item.label || '未知'} 详情">
                <div class="search-item-left">
                    <div class="search-item-icon">${item.bin_icon || ''}</div>
                    <div class="search-item-info">
                        <div class="search-item-label">${item.match_label || item.label || '未知'}</div>
                        <div class="search-item-category">${item.category || '未知类别'}</div>
                    </div>
                </div>
                <div class="search-score">
                    <span class="score-value">${item.similarity_score || 0}%</span>
                    <span class="score-label">相似度</span>
                </div>
            </div>
        `).join('');

        this.resultsContainer.innerHTML = `
            <div class="search-results-header">
                <span class="results-count">找到 ${results.length} 条相关结果</span>
                <span class="results-query">"${this._currentQuery}"</span>
            </div>
            <div class="search-results-list">
                ${listHTML}
            </div>
        `;

        /* 为每个结果项绑定点击事件 */
        this._bindResultItemEvents(results);
    }

    /**
     * 为搜索结果列表项绑定点击事件
     * 点击后存储结果数据并跳转到结果展示页
     *
     * @param {Array<Object>} results - 原始结果数据数组
     * @private
     */
    _bindResultItemEvents(results) {
        const items = this.resultsContainer?.querySelectorAll('.search-result-item');
        if (!items) return;

        items.forEach((itemEl, index) => {
            /* 点击查看详情 */
            itemEl.addEventListener('click', () => {
                const resultData = results[index];
                /* 将搜索结果格式化为标准 predictResult 格式存入 store */
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

                /* 跳转结果展示页（复用 ResultCard 展示） */
                window.location.hash = '#/result';
            });

            /* 键盘无障碍支持 */
            itemEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    itemEl.click();
                }
            });
        });
    }

    /**
     * 渲染空状态提示
     * 当搜索无匹配结果时显示友好提示
     *
     * @param {string} query - 用户搜索的关键词
     * @private
     */
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
                </ul>
            </div>
        `;

        this.resultsContainer.innerHTML = '';
        this.resultsContainer.appendChild(this.emptyState);
    }

    /**
     * 渲染错误状态
     * 搜索请求失败时显示错误信息
     *
     * @param {string} errorMsg - 错误提示文本
     * @private
     */
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
}

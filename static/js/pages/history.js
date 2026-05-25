/**
 * 历史记录页视图（History Page）
 *
 * 职责：展示用户过往的识别历史记录列表；
 *       支持单条删除、一键清空（二次确认）、点击回看详情（复用 ResultCard）；
 *       空状态引导、顶部统计信息。
 * 容器：#page-history
 */

// ==================== 模块依赖导入 ====================
import { store } from '../store.js';
import { api } from '../api.js';
import { showToast, confirm, showModal } from '../utils/ui.js';

// ==================== 页面类定义 ====================
export class HistoryPage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 历史记录列表容器 */
    listContainer = null;

    /** 统计信息容器 */
    statsContainer = null;

    /** 当前历史记录数据 */
    _records = [];

    /** 绑定的事件处理器引用集合 */
    _boundHandlers = {};

    /**
     * 初始化历史记录页
     * 从本地存储读取记录并渲染列表
     */
    async init() {
        this.container = document.getElementById('page-history');
        if (!this.container) {
            console.error('[HistoryPage] 容器 #page-history 不存在');
            return;
        }

        /* 渲染页面骨架 */
        this._render();
        /* 缓存 DOM 引用 */
        this._cacheDOM();
        /* 加载并渲染历史记录 */
        await this._loadRecords();
        /* 绑定事件 */
        this._bindEvents();

        console.log('[HistoryPage] 历史记录页初始化完成');
    }

    /**
     * 销毁历史记录页
     * 移除事件监听、清空容器、释放引用
     */
    destroy() {
        /* 移除列表容器事件委托 */
        if (this.listContainer && this._boundHandlers.listClick) {
            this.listContainer.removeEventListener('click', this._boundHandlers.listClick);
        }

        /* 移除清空按钮事件 */
        const clearBtn = document.getElementById('clearAllBtn');
        if (clearBtn) {
            clearBtn.removeEventListener('click', this._boundHandlers.clear);
        }

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 释放引用 */
        this.container = null;
        this.listContainer = null;
        this.statsContainer = null;
        this._records = [];
        this._boundHandlers = {};

        console.log('[HistoryPage] 历史记录页已销毁');
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染页面 HTML 骨架结构
     * 包含导航栏、统计区、操作栏、列表容器、空状态占位
     * @private
     */
    _render() {
        this.container.innerHTML = `
            <!-- 导航栏 -->
            <div class="history-nav">
                <button class="nav-back-btn" id="historyBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="history-nav-title">识别历史</h2>
            </div>

            <!-- 统计信息卡片 -->
            <div class="card history-stats-card">
                <div class="stats-row">
                    <div class="stats-item">
                        <span class="stats-number" id="statsCount">0</span>
                        <span class="stats-label">条记录</span>
                    </div>
                    <div class="stats-divider"></div>
                    <div class="stats-item">
                        <span class="stats-icon">📊</span>
                        <span class="stats-label">历史统计</span>
                    </div>
                </div>
            </div>

            <!-- 操作栏：一键清空按钮 -->
            <div class="history-toolbar" id="historyToolbar" style="display: none;">
                <button class="btn btn-secondary btn-clear-all" id="clearAllBtn">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    一键清空
                </button>
            </div>

            <!-- 历史记录列表容器 -->
            <div id="historyListContainer" class="history-list-container">
                <!-- 动态填充：记录列表或空状态 -->
            </div>
        `;
    }

    // ==================== 私有方法：DOM 缓存 ====================

    /**
     * 缓存高频使用的 DOM 元素引用
     * @private
     */
    _cacheDOM() {
        this.listContainer = document.getElementById('historyListContainer');
        this.statsContainer = document.getElementById('statsCount');
    }

    // ==================== 私有方法：数据加载 ====================

    /**
     * 从本地存储加载历史记录 (F-1.5.2)
     * 使用 Storage 工具类读取持久化数据
     * @private
     */
    async _loadRecords() {
        try {
            /* 通过后端 API 获取历史记录（大页数一次拉取） */
            const response = await api.getHistory(1, 200);
            this._records = (response && response.length !== undefined)
                ? response  // api.request 已提取 data 字段，直接是数组
                : [];

            /* 更新统计信息 */
            this._updateStats();

            /* 根据是否有数据渲染不同界面 */
            if (this._records.length > 0) {
                this._renderRecordList();
            } else {
                this._renderEmptyState();
            }

        } catch (error) {
            console.error('[HistoryPage] 加载历史记录失败:', error);
            this._renderErrorState('读取历史记录失败，请检查网络连接后重试');
        }
    }

    // ==================== 私有方法：统计更新 ====================

    /**
     * 更新顶部统计信息显示
     * 格式：「共 N 条记录」
     * @private
     */
    _updateStats() {
        if (!this.statsContainer) return;

        const count = this._records.length;
        this.statsContainer.textContent = count;

        /* 显示/隐藏工具栏（有记录时显示清空按钮） */
        const toolbar = document.getElementById('historyToolbar');
        if (toolbar) {
            toolbar.style.display = count > 0 ? 'flex' : 'none';
        }
    }

    // ==================== 私有方法：列表渲染 ====================

    /**
     * 渲染历史记录列表
     * 每项包含：缩略图 + 物品名 + 类别标签 + 置信度 + 时间戳
     * F-1.5.2 历史记录侧边栏/抽屉 的列表展示形式
     *
     * @private
     */
    _renderRecordList() {
        if (!this.listContainer) return;

        /* 按时间倒序排列（最新在前） */
        const sortedRecords = [...this._records].sort(
            (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
        );

        /* 构建每条记录的 HTML */
        const itemsHTML = sortedRecords.map((record, index) => {
            return this._buildRecordItem(record, index);
        }).join('');

        this.listContainer.innerHTML = `
            <div class="history-record-list">
                ${itemsHTML}
            </div>
        `;
    }

    /**
     * 构建单条历史记录项的 HTML
     *
     * @param {Object} record - 记录数据对象
     * @param {number} index - 列表索引
     * @returns {string} 记录项 HTML 字符串
     * @private
     */
    _buildRecordItem(record, index) {
        const label = record.label_cn || record.label || '未知物品';
        const category = record.category || '未知类别';
        const categoryColor = record.bin_color || '#666';
        const confidence = record.confidence ? Math.round(record.confidence * 100) : 0;
        const timestamp = record.created_at ? this._formatTimestamp(record.created_at) : '';

        return `
            <div class="card history-record-item"
                 data-record-id="${record.id}"
                 style="animation-delay: ${index * 0.05}s">

                <!-- 左侧：缩略图区域（API 无图片，固定显示占位图标） -->
                <div class="record-thumbnail">
                    <div class="thumb-placeholder" style="background: ${categoryColor}20;">
                        <span style="color: ${categoryColor}">${label.charAt(0)}</span>
                    </div>
                </div>

                <!-- 中间：信息区域 -->
                <div class="record-info">
                    <div class="record-name-row">
                        <span class="record-name">${label}</span>
                        <span class="record-category-tag"
                              style="background: ${categoryColor}15; color: ${categoryColor}; border: 1px solid ${categoryColor}30;">
                            ${category}
                        </span>
                    </div>
                    <div class="record-meta">
                        <span class="record-confidence">置信度 ${confidence}%</span>
                        <span class="record-time">${timestamp}</span>
                    </div>
                </div>

                <!-- 右侧：操作按钮 -->
                <div class="record-actions">
                    <button class="record-delete-btn"
                            data-delete-id="${record.id}"
                            title="删除此记录"
                            aria-label="删除记录">
                        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }

    // ==================== 私有方法：时间格式化 ====================

    /**
     * 格式化时间戳为可读字符串
     * 支持相对时间格式（如 "3分钟前"）和绝对时间格式
     *
     * @param {string} isoString - ISO 8601 格式的时间戳
     * @returns {string} 格式化的时间文本
     * @private
     */
    _formatTimestamp(isoString) {
        try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now.getTime() - date.getTime();
            const diffMin = Math.floor(diffMs / 60000);
            const diffHour = Math.floor(diffMs / 3600000);
            const diffDay = Math.floor(diffMs / 86400000);

            /* 相对时间格式（更友好） */
            if (diffMin < 1) return '刚刚';
            if (diffMin < 60) return `${diffMin}分钟前`;
            if (diffHour < 24) return `${diffHour}小时前`;
            if (diffDay < 7) return `${diffDay}天前`;

            /* 超过一周则显示日期 */
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');

            return `${month}-${day} ${hours}:${minutes}`;

        } catch (error) {
            return '';
        }
    }

    // ==================== 私有方法：空/错误状态 ====================

    /**
     * 渲染空状态提示
     * 引导用户去拍照识别产生历史记录
     * @private
     */
    _renderEmptyState() {
        if (!this.listContainer) return;

        this.listContainer.innerHTML = `
            <div class="card empty-history-card">
                <div class="empty-history-icon">
                    <svg viewBox="0 0 24 24" width="56" height="56" stroke="#95A0AA" stroke-width="1.2" fill="none">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                </div>
                <div class="empty-history-text">暂无识别历史</div>
                <div class="empty-history-hint">快去拍照试试吧</div>
                <button class="btn btn-primary btn-go-identify" id="goIdentifyBtn">
                    <svg viewBox="0 0 24 24" width="18" height="18" stroke="white" stroke-width="2" fill="none">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                        <circle cx="12" cy="13" r="4"/>
                    </svg>
                    开始识别
                </button>
            </div>
        `;

        /* 绑定「开始识别」按钮跳转首页 */
        const goBtn = document.getElementById('goIdentifyBtn');
        if (goBtn) {
            goBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }
    }

    /**
     * 渲染错误状态
     *
     * @param {string} message - 错误提示文本
     * @private
     */
    _renderErrorState(message) {
        if (!this.listContainer) return;

        this.listContainer.innerHTML = `
            <div class="card error-state-card">
                <p>${message}</p>
            </div>
        `;
    }

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定页面级事件（返回按钮、清空按钮等）
     * @private
     */
    _bindEvents() {
        /* 返回按钮 — 回到首页 */
        const backBtn = document.getElementById('historyBackBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }

        /* 一键清空按钮（需二次确认） */
        this._boundHandlers.clear = () => this._handleClearAll();
        const clearBtn = document.getElementById('clearAllBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', this._boundHandlers.clear);
        }

        /* 列表容器事件委托：点击查看详情 / 删除单条记录 */
        this._boundHandlers.listClick = (e) => {
            const deleteBtn = e.target.closest('.record-delete-btn');
            if (deleteBtn) {
                const recordId = deleteBtn.dataset.deleteId;
                const itemEl = deleteBtn.closest('.history-record-item');
                if (recordId && itemEl) {
                    this._deleteRecord(recordId, itemEl);
                }
                return;
            }

            const itemEl = e.target.closest('.history-record-item');
            if (itemEl) {
                const recordId = itemEl.dataset.recordId;
                const record = this._records.find(r => r.id === recordId);
                if (!record) return;

                store.set('predictResult', {
                    label_cn: record.label_cn || record.label || '',
                    category: record.category || '',
                    confidence: record.confidence || 0,
                    bin_color: record.bin_color || '#666',
                    guidance: record.guidance || ''
                });

                window.location.hash = '#/result';
            }
        };

        if (this.listContainer) {
            this.listContainer.addEventListener('click', this._boundHandlers.listClick);
        }
    }

    // ==================== 私有方法：操作处理 ====================

    /**
     * 删除单条历史记录
     * 带动画移除效果后从存储中删除
     *
     * @param {string} recordId - 要删除的记录 ID
     * @param {HTMLElement} itemEl - 对应的 DOM 元素
     * @private
     */
    async _deleteRecord(recordId, itemEl) {
        try {
            /* 添加淡出动画 */
            itemEl.style.transition = 'all 0.3s ease';
            itemEl.style.opacity = '0';
            itemEl.style.transform = 'translateX(30px)';

            /* 等待动画完成后执行实际删除 */
            await new Promise(resolve => setTimeout(resolve, 300));

            /* 从后端删除 */
            await api.deleteHistoryRecord(recordId);

            /* 从内存数据中移除 */
            this._records = this._records.filter(r => r.id !== recordId);

            /* 从 DOM 中移除 */
            itemEl.remove();

            /* 更新统计 */
            this._updateStats();

            showToast('已删除', 'success');

            /* 如果删完最后一条，显示空状态 */
            if (this._records.length === 0) {
                this._renderEmptyState();
            }

        } catch (error) {
            console.error('[HistoryPage] 删除记录失败:', error);
            showToast('删除失败，请重试', 'error');
        }
    }

    /**
     * 一键清空全部历史记录
     * 使用 confirm 二次确认后执行清空操作
     * @private
     */
    async _handleClearAll() {
        if (this._records.length === 0) return;

        /* 二次确认弹窗 */
        const confirmed = await confirm(
            '确认清空',
            `确定要清空全部 ${this._records.length} 条识别历史吗？此操作不可撤销。`,
            '取消',
            '确认清空'
        );

        if (!confirmed) return; /* 用户取消 */

        try {
            /* 调用后端 API 清空全部记录 */
            await api.clearAllHistory();

            /* 清空内存数据 */
            this._records = [];

            /* 重新渲染界面 */
            this._updateStats();
            this._renderEmptyState();

            showToast('已清空全部历史记录', 'success');

        } catch (error) {
            console.error('[HistoryPage] 清空历史记录失败:', error);
            showToast('清空失败，请重试', 'error');
        }
    }
}

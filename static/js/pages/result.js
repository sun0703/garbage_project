/**
 * 识别结果展示页视图（Result Page）
 *
 * 职责：渲染 AI 识别结果，包含 ResultCard 组件、CategoryTag 组件；
 *       提供操作按钮组（继续识别/分享结果/返回首页）；
 *       自动保存识别记录到本地历史 (F-1.5.1)。
 * 容器：#page-result
 */

// ==================== 模块依赖导入 ====================
import { store } from '../store.js';
import { showToast, showModal, confirm } from '../utils/ui.js';
import { ResultCard } from '../components/result-card.js';
import { CategoryTag } from '../components/category-tag.js';
import { storage } from '../utils/storage.js';

// ==================== 页面类定义 ====================
export class ResultPage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 当前识别结果数据 */
    _resultData = null;

    /** ResultCard 组件实例引用（用于 destroy 时清理） */
    _resultCard = null;

    /** CategoryTag 组件实例引用（用于 destroy 时清理） */
    _categoryTag = null;

    /** 绑定的事件处理器引用集合 */
    _boundHandlers = {};

    /**
     * 初始化结果展示页
     * 从 store 读取 predictResult 并渲染完整结果界面
     */
    init() {
        this.container = document.getElementById('page-result');
        if (!this.container) {
            console.error('[ResultPage] 容器 #page-result 不存在');
            return;
        }

        /* 从 store 获取识别结果 */
        const predictResult = store.get('predictResult');
        if (!predictResult) {
            showToast('无识别结果，请先上传图片识别', 'warning');
            window.location.hash = '#/';
            return;
        }

        this._resultData = predictResult;

        /* 渲染页面结构 */
        this._render();
        /* 渲染组件内容 */
        this._renderComponents();
        /* F-1.5.1 保存识别结果到本地历史记录 (localStorage) */
        this._saveToLocalHistory(predictResult);
        /* 绑定按钮事件 */
        this._bindEvents();

        console.log('[ResultPage] 结果页初始化完成', predictResult);
    }

    /**
     * 销毁结果展示页
     * 移除事件监听、清空容器、释放数据引用
     */
    destroy() {
        const guideBtn = document.getElementById('guideDetailBtn');
        const continueBtn = document.getElementById('continueBtn');
        const shareBtn = document.getElementById('shareBtn');
        const homeBtn = document.getElementById('homeBtn');

        if (guideBtn) guideBtn.removeEventListener('click', this._boundHandlers.guide);
        if (continueBtn) continueBtn.removeEventListener('click', this._boundHandlers.continue);
        if (shareBtn) shareBtn.removeEventListener('click', this._boundHandlers.share);
        if (homeBtn) homeBtn.removeEventListener('click', this._boundHandlers.home);

        /* 销毁子组件实例释放事件监听 */
        if (this._resultCard && typeof this._resultCard.destroy === 'function') {
            this._resultCard.destroy();
            this._resultCard = null;
        }
        if (this._categoryTag && typeof this._categoryTag.destroy === 'function') {
            this._categoryTag.destroy();
            this._categoryTag = null;
        }

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 释放数据引用 */
        this.container = null;
        this._resultData = null;
        this._boundHandlers = {};

        console.log('[ResultPage] 结果页已销毁');
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染结果页面 HTML 骨架
     * 包含导航栏、结果卡片容器、分类标签容器、操作按钮组
     * @private
     */
    _render() {
        /* 检测是否为演示模式（从API返回数据中读取） */
        const isDemoMode = this._resultData?.is_demo_mode || false;

        this.container.innerHTML = `
            <!-- 导航栏 -->
            <div class="result-nav">
                <button class="nav-back-btn" id="resultBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="result-nav-title">识别结果</h2>
            </div>

            ${isDemoMode ? `
            <!-- 演示模式警告标识 -->
            <div class="demo-mode-badge">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 10v4h2v-4h-2zm0 6v2h2v-2h-2z"/>
                </svg>
                <span>演示模式 · 结果仅供参考</span>
            </div>
            ` : ''}

            <!-- 结果卡片区域 (F-1.3.1~F-1.3.5) -->
            <div id="resultCardContainer"></div>

            <!-- 分类标签区域 -->
            <div id="categoryTagContainer"></div>

            <!-- 操作按钮组 -->
            <div class="card result-actions-card">
                <div class="btn-group result-btn-group">
                    <button class="btn btn-primary" id="guideDetailBtn">
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="white" stroke-width="2" fill="none">
                            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                        </svg>
                        查看投放指引
                    </button>
                    <button class="btn btn-secondary" id="continueBtn">
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
                            <polyline points="1 4 1 10 7 10"/>
                            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                        </svg>
                        继续识别
                    </button>
                    <button class="btn btn-secondary" id="shareBtn">
                        <svg viewBox="0 0 24 24" width="17" height="17" stroke="currentColor" stroke-width="2" fill="none">
                            <circle cx="18" cy="5" r="3"/>
                            <circle cx="6" cy="12" r="3"/>
                            <circle cx="18" cy="19" r="3"/>
                            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                        </svg>
                        分享结果
                    </button>
                    <button class="btn btn-secondary" id="homeBtn">
                        <svg viewBox="0 0 24 24" width="17" height="17" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                            <polyline points="9 22 9 12 15 12 15 22"/>
                        </svg>
                        返回首页
                    </button>
                </div>
            </div>
        `;
    }

    // ==================== 私有方法：组件渲染 ====================

    /**
     * 渲染 ResultCard 和 CategoryTag 组件
     * F-1.3.1 ~ F-1.3.5 全部任务在此完成
     * @private
     */
    _renderComponents() {
        /* ---- 渲染主结果卡片 (ResultCard) ---- */
        const cardContainer = document.getElementById('resultCardContainer');
        if (cardContainer && this._resultData) {
            this._resultCard = new ResultCard();
            this._resultCard.render(cardContainer);
            this._resultCard.update(this._resultData);
        }

        /* ---- 渲染分类标签 (CategoryTag) ---- */
        const tagContainer = document.getElementById('categoryTagContainer');
        if (tagContainer && this._resultData?.category) {
            this._categoryTag = new CategoryTag();
            this._categoryTag.render(tagContainer);
            this._categoryTag.updateByName(this._resultData.category);
        }
    }

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定操作按钮事件
     * @private
     */
    _bindEvents() {
        this._boundHandlers.guide = () => this._handleGuide();
        const guideBtn = document.getElementById('guideDetailBtn');
        if (guideBtn) {
            guideBtn.addEventListener('click', this._boundHandlers.guide);
        }

        this._boundHandlers.continue = () => this._handleContinue();
        const continueBtn = document.getElementById('continueBtn');
        if (continueBtn) {
            continueBtn.addEventListener('click', this._boundHandlers.continue);
        }

        /* 分享结果 — 复制分享文本到剪贴板 */
        this._boundHandlers.share = () => this._handleShare();
        const shareBtn = document.getElementById('shareBtn');
        if (shareBtn) {
            shareBtn.addEventListener('click', this._boundHandlers.share);
        }

        /* 返回首页 */
        this._boundHandlers.home = () => {
            window.location.hash = '#/';
        };
        const homeBtn = document.getElementById('homeBtn');
        if (homeBtn) {
            homeBtn.addEventListener('click', this._boundHandlers.home);
        }

        /* 导航栏返回按钮 */
        const backBtn = document.getElementById('resultBackBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }
    }

    // ==================== 私有方法：操作处理 ====================

    /**
     * 处理「继续识别」操作
     * 清除当前图片和结果状态，跳转回首页
     * @private
     */
    _handleGuide() {
        const keyword = this._resultData?.label_cn || this._resultData?.label_en || '';
        if (keyword) {
            store.set('currentItemKeyword', keyword);
            window.location.hash = '#/item/' + encodeURIComponent(keyword);
        } else {
            showToast('无法获取物品名称', 'warning');
        }
    }

    _handleContinue() {
        /* 清除 store 中的图片和结果数据 */
        store.remove('selectedImage');
        store.remove('selectedFile');
        store.remove('predictResult');

        /* 跳转首页 */
        window.location.hash = '#/';
    }

    /**
     * 处理「分享结果」操作
     * 构造分享文本并写入剪贴板
     * 使用 navigator.clipboard API（需 HTTPS 环境）
     * @private
     */
    async _handleShare() {
        const shareText = this._getShareText();

        try {
            /* 尝试使用现代 Clipboard API */
            await navigator.clipboard.writeText(shareText);
            showToast('已复制到剪贴板', 'success');

        } catch (clipboardError) {
            /* Clipboard API 降级方案：使用 execCommand */
            console.warn('[ResultPage] Clipboard API 不可用，尝试降级方案:', clipboardError);

            try {
                const textarea = document.createElement('textarea');
                textarea.value = shareText;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showToast('已复制到剪贴板', 'success');

            } catch (fallbackError) {
                console.error('[ResultPage] 复制完全失败:', fallbackError);
                showModal('分享失败', '无法复制到剪贴板，请手动截屏分享', '确定');
            }
        }
    }

    /**
     * 构造分享用的文本内容
     * 格式化输出识别结果的关键信息
     *
     * @returns {string} 格式化的分享文本
     * @private
     */
    _getShareText() {
        const data = this._resultData || {};
        const label = data.label_cn || data.label_en || '未知物品';
        const category = data.category || '未知类别';
        const confidence = data.confidence ? Math.round(data.confidence * 100) : 0;
        const guidance = data.guidance || '';

        let text = `【校园垃圾分类AI助手】\n`;
        text += `━━━━━━━━━━━━━━━\n`;
        text += `📦 物品名称：${label}\n`;
        text += `🏷️ 分类归属：${category}\n`;
        text += `📊 置信度：${confidence}%\n`;

        if (guidance) {
            text += `💡 投放指引：${guidance}\n`;
        }

        text += `━━━━━━━━━━━━━━━\n`;
        text += `由 YOLOv8 深度学习引擎提供支持`;

        return text;
    }

    _saveToLocalHistory(predictResult) {
        try {
            const imgDataUrl = store.get('selectedImage');
            storage.saveHistory({
                thumbnail: imgDataUrl || '',
                category: predictResult.category || '未知类别',
                category_id: predictResult.category_id ?? 0,
                confidence: predictResult.confidence || 0,
                item_name: predictResult.label_cn || predictResult.label_en || '未知物品',
                bin_color: predictResult.bin_color || '#666',
                guidance: predictResult.guidance || ''
            });
            console.log('[ResultPage] 已保存识别记录到 localStorage (F-1.5.1)');
        } catch (e) {
            console.warn('[ResultPage] 保存本地历史失败:', e);
        }
    }
}

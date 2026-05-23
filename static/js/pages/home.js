/**
 * 首页视图 — 上传区域 + 搜索入口
 *
 * 职责：渲染图片上传区（点击/拖拽/粘贴）、搜索框、语音按钮占位；
 *       选择图片后执行校验→压缩→存储→跳转预览页的完整流程。
 * 容器：#page-home
 */

// ==================== 模块依赖导入 ====================
import { store } from '../store.js';
import { api } from '../api.js';
import { ImageProcessor } from '../utils/image.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';

// ==================== 页面类定义 ====================
export class HomePage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 隐藏的文件选择 input 元素 */
    fileInput = null;

    /** 上传区域 DOM */
    uploadArea = null;

    /** 预览图片 img 元素 */
    previewImg = null;

    /** 搜索输入框 */
    searchInput = null;

    /** 语音按钮（占位） */
    voiceBtn = null;

    /** 绑定的事件处理器引用集合，用于 destroy 时移除 */
    _boundHandlers = {};

    /**
     * 初始化首页视图
     * 渲染上传区域、搜索框、绑定交互事件
     */
    init() {
        this.container = document.getElementById('page-home');
        if (!this.container) {
            console.error('[HomePage] 容器 #page-home 不存在');
            return;
        }

        /* 渲染页面结构 */
        this._render();
        /* 缓存关键 DOM 引用 */
        this._cacheDOM();
        /* 绑定所有交互事件 */
        this._bindEvents();

        console.log('[HomePage] 首页初始化完成');
    }

    /**
     * 销毁首页视图
     * 移除所有事件监听、清空容器内容、释放 DOM 引用
     */
    destroy() {
        // 移除拖拽事件
        if (this.uploadArea) {
            this.uploadArea.removeEventListener('dragenter', this._boundHandlers.dragenter);
            this.uploadArea.removeEventListener('dragover', this._boundHandlers.dragover);
            this.uploadArea.removeEventListener('dragleave', this._boundHandlers.dragleave);
            this.uploadArea.removeEventListener('drop', this._boundHandlers.drop);
        }

        // 移除文件选择变化事件
        if (this.fileInput) {
            this.fileInput.removeEventListener('change', this._boundHandlers.change);
        }

        // 移除搜索回车事件
        if (this.searchInput) {
            this.searchInput.removeEventListener('keydown', this._boundHandlers.keydown);
        }

        // 移除粘贴事件（全局）
        document.removeEventListener('paste', this._boundHandlers.paste);

        // 清空容器
        if (this.container) {
            this.container.innerHTML = '';
        }

        // 释放引用
        this.container = null;
        this.fileInput = null;
        this.uploadArea = null;
        this.previewImg = null;
        this.searchInput = null;
        this.voiceBtn = null;
        this._boundHandlers = {};

        console.log('[HomePage] 首页已销毁');
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染首页完整 HTML 结构
     * 包含上传区域（F-1.2.1 优化）、搜索框、语音按钮占位
     * @private
     */
    _render() {
        this.container.innerHTML = `
            <!-- 页面标题区 -->
            <div class="home-header">
                <div class="home-header-inner">
                    <div class="home-logo">
                        <svg viewBox="0 0 24 24" width="24" height="24" fill="white">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                        </svg>
                    </div>
                    <h1 class="home-title">校园垃圾分类AI助手</h1>
                </div>
                <p class="home-subtitle">拍照识别 · 语音搜索 · 智能分类</p>
            </div>

            <!-- 主操作卡片 -->
            <div class="card home-card">
                <!-- 上传区域：大尺寸虚线边框 ≥200px高 -->
                <div class="upload-area" id="homeUploadArea">
                    <div class="upload-icon-wrap">
                        <svg viewBox="0 0 24 24" width="28" height="28" stroke="white" stroke-width="2" fill="none">
                            <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
                        </svg>
                    </div>
                    <div class="upload-text">点击或拖拽图片到此处</div>
                    <div class="upload-hint">支持 JPG / PNG / WebP / GIF 格式</div>
                    <img id="homePreviewImg" alt="预览图" class="preview-image">
                </div>

                <!-- 隐藏的文件输入框 -->
                <input type="file"
                       id="homeFileInput"
                       class="hidden-input"
                       accept="image/*"
                       capture="environment">

                <!-- 分割线 -->
                <div class="divider"><span>或</span></div>

                <!-- 搜索区域 -->
                <div class="search-box">
                    <input type="text"
                           id="homeSearchInput"
                           class="search-input"
                           placeholder="输入垃圾名称搜索..."
                           autocomplete="off">
                    <button class="voice-btn" id="homeVoiceBtn" title="语音输入" aria-label="语音输入">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </button>
                </div>
            </div>

            <!-- 底部提示 -->
            <div class="home-footer">
                <p>基于 YOLOv8 深度学习引擎 · 保护环境从分类开始</p>
            </div>
        `;
    }

    // ==================== 私有方法：DOM 缓存 ====================

    /**
     * 缓存高频使用的 DOM 元素引用，避免重复查询
     * @private
     */
    _cacheDOM() {
        this.fileInput = document.getElementById('homeFileInput');
        this.uploadArea = document.getElementById('homeUploadArea');
        this.previewImg = document.getElementById('homePreviewImg');
        this.searchInput = document.getElementById('homeSearchInput');
        this.voiceBtn = document.getElementById('homeVoiceBtn');
    }

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定全部交互事件（上传、拖拽、粘贴、搜索、语音）
     * F-1.2.5 拖拽上传 + F-1.2.6 粘贴上传
     * @private
     */
    _bindEvents() {
        const self = this;

        /* ---- 点击上传区域触发文件选择 ---- */
        if (this.uploadArea) {
            this.uploadArea.addEventListener('click', () => {
                this.fileInput?.click();
            });
        }

        /* ---- 文件选择变化处理 ---- */
        this._boundHandlers.change = (e) => this._handleFileSelect(e);
        if (this.fileInput) {
            this.fileInput.addEventListener('change', this._boundHandlers.change);
        }

        /* ---- 拖拽上传事件组 (F-1.2.5) ---- */
        this._boundHandlers.dragenter = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.uploadArea?.classList.add('active');
        };
        this._boundHandlers.dragover = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.uploadArea?.classList.add('active');
        };
        this._boundHandlers.dragleave = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.uploadArea?.classList.remove('active');
        };
        this._boundHandlers.drop = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.uploadArea?.classList.remove('active');
            this._handleDrop(e);
        };

        if (this.uploadArea) {
            this.uploadArea.addEventListener('dragenter', this._boundHandlers.dragenter);
            this.uploadArea.addEventListener('dragover', this._boundHandlers.dragover);
            this.uploadArea.addEventListener('dragleave', this._boundHandlers.dragleave);
            this.uploadArea.addEventListener('drop', this._boundHandlers.drop);
        }

        /* ---- 粘贴上传事件 (F-1.2.6) ---- */
        this._boundHandlers.paste = (e) => this._handlePaste(e);
        document.addEventListener('paste', this._boundHandlers.paste);

        /* ---- 搜索回车跳转 ---- */
        this._boundHandlers.keydown = (e) => {
            if (e.key === 'Enter') {
                const query = this.searchInput?.value.trim();
                if (query) {
                    // 存储搜索关键词到 store，跳转搜索结果页
                    store.set('searchQuery', query);
                    window.location.hash = '#/search?q=' + encodeURIComponent(query);
                }
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', this._boundHandlers.keydown);
        }

        /* ---- 语音按钮占位（阶段二实现）---- */
        if (this.voiceBtn) {
            this.voiceBtn.addEventListener('click', () => {
                showToast('语音识别功能即将上线，敬请期待');
            });
        }
    }

    // ==================== 私有方法：文件处理核心逻辑 ====================

    /**
     * 处理文件选择（input change 事件）
     * 流程：validate → compress → store存储 → 跳转#/preview
     * @param {Event} e - 文件选择变化事件
     * @private
     */
    async _handleFileSelect(e) {
        const file = e.target.files?.[0];
        if (!file) return;

        await this._processImage(file);
    }

    /**
     * 处理拖拽释放的文件 (F-1.2.5)
     * 从 dataTransfer 提取图片文件并进入处理流程
     * @param {DragEvent} e - 拖拽释放事件
     * @private
     */
    async _handleDrop(e) {
        const files = e.dataTransfer?.files;
        if (!files || files.length === 0) return;

        const file = files[0];
        /* 仅接受图片类型 */
        if (!file.type.startsWith('image/')) {
            showToast('请选择图片文件', 'warning');
            return;
        }

        await this._processImage(file);
    }

    /**
     * 处理剪贴板粘贴的图片 (F-1.2.6)
     * 从 clipboardData.items 中提取图片并进入处理流程
     * @param {ClipboardEvent} e - 粘贴事件
     * @private
     */
    async _handlePaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;

        /* 遍历剪贴板条目，查找图片类型 */
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) {
                    await this._processImage(file);
                    break; /* 只处理第一张图片 */
                }
            }
        }
    }

    /**
     * 图片处理核心流水线
     * 校验 → 压缩 → 存储 → 路由跳转
     *
     * @param {File} file - 原始图片 File 对象
     * @private
     */
    async _processImage(file) {
        try {
            /* 第一步：格式与大小校验 (F-1.2.1) */
            const validation = ImageProcessor.validate(file);
            if (!validation.valid) {
                showToast(validation.message, 'error');
                return;
            }

            /* 显示加载状态 */
            showLoading('正在处理图片...');

            /* 第二步：图片压缩 */
            const compressedBlob = await ImageProcessor.compress(file, 2048);

            /* 第三步：生成预览 URL 并显示 */
            const objectUrl = URL.createObjectURL(compressedBlob);
            if (this.previewImg) {
                this.previewImg.src = objectUrl;
                this.previewImg.style.display = 'block';
                this.uploadArea?.classList.add('has-image');
            }

            /* 第四步：转换为 Base64 并存入 store */
            const base64 = await ImageProcessor.toBase64(compressedBlob);
            store.set('selectedImage', base64);
            store.set('selectedFileName', file.name);

            hideLoading();

            /* 第五步：延迟跳转到预览确认页 */
            setTimeout(() => {
                window.location.hash = '#/preview';
            }, 300);

        } catch (error) {
            hideLoading();
            console.error('[HomePage] 图片处理失败:', error);
            showToast('图片处理失败，请重试或更换图片', 'error');
        }
    }
}

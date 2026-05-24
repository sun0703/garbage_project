/**
 * 首页视图 — 上传区域 + 搜索入口 + 语音识别 + 搜索联想
 *
 * 职责：渲染图片上传区（点击/拖拽/粘贴）、搜索框、语音按钮、搜索联想；
 *       选择图片后执行校验→压缩→存储→跳转预览页的完整流程；
 *       语音识别结果自动填充搜索框并跳转搜索页；
 *       搜索联想实时提示匹配物品。
 * 容器：#page-home
 */

import { store } from '../store.js';
import { api } from '../api.js';
import { ImageProcessor } from '../utils/image.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { VoiceButton } from '../components/voice-btn.js';
import { SearchSuggest } from '../components/search-suggest.js';
import { SearchHistory } from '../utils/search-history.js';

export class HomePage {
    container = null;
    fileInput = null;
    uploadArea = null;
    previewImg = null;
    searchInput = null;
    voiceBtnContainer = null;
    voiceButton = null;
    searchSuggest = null;
    _boundHandlers = {};

    init() {
        this.container = document.getElementById('page-home');
        if (!this.container) {
            console.error('[HomePage] 容器 #page-home 不存在');
            return;
        }

        this._render();
        this._cacheDOM();
        this._bindEvents();
        this._initVoiceButton();
        this._initSearchSuggest();

        console.log('[HomePage] 首页初始化完成');
    }

    destroy() {
        if (this.uploadArea) {
            this.uploadArea.removeEventListener('dragenter', this._boundHandlers.dragenter);
            this.uploadArea.removeEventListener('dragover', this._boundHandlers.dragover);
            this.uploadArea.removeEventListener('dragleave', this._boundHandlers.dragleave);
            this.uploadArea.removeEventListener('drop', this._boundHandlers.drop);
        }

        if (this.fileInput) {
            this.fileInput.removeEventListener('change', this._boundHandlers.change);
        }

        if (this.searchInput) {
            this.searchInput.removeEventListener('keydown', this._boundHandlers.keydown);
        }

        document.removeEventListener('paste', this._boundHandlers.paste);

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
        this.fileInput = null;
        this.uploadArea = null;
        this.previewImg = null;
        this.searchInput = null;
        this.voiceBtnContainer = null;
        this._boundHandlers = {};

        console.log('[HomePage] 首页已销毁');
    }

    _render() {
        this.container.innerHTML = `
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

            <div class="card home-card">
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

                <input type="file"
                       id="homeFileInput"
                       class="hidden-input"
                       accept="image/*"
                       capture="environment">

                <div class="divider"><span>或</span></div>

                <div class="search-box">
                    <input type="text"
                           id="homeSearchInput"
                           class="search-input"
                           placeholder="输入垃圾名称或拼音搜索..."
                           autocomplete="off">
                    <div id="homeVoiceBtnContainer" class="voice-btn-slot"></div>
                </div>
            </div>

            <div class="home-footer">
                <p>基于 YOLOv8 深度学习引擎 · 保护环境从分类开始</p>
            </div>
        `;
    }

    _cacheDOM() {
        this.fileInput = document.getElementById('homeFileInput');
        this.uploadArea = document.getElementById('homeUploadArea');
        this.previewImg = document.getElementById('homePreviewImg');
        this.searchInput = document.getElementById('homeSearchInput');
        this.voiceBtnContainer = document.getElementById('homeVoiceBtnContainer');
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
        store.set('searchQuery', label);
        window.location.hash = '#/search?q=' + encodeURIComponent(label);
    }

    _handleVoiceResult(text) {
        if (!text || !text.trim()) return;

        const query = text.trim();

        if (this.searchInput) {
            this.searchInput.value = query;
        }

        SearchHistory.add(query);
        store.set('searchQuery', query);
        showToast(`识别到: ${query}`, 'success');

        setTimeout(() => {
            window.location.hash = '#/search?q=' + encodeURIComponent(query);
        }, 500);
    }

    _handleVoiceError(code, message) {
        if (code === 'unsupported') {
            showToast(message, 'warning', 4000);
        } else if (code !== 'aborted') {
            showToast(message, 'error');
        }
    }

    _bindEvents() {
        if (this.uploadArea) {
            this.uploadArea.addEventListener('click', () => {
                this.fileInput?.click();
            });
        }

        this._boundHandlers.change = (e) => this._handleFileSelect(e);
        if (this.fileInput) {
            this.fileInput.addEventListener('change', this._boundHandlers.change);
        }

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

        this._boundHandlers.paste = (e) => this._handlePaste(e);
        document.addEventListener('paste', this._boundHandlers.paste);

        this._boundHandlers.keydown = (e) => {
            if (e.key === 'Enter') {
                const query = this.searchInput?.value.trim();
                if (query) {
                    SearchHistory.add(query);
                    store.set('searchQuery', query);
                    window.location.hash = '#/search?q=' + encodeURIComponent(query);
                }
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', this._boundHandlers.keydown);
        }
    }

    async _handleFileSelect(e) {
        const file = e.target.files?.[0];
        if (!file) return;
        await this._processImage(file);
    }

    async _handleDrop(e) {
        const files = e.dataTransfer?.files;
        if (!files || files.length === 0) return;

        const file = files[0];
        if (!file.type.startsWith('image/')) {
            showToast('请选择图片文件', 'warning');
            return;
        }
        await this._processImage(file);
    }

    async _handlePaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;

        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) {
                    await this._processImage(file);
                    break;
                }
            }
        }
    }

    async _processImage(file) {
        try {
            const validation = ImageProcessor.validate(file);
            if (!validation.valid) {
                showToast(validation.message, 'error');
                return;
            }

            showLoading('正在处理图片...');

            const compressedBlob = await ImageProcessor.compress(file, {
                maxWidth: 1024,
                maxHeight: 1024,
                quality: 0.85,
                mimeType: 'image/jpeg'
            });

            const objectUrl = URL.createObjectURL(compressedBlob);
            if (this.previewImg) {
                this.previewImg.src = objectUrl;
                this.previewImg.style.display = 'block';
                this.uploadArea?.classList.add('has-image');
            }

            const base64 = await ImageProcessor.blobToBase64(compressedBlob);
            store.set('selectedImage', base64);
            store.set('selectedFileName', file.name);

            hideLoading();

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

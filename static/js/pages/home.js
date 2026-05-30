// 首页 — 上传区域 + 搜索入口
// 选图后走校验→压缩→存储→跳转预览的流程

import { store } from '../store.js';
import { api } from '../api.js';
import { ImageProcessor } from '../utils/image.js';
import { showToast, showLoading, hideLoading } from '../utils/ui.js';
import { escapeHtml } from '../utils/escape.js';
import { VoiceButton } from '../components/voice-btn.js';
import { SearchSuggest } from '../components/search-suggest.js';

export class HomePage {
    container = null;
    fileInput = null;
    uploadArea = null;
    previewImg = null;
    searchInput = null;
    voiceBtn = null;
    _boundHandlers = {};
    _suggest = null;
    predictBtn = null;
    loadingOverlayEl = null;
    loadingTextEl = null;
    errorMsgEl = null;
    resultSection = null;
    searchResultSection = null;
    _selectedImage = null;

    init() {
        this.container = document.getElementById('page-home');
        if (!this.container) {
            console.error('[HomePage] 容器 #page-home 不存在');
            return;
        }

        this._render();
        this._cacheDOM();
        this._bindEvents();
        this._loadAchievements();
        this._checkLoginStatus();

        document.body.setAttribute('data-home-active', '');

        console.log('[HomePage] 首页初始化完成');
    }

    destroy() {
        document.body.removeAttribute('data-home-active');

        if (this.uploadArea) {
            this.uploadArea.removeEventListener('click', this._boundHandlers.uploadClick);
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

        if (this.predictBtn) {
            this.predictBtn.removeEventListener('click', this._boundHandlers.predictClick);
        }

        const resetBtn = document.getElementById('homeResetBtn');
        if (resetBtn) {
            resetBtn.removeEventListener('click', this._boundHandlers.resetClick);
        }

        const loginLink = document.getElementById('homeLoginLink');
        if (loginLink) {
            loginLink.removeEventListener('click', this._boundHandlers.loginLink);
        }

        if (this._suggest) {
            this._suggest.destroy();
            this._suggest = null;
        }

        document.removeEventListener('paste', this._boundHandlers.paste);

        if (this._voiceButton) {
            this._voiceButton.destroy();
            this._voiceButton = null;
        }

        /* 释放摄像头资源 */
        this._closeCamera();

        if (this.container) {
            this.container.innerHTML = '';
        }

        this.container = null;
        this.fileInput = null;
        this.uploadArea = null;
        this.previewImg = null;
        this.predictBtn = null;
        this.searchInput = null;
        this.voiceBtn = null;
        this.loadingOverlayEl = null;
        this.loadingTextEl = null;
        this.errorMsgEl = null;
        this.resultSection = null;
        this.searchResultSection = null;
        this._selectedImage = null;
        this._boundHandlers = {};

        console.log('[HomePage] 首页已销毁');
    }

    /* ---- 渲染 ---- */

    _render() {
        this.container.innerHTML = `
            <div class="page__content container">
            <!-- 页面标题区 -->
            <div class="home-header">
                <div class="home-header__logo">
                    <svg viewBox="0 0 24 24" width="28" height="28" fill="white">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                    </svg>
                </div>
                <h1 class="home-header__title">垃圾分类AI助手</h1>
                <p class="home-header__subtitle">拍照识别 · 语音搜索 · 智能分类</p>
                <p style="margin-top:6px;"><a href="javascript:void(0)" id="homeLoginLink" style="color:#2D9B5E;font-size:13px;font-weight:500;text-decoration:none;">登录 / 注册</a> <span id="homeLoginStatus" style="font-size:12px;color:#95A0AA;"></span></p>
            </div>

            <!-- 历史记录抽屉按钮 -->
            <button class="history-drawer-toggle" id="homeHistoryToggle" title="识别历史">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                <span class="history-drawer-toggle__label">历史</span>
            </button>

            <!-- 主操作卡片 -->
            <div class="card home-card">
                <!-- 上传区域 -->
                <div class="upload-area" id="homeUploadArea">
                    <div class="upload-area__icon-wrap">
                        <svg viewBox="0 0 24 24" width="28" height="28" stroke="white" stroke-width="2" fill="none">
                            <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
                        </svg>
                    </div>
                    <div class="upload-area__text">点击或拖拽图片到此处</div>
                    <div class="upload-area__hint">支持 JPG / PNG / WebP / GIF 格式</div>
                    <img id="homePreviewImg" alt="预览图" class="upload-area__preview">
                </div>

                <div class="upload-actions">
                    <button class="btn btn-camera" id="homeCameraBtn" title="打开摄像头拍照">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                            <circle cx="12" cy="13" r="4"/>
                        </svg>
                        拍照识别
                    </button>
                    <button class="btn btn-upload-file" id="homeUploadBtn" title="从相册选择图片">
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                        选择图片
                    </button>
                </div>

                <!-- 摄像头预览区域（默认隐藏） -->
                <div class="camera-preview hidden" id="homeCameraPreview">
                    <video id="homeCameraVideo" autoplay playsinline></video>
                    <canvas id="homeCameraCanvas" class="hidden"></canvas>
                    <div class="camera-controls">
                        <button class="btn btn-secondary camera-close-btn" id="homeCameraCloseBtn">✕ 关闭</button>
                        <button class="btn btn-primary camera-capture-btn" id="homeCameraCaptureBtn">
                            <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                                <circle cx="12" cy="12" r="10"/>
                                <circle cx="12" cy="12" r="6" fill="#fff"/>
                            </svg>
                            拍照
                        </button>
                    </div>
                </div>

                <input type="file"
                       id="homeFileInput"
                       class="hidden-input"
                       accept="image/*">

                <div class="loading-overlay hidden" id="homeLoadingOverlay">
                    <div class="spinner"></div>
                    <div class="loading-text" id="homeLoadingText">正在识别中...</div>
                </div>

                <div class="error-msg hidden" id="homeErrorMsg"></div>

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

                <div class="btn-group">
                    <button class="btn btn-primary" id="homePredictBtn" disabled>开始识别</button>
                    <button class="btn btn-secondary" id="homeResetBtn">
                        <svg viewBox="0 0 24 24" style="width:17px;height:17px;stroke:currentColor;stroke-width:2;fill:none"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                        重置
                    </button>
                </div>
            </div>

            <div class="card result-section hidden" id="homeResultSection">
                <div class="result-header">
                    <span class="category-badge" id="homeCategoryBadge">可回收物</span>
                    <div class="item-name" id="homeItemName">塑料瓶</div>
                    <div class="confidence-row">
                        <span>置信度</span>
                        <div class="confidence-bar">
                            <div class="confidence-fill high" id="homeConfidenceFill" style="width: 0%"></div>
                        </div>
                        <span id="homeConfidenceText">92%</span>
                    </div>
                </div>
                <div class="guidance-box">
                    <div class="guidance-label">投放指引</div>
                    <div class="guidance-text" id="homeGuidanceText"></div>
                </div>
                <div class="inference-info" id="homeInferenceInfo"></div>
            </div>

            <div class="card result-section hidden" id="homeSearchResultSection">
                <div class="guidance-label" style="margin-bottom:10px;">搜索结果</div>
                <div class="search-results" id="homeSearchResults"></div>
            </div>

            <div class="card" id="homeAchievementsCard">
                <div class="guidance-label">🏆 环保成就</div>
                <div class="achievements-grid" id="homeAchievementsGrid">
                    <p class="loading-text" style="text-align:center;padding:12px;">加载中...</p>
                </div>
            </div>

            <div class="home-footer">
                <p>基于 YOLOv8 深度学习引擎 · 保护环境从分类开始</p>
            </div>

            <!-- 历史记录抽屉 -->
            <div class="history-drawer-overlay" id="homeHistoryOverlay"></div>
            <aside class="history-drawer" id="homeHistoryDrawer">
                <div class="history-drawer__header">
                    <h3>识别历史</h3>
                    <button class="history-drawer__close" id="homeHistoryClose">&times;</button>
                </div>
                <div class="history-drawer__body" id="homeHistoryBody">
                    <p style="color:#95A0AA;text-align:center;padding:20px;">加载中...</p>
                </div>
                <div class="history-drawer__footer">
                    <a href="#/history" class="history-drawer__more">查看全部历史</a>
                </div>
            </aside>
            </div>
        `;
    }

    _cacheDOM() {
        this.fileInput = document.getElementById('homeFileInput');
        this.uploadArea = document.getElementById('homeUploadArea');
        this.previewImg = document.getElementById('homePreviewImg');
        this.predictBtn = document.getElementById('homePredictBtn');
        this.searchInput = document.getElementById('homeSearchInput');
        this.voiceBtn = document.getElementById('homeVoiceBtn');
        this.loadingOverlayEl = document.getElementById('homeLoadingOverlay');
        this.loadingTextEl = document.getElementById('homeLoadingText');
        this.errorMsgEl = document.getElementById('homeErrorMsg');
        this.resultSection = document.getElementById('homeResultSection');
        this.searchResultSection = document.getElementById('homeSearchResultSection');

        /* 摄像头相关DOM */
        this.cameraBtn = document.getElementById('homeCameraBtn');
        this.uploadBtn = document.getElementById('homeUploadBtn');
        this.cameraPreview = document.getElementById('homeCameraPreview');
        this.cameraVideo = document.getElementById('homeCameraVideo');
        this.cameraCanvas = document.getElementById('homeCameraCanvas');
        this.cameraCloseBtn = document.getElementById('homeCameraCloseBtn');
        this.cameraCaptureBtn = document.getElementById('homeCameraCaptureBtn');
        this._cameraStream = null;
    }

    /* ---- 事件绑定 ---- */

    _bindEvents() {
        const self = this;

        // 历史记录抽屉
        const historyToggle = document.getElementById('homeHistoryToggle');
        const historyOverlay = document.getElementById('homeHistoryOverlay');
        const historyClose = document.getElementById('homeHistoryClose');
        const historyDrawer = document.getElementById('homeHistoryDrawer');

        const openDrawer = () => {
            if (historyDrawer) historyDrawer.classList.add('open');
            if (historyOverlay) historyOverlay.classList.add('open');
            this._loadDrawerHistory();
        };
        const closeDrawer = () => {
            if (historyDrawer) historyDrawer.classList.remove('open');
            if (historyOverlay) historyOverlay.classList.remove('open');
        };

        if (historyToggle) historyToggle.addEventListener('click', openDrawer);
        if (historyOverlay) historyOverlay.addEventListener('click', closeDrawer);
        if (historyClose) historyClose.addEventListener('click', closeDrawer);

        // 点击上传区域触发文件选择
        this._boundHandlers.uploadClick = (e) => {
            if (!this.fileInput) {
                console.error('[HomePage] fileInput 元素不存在！');
                return;
            }
            this.uploadArea?.classList.add('clicked');
            setTimeout(() => this.uploadArea?.classList.remove('clicked'), 200);
            this.fileInput.click();
        };
        if (this.uploadArea) {
            this.uploadArea.addEventListener('click', this._boundHandlers.uploadClick);
        }

        // 文件选择变化
        this._boundHandlers.change = (e) => this._onFileSelect(e);
        if (this.fileInput) {
            this.fileInput.addEventListener('change', this._boundHandlers.change);
        }

        // 拖拽上传
        this._boundHandlers.dragenter = (e) => {
            e.preventDefault(); e.stopPropagation();
            this.uploadArea?.classList.add('active');
        };
        this._boundHandlers.dragover = (e) => {
            e.preventDefault(); e.stopPropagation();
            this.uploadArea?.classList.add('active');
        };
        this._boundHandlers.dragleave = (e) => {
            e.preventDefault(); e.stopPropagation();
            this.uploadArea?.classList.remove('active');
        };
        this._boundHandlers.drop = (e) => {
            e.preventDefault(); e.stopPropagation();
            this.uploadArea?.classList.remove('active');
            this._onDrop(e);
        };

        if (this.uploadArea) {
            this.uploadArea.addEventListener('dragenter', this._boundHandlers.dragenter);
            this.uploadArea.addEventListener('dragover', this._boundHandlers.dragover);
            this.uploadArea.addEventListener('dragleave', this._boundHandlers.dragleave);
            this.uploadArea.addEventListener('drop', this._boundHandlers.drop);
        }

        // 粘贴上传
        this._boundHandlers.paste = (e) => {
            this._onPaste(e);
            const items = e.clipboardData?.items;
            if (items) {
                for (const item of items) {
                    if (item.type.startsWith('image/')) {
                        const file = item.getAsFile();
                        if (file) {
                            showToast(`已粘贴图片: ${file.name || '截图'}`, 'success', 1500);
                            break;
                        }
                    }
                }
            }
        };
        document.addEventListener('paste', this._boundHandlers.paste);

        // 搜索回车跳转
        this._boundHandlers.keydown = (e) => {
            if (e.key === 'Enter') {
                const query = this.searchInput?.value.trim();
                if (query) {
                    store.setState('searchQuery', query);
                    window.location.hash = '#/search?q=' + encodeURIComponent(query);
                }
            }
        };
        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', this._boundHandlers.keydown);
        }

        // 搜索联想下拉
        this._suggest = new SearchSuggest({
            inputEl: this.searchInput,
            onSelect: (keyword) => {
                store.setState('searchQuery', keyword);
                window.location.hash = '#/search?q=' + encodeURIComponent(keyword);
            }
        });

        // 语音按钮
        if (this.voiceBtn) {
            this._voiceButton = new VoiceButton({
                btnEl: this.voiceBtn,
                onResult: (corrected, changed, original) => {
                    if (this.searchInput) {
                        this.searchInput.value = corrected;
                        store.setState('searchQuery', corrected);
                        window.location.hash = '#/search?q=' + encodeURIComponent(corrected);
                    }
                    if (changed) {
                        showToast(`已自动纠正: "${original}" → "${corrected}"`, 'success', 2000);
                    }
                },
                onError: (errorCode, message) => {
                    console.warn('[HomePage] 语音识别错误:', errorCode, message);
                },
            });
        }

        // 开始识别按钮
        this._boundHandlers.predictClick = () => {
            if (this._selectedImage) {
                store.setState('selectedImage', this._selectedImage);
                window.location.hash = '#/preview';
            }
        };
        if (this.predictBtn) {
            this.predictBtn.addEventListener('click', this._boundHandlers.predictClick);
        }

        // 重置按钮
        this._boundHandlers.resetClick = () => {
            this._selectedImage = null;
            if (this.fileInput) this.fileInput.value = '';
            if (this.previewImg) { this.previewImg.src = ''; this.previewImg.style.display = ''; }
            if (this.uploadArea) this.uploadArea.classList.remove('has-image');
            if (this.predictBtn) this.predictBtn.disabled = true;
            this._hideError();
            this._hideResults();
            this._hideLoading();
        };
        const resetBtn = document.getElementById('homeResetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', this._boundHandlers.resetClick);
        }

        // 登录链接
        this._boundHandlers.loginLink = () => this._showLoginModal();
        const loginLink = document.getElementById('homeLoginLink');
        if (loginLink) {
            loginLink.addEventListener('click', this._boundHandlers.loginLink);
        }

        /* ---- 摄像头拍照功能 ---- */
        if (this.cameraBtn) {
            this.cameraBtn.addEventListener('click', () => this._openCamera());
        }
        if (this.uploadBtn) {
            this.uploadBtn.addEventListener('click', () => this.fileInput?.click());
        }
        if (this.cameraCloseBtn) {
            this.cameraCloseBtn.addEventListener('click', () => this._closeCamera());
        }
        if (this.cameraCaptureBtn) {
            this.cameraCaptureBtn.addEventListener('click', () => this._capturePhoto());
        }
    }

    /* 打开摄像头 */
    async _openCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showToast('您的浏览器不支持摄像头功能', 'warning');
            return;
        }

        try {
            /* 请求后置摄像头（优先），允许切换到前置 */
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false
            });

            this._cameraStream = stream;

            if (this.cameraVideo && this.cameraPreview) {
                this.cameraVideo.srcObject = stream;
                this.cameraPreview.classList.remove('hidden');
                this.uploadArea?.classList.add('hidden');

                /* 滚动到摄像头预览区域 */
                this.cameraPreview.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        } catch (error) {
            let msg = '无法访问摄像头';
            if (error.name === 'NotAllowedError') {
                msg = '请授权使用摄像头权限';
            } else if (error.name === 'NotFoundError') {
                msg = '未检测到摄像头设备';
            } else if (error.name === 'NotReadableError') {
                msg = '摄像头被其他应用占用';
            }
            console.error('[HomePage] 摄像头打开失败:', error);
            showToast(msg, 'warning', 3000);
        }
    }

    /* 关闭摄像头 */
    _closeCamera() {
        if (this._cameraStream) {
            this._cameraStream.getTracks().forEach(track => track.stop());
            this._cameraStream = null;
        }

        if (this.cameraVideo) {
            this.cameraVideo.srcObject = null;
        }

        if (this.cameraPreview) {
            this.cameraPreview.classList.add('hidden');
        }

        if (this.uploadArea) {
            this.uploadArea.classList.remove('hidden');
        }
    }

    /* 拍照并处理图片 */
    _capturePhoto() {
        if (!this.cameraVideo || !this.cameraCanvas || !this._cameraStream) {
            showToast('摄像头未就绪', 'warning');
            return;
        }

        const video = this.cameraVideo;
        const canvas = this.cameraCanvas;

        /* 设置canvas尺寸与视频一致 */
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        /* 将canvas转为Blob文件 */
        canvas.toBlob((blob) => {
            if (!blob) {
                showToast('拍照失败，请重试', 'error');
                return;
            }

            const file = new File([blob], `camera_${Date.now()}.jpg`, { type: 'image/jpeg' });
            console.log(`[HomePage] 拍照成功: ${file.name}, 大小: ${(file.size / 1024).toFixed(1)}KB`);

            /* 关闭摄像头预览 */
            this._closeCamera();

            /* 处理图片（复用现有流程） */
            this._prepareImage(file);

            showToast('拍照成功！正在处理...', 'success', 1500);
        }, 'image/jpeg', 0.92);
    }

    /* ---- 文件处理 ---- */

    // 文件选择回调
    async _onFileSelect(e) {
        const file = e.target.files?.[0];
        if (!file) return;
        await this._prepareImage(file);
    }

    // 拖拽释放回调
    async _onDrop(e) {
        const files = e.dataTransfer?.files;
        if (!files || files.length === 0) return;

        const file = files[0];
        if (!file.type.startsWith('image/')) {
            showToast('请选择图片文件', 'warning');
            return;
        }
        await this._prepareImage(file);
    }

    // 粘贴回调
    async _onPaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;

        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) {
                    await this._prepareImage(file);
                    break; // 只处理第一张
                }
            }
        }
    }

    // 加载抽屉里的历史记录
    async _loadDrawerHistory() {
        const body = document.getElementById('homeHistoryBody');
        if (!body) return;

        try {
            const response = await api.getHistory(1, 10);
            const records = Array.isArray(response) ? response : [];

            if (records.length === 0) {
                body.innerHTML = '<p style="color:#95A0AA;text-align:center;padding:20px;">暂无识别历史</p>';
                return;
            }

            body.innerHTML = records.map(r => {
                const label = r.label_cn || r.label || '未知';
                const category = r.category || '';
                const color = r.bin_color || '#666';
                const confidence = r.confidence ? Math.round(r.confidence * 100) : 0;
                return `
                    <div class="history-drawer__item" data-record-id="${r.id}" style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f0f0f0;cursor:pointer;">
                        <div style="width:36px;height:36px;border-radius:8px;background:${color}15;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <span style="color:${color};font-size:14px;font-weight:600;">${escapeHtml(label.charAt(0))}</span>
                        </div>
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:14px;font-weight:500;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(label)}</div>
                            <div style="font-size:12px;color:var(--text-muted);margin-top:2px;">
                                <span style="color:${color}">${escapeHtml(category)}</span> · ${confidence}%
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // 点击记录回看详情
            const historyDrawer = document.getElementById('homeHistoryDrawer');
            const historyOverlay = document.getElementById('homeHistoryOverlay');
            const closeDrawer = () => {
                if (historyDrawer) historyDrawer.classList.remove('open');
                if (historyOverlay) historyOverlay.classList.remove('open');
            };

            body.querySelectorAll('.history-drawer__item').forEach(el => {
                el.addEventListener('click', () => {
                    const recordId = el.dataset.recordId;
                    const record = records.find(r => r.id === recordId);
                    if (!record) return;
                    store.setState('predictResult', {
                        label_cn: record.label_cn || record.label || '',
                        category: record.category || '',
                        confidence: record.confidence || 0,
                        bin_color: record.bin_color || '#666',
                        guidance: record.guidance || ''
                    });
                    closeDrawer();
                    window.location.hash = '#/result';
                });
            });
        } catch (err) {
            console.error('[HomePage] 加载抽屉历史失败:', err);
            body.innerHTML = '<p style="color:#dc3545;text-align:center;padding:20px;">加载失败</p>';
        }
    }

    // 图片处理流水线：校验 → 压缩 → 存储 → 跳转
    async _prepareImage(file) {
        try {
            const validation = ImageProcessor.validate(file);
            if (!validation.valid) {
                showToast(validation.message, 'error');
                return;
            }

            showLoading('正在处理图片...');

            // 压缩到2MB以内
            const compressedBlob = await ImageProcessor.compress(file, 2048);

            const objectUrl = URL.createObjectURL(compressedBlob);
            if (this.previewImg) {
                this.previewImg.src = objectUrl;
                this.previewImg.style.display = 'block';
                this.uploadArea?.classList.add('has-image');
            }

            const base64 = await ImageProcessor.toBase64(compressedBlob);
            this._selectedImage = base64;
            store.setState('selectedImage', base64);
            store.setState('selectedFileName', file.name);

            // 释放ObjectURL，base64已经存了不需要了
            URL.revokeObjectURL(objectUrl);

            if (this.predictBtn) this.predictBtn.disabled = false;

            hideLoading();

            // 延迟跳转预览页
            setTimeout(() => {
                window.location.hash = '#/preview';
            }, 300);

        } catch (error) {
            hideLoading();
            console.error('[HomePage] 图片处理失败:', error);
            showToast('图片处理失败，请重试或更换图片', 'error');
        }
    }

    /* ---- 加载遮罩与错误提示 ---- */

    _showLoading(text) {
        if (text && this.loadingTextEl) this.loadingTextEl.textContent = text;
        if (this.loadingOverlayEl) this.loadingOverlayEl.classList.remove('hidden');
    }

    _hideLoading() {
        if (this.loadingOverlayEl) this.loadingOverlayEl.classList.add('hidden');
    }

    _showError(msg) {
        if (this.errorMsgEl) {
            this.errorMsgEl.textContent = msg;
            this.errorMsgEl.classList.remove('hidden');
        }
    }

    _hideError() {
        if (this.errorMsgEl) {
            this.errorMsgEl.classList.add('hidden');
            this.errorMsgEl.textContent = '';
        }
    }

    _hideResults() {
        if (this.resultSection) this.resultSection.classList.add('hidden');
        if (this.searchResultSection) this.searchResultSection.classList.add('hidden');
    }

    /* ---- 成就系统 ---- */

    async _loadAchievements() {
        try {
            const d = await api.getAchievements();
            const achievements = d.achievements || d.data || d;
            if (achievements && achievements.length > 0) {
                this._renderAchievements(achievements);
                return;
            }
        } catch (_) {}
        const grid = document.getElementById('homeAchievementsGrid');
        if (grid) grid.innerHTML = '<p style="color:#95A0AA;font-size:13px;text-align:center;padding:12px;">登录后解锁环保成就</p>';
    }

    _renderAchievements(list) {
        const grid = document.getElementById('homeAchievementsGrid');
        if (!grid) return;
        grid.innerHTML = list.map(a => `
            <div class="achievement-badge-card ${a.unlocked ? 'achievement-badge-card--unlocked' : 'achievement-badge-card--locked'}">
                <span class="achievement-badge-card__lock-icon">${a.unlocked ? '' : '🔒'}</span>
                <span class="achievement-badge-card__icon">${escapeHtml(a.icon)}</span>
                <span class="achievement-badge-card__name">${escapeHtml(a.name)}</span>
            </div>
        `).join('');
    }

    _showAchievementToast(ach) {
        const container = document.getElementById('achvToastGlobal');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = 'achv-toast';
        toast.innerHTML = `
            <span class="achv-toast__icon">${escapeHtml(ach.icon)}</span>
            <div class="achv-toast__content">
                <div class="achv-toast__title">🎉 成就解锁!</div>
                <div class="achv-toast__name">${escapeHtml(ach.name)}</div>
                ${ach.points_reward > 0 ? `<div class="achv-toast__reward">+${ach.points_reward} 积分奖励</div>` : ''}
            </div>
            <button class="achv-toast__close" onclick="this.parentElement.classList.add('exiting');setTimeout(()=>this.parentElement.remove(),260)">✕</button>
        `;
        container.appendChild(toast);
        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.add('exiting');
                setTimeout(() => { if (toast.parentElement) toast.remove(); }, 260);
            }
        }, 4000);
    }

    // 处理API返回的新成就通知
    static processAchievements(responseData) {
        const list = responseData.new_achievements;
        if (list && list.length > 0) {
            const instance = new HomePage();
            list.forEach(a => instance._showAchievementToast(a));
            setTimeout(() => instance._loadAchievements(), 500);
        }
    }

    /* ---- 登录状态与登录弹窗 ---- */

    async _checkLoginStatus() {
        try {
            const d = await api.getMe();
            const user = d.user || d;
            if (user && (user.nickname || user.username)) {
                const loginLink = document.getElementById('homeLoginLink');
                const loginStatus = document.getElementById('homeLoginStatus');
                if (loginLink) {
                    loginLink.textContent = user.nickname || user.username;
                    loginLink.style.color = '#1A1A2E';
                    loginLink.style.fontWeight = '600';
                }
                if (loginStatus) loginStatus.textContent = '已登录';
            }
        } catch (_) {}
    }

    // 登录/注册弹窗，三个tab
    _showLoginModal() {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-card">
                <div class="modal-tabs">
                    <button class="modal-tab active" data-tab="login">登录</button>
                    <button class="modal-tab" data-tab="register">注册</button>
                    <button class="modal-tab" data-tab="phone-login">手机号登录</button>
                </div>
                <div id="loginForm" class="modal-form">
                    <form onsubmit="return false;" autocomplete="on">
                    <div class="form-group"><label>用户名</label><input type="text" id="loginUsername" class="form-input" placeholder="请输入用户名" autocomplete="username"></div>
                    <div class="form-group"><label>密码</label><input type="password" id="loginPassword" class="form-input" placeholder="请输入密码" autocomplete="current-password"></div>
                    <button type="submit" class="btn btn-primary btn-block" id="submitLogin">登录</button>
                    <p class="form-error" id="loginError" style="display:none"></p>
                    </form>
                </div>
                <div id="registerForm" class="modal-form" style="display:none">
                    <form onsubmit="return false;" autocomplete="on">
                    <div class="form-group"><label>用户名</label><input type="text" id="regUsername" class="form-input" placeholder="3-20个字符" autocomplete="username"></div>
                    <div class="form-group"><label>密码</label><input type="password" id="regPassword" class="form-input" placeholder="6-32个字符" autocomplete="new-password"></div>
                    <div class="form-group"><label>昵称</label><input type="text" id="regNickname" class="form-input" placeholder="选填" autocomplete="nickname"></div>
                    <button type="submit" class="btn btn-primary btn-block" id="submitRegister">注册</button>
                    <p class="form-error" id="regError" style="display:none"></p>
                    </form>
                </div>
                <div id="phoneLoginForm" class="modal-form" style="display:none">
                    <form onsubmit="return false;" autocomplete="on">
                    <div class="form-group"><label>手机号</label><input type="tel" id="phoneLoginPhone" class="form-input" placeholder="请输入手机号" maxlength="11" autocomplete="tel"></div>
                    <div class="form-group" style="display:flex;gap:8px;align-items:flex-end;">
                        <div style="flex:1;"><label>验证码</label><input type="text" id="phoneLoginCode" class="form-input" placeholder="请输入验证码" maxlength="6" autocomplete="one-time-code"></div>
                        <button type="button" class="btn btn-secondary" id="sendSmsCodeBtn" style="white-space:nowrap;min-width:100px;">发送验证码</button>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block" id="submitPhoneLogin">登录 / 注册</button>
                    <p class="form-error" id="phoneLoginError" style="display:none"></p>
                    </form>
                </div>
                <button class="modal-close" id="closeModal">&times;</button>
            </div>
        `;
        document.body.appendChild(overlay);
        requestAnimationFrame(() => overlay.classList.add('visible'));

        // Tab切换
        overlay.querySelectorAll('.modal-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                overlay.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const tabName = tab.dataset.tab;
                document.getElementById('loginForm').style.display = tabName === 'login' ? 'block' : 'none';
                document.getElementById('registerForm').style.display = tabName === 'register' ? 'block' : 'none';
                document.getElementById('phoneLoginForm').style.display = tabName === 'phone-login' ? 'block' : 'none';
            });
        });

        document.getElementById('closeModal').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

        // 发送验证码
        let smsCooldown = 0;
        const sendSmsBtn = document.getElementById('sendSmsCodeBtn');
        sendSmsBtn.addEventListener('click', async () => {
            const phone = document.getElementById('phoneLoginPhone').value.trim();
            const err = document.getElementById('phoneLoginError');
            err.style.display = 'none';

            if (!/^1[3-9]\d{9}$/.test(phone)) {
                err.textContent = '请输入正确的手机号';
                err.style.display = 'block';
                return;
            }

            if (smsCooldown > 0) return;

            try {
                sendSmsBtn.disabled = true;
                sendSmsBtn.textContent = '发送中...';
                const d = await api.sendSmsCode(phone);
                if (d.success) {
                    // MVP阶段自动填入验证码
                    if (d.code) {
                        document.getElementById('phoneLoginCode').value = d.code;
                        showToast('验证码已发送（开发模式自动填入）', 'success', 2000);
                    } else {
                        showToast('验证码已发送', 'success', 2000);
                    }
                    smsCooldown = 60;
                    const timer = setInterval(() => {
                        smsCooldown--;
                        if (smsCooldown <= 0) {
                            clearInterval(timer);
                            sendSmsBtn.disabled = false;
                            sendSmsBtn.textContent = '发送验证码';
                        } else {
                            sendSmsBtn.textContent = `${smsCooldown}s`;
                        }
                    }, 1000);
                }
            } catch (e) {
                sendSmsBtn.disabled = false;
                sendSmsBtn.textContent = '发送验证码';
                err.textContent = e.message || '发送验证码失败';
                err.style.display = 'block';
            }
        });

        // 手机号登录提交
        document.getElementById('submitPhoneLogin').addEventListener('click', async () => {
            const phone = document.getElementById('phoneLoginPhone').value.trim();
            const code = document.getElementById('phoneLoginCode').value.trim();
            const err = document.getElementById('phoneLoginError');
            err.style.display = 'none';

            if (!phone || !code) { err.textContent = '请填写手机号和验证码'; err.style.display = 'block'; return; }
            if (!/^1[3-9]\d{9}$/.test(phone)) { err.textContent = '请输入正确的手机号'; err.style.display = 'block'; return; }
            if (code.length < 4) { err.textContent = '验证码至少4位'; err.style.display = 'block'; return; }

            try {
                const d = await api.phoneLogin(phone, code);
                const user = d.user || d;
                if (user) {
                    overlay.remove();
                    this._checkLoginStatus();
                    this._loadAchievements();
                    showToast(d.message || (d.is_new_user ? '注册成功' : '登录成功'), 'success', 2000);
                } else {
                    err.textContent = '登录失败，请重试';
                    err.style.display = 'block';
                }
            } catch (e) { err.textContent = e.message || '网络错误，请稍后重试'; err.style.display = 'block'; }
        });

        document.getElementById('submitLogin').addEventListener('click', async () => {
            const u = document.getElementById('loginUsername').value.trim();
            const p = document.getElementById('loginPassword').value;
            const err = document.getElementById('loginError');
            err.style.display = 'none';

            if (!u || !p) { err.textContent = '请填写用户名和密码'; err.style.display = 'block'; return; }
            if (u.length < 3) { err.textContent = '用户名至少需要3个字符'; err.style.display = 'block'; return; }

            try {
                const d = await api.login(u, p);
                const user = d.user || d;
                if (user) { overlay.remove(); this._checkLoginStatus(); this._loadAchievements(); }
                else { err.textContent = '登录失败，请检查用户名和密码'; err.style.display = 'block'; }
            } catch (e) { err.textContent = e.message || '网络错误，请稍后重试'; err.style.display = 'block'; }
        });

        document.getElementById('submitRegister').addEventListener('click', async () => {
            const un = document.getElementById('regUsername').value.trim();
            const pw = document.getElementById('regPassword').value;
            const nn = document.getElementById('regNickname').value.trim();
            const err = document.getElementById('regError');
            err.style.display = 'none';

            if (!un || !pw || !nn) { err.textContent = '请填写所有字段'; err.style.display = 'block'; return; }
            if (un.length < 3) { err.textContent = '用户名至少需要3个字符'; err.style.display = 'block'; return; }
            if (pw.length < 6) { err.textContent = '密码至少需要6个字符'; err.style.display = 'block'; return; }
            if (nn.length < 1) { err.textContent = '昵称不能为空'; err.style.display = 'block'; return; }

            try {
                const d = await api.register(un, pw, nn);
                const user = d.user || d;
                if (user) { overlay.remove(); this._checkLoginStatus(); this._loadAchievements(); }
                else { err.textContent = '注册失败，请稍后重试'; err.style.display = 'block'; }
            } catch (e) { err.textContent = e.message || '网络错误，请稍后重试'; err.style.display = 'block'; }
        });
    }

    /* ---- 内联结果渲染 ---- */

    _renderInlineResult(result) {
        if (!this.resultSection) return;

        const badge = document.getElementById('homeCategoryBadge');
        const itemName = document.getElementById('homeItemName');
        const confFill = document.getElementById('homeConfidenceFill');
        const confText = document.getElementById('homeConfidenceText');
        const guidance = document.getElementById('homeGuidanceText');
        const inference = document.getElementById('homeInferenceInfo');

        if (badge) {
            badge.textContent = result.category || '';
            if (result.bin_color) badge.style.backgroundColor = result.bin_color;
        }
        if (itemName) itemName.textContent = result.label_cn || '';

        if (confFill) {
            const pct = Math.round((result.confidence || 0) * 100);
            confFill.style.width = pct + '%';
            confFill.className = 'confidence-fill' + (pct >= 80 ? ' high' : pct >= 50 ? ' medium' : ' low');
        }
        if (confText) confText.textContent = Math.round((result.confidence || 0) * 100) + '%';

        if (guidance) guidance.textContent = result.guidance || '';
        if (inference) inference.textContent = result.inference_time_ms ? `推理耗时: ${result.inference_time_ms}ms` : '';

        this.resultSection.classList.remove('hidden');
    }

    _renderInlineSearchResult(results) {
        if (!this.searchResultSection) return;
        const container = document.getElementById('homeSearchResults');
        if (!container) return;

        if (!results || results.length === 0) {
            container.innerHTML = '<p style="color:#95A0AA;text-align:center;padding:12px;">未找到相关结果</p>';
        } else {
            container.innerHTML = results.map(r => `
                <div class="search-result-item">
                    <span class="category-badge" style="background:${r.bin_color || '#4CAF50'}">${escapeHtml(r.category || '')}</span>
                    <span class="item-name">${escapeHtml(r.label || '')}</span>
                    <span class="similarity">${r.similarity_score || 0}%</span>
                </div>
            `).join('');
        }

        this.searchResultSection.classList.remove('hidden');
    }
}

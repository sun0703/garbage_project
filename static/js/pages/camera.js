/**
 * 预览确认页视图（Camera/Preview Page）
 *
 * 职责：展示已选图片预览，提供「开始识别」和「重新选择」操作；
 *       识别流程：压缩 → 上传 → 识别结果处理（含状态机反馈、网络异常检测、自动降级）。
 * 容器：#page-preview
 */

// ==================== 模块依赖导入 ====================
import { store } from '../store.js';
import { api, ApiError } from '../api.js';
import { ImageProcessor } from '../utils/image.js';
import { showToast, showLoading, hideLoading, setLoadingText, showModal } from '../utils/ui.js';

// ==================== 状态机枚举 ====================

/** 识别流程各阶段状态 (F-1.2.4 上传状态反馈) */
const RecognizeState = {
    IDLE: 'idle',           // 空闲
    COMPRESSING: 'compressing', // 压缩中
    UPLOADING: 'uploading',     // 上传中
    RECOGNIZING: 'recognizing', // 识别中
    ERROR: 'error'              // 出错
};

// ==================== 需要降级处理的错误码 (F-1.4.2) ====================
const FALLBACK_ERROR_CODES = new Set(['E2002', 'E002']);

// ==================== 页面类定义 ====================
export class PreviewPage {
    /** 页面根容器 DOM 引用 */
    container = null;

    /** 预览图片元素 */
    previewImg = null;

    /** 开始识别按钮 */
    startBtn = null;

    /** 重新选择按钮 */
    reselectBtn = null;

    /** 当前图片的 Object URL（用于 destroy 时释放） */
    _objectUrl = null;

    /** 当前识别状态 */
    _state = RecognizeState.IDLE;

    /** 绑定的事件处理器引用集合 */
    _boundHandlers = {};

    /** 是否正在识别中（防止重复提交） */
    _recognizing = false;

    /**
     * 初始化预览确认页
     * 从 store 读取 selectedImage 并渲染预览界面
     */
    init() {
        this.container = document.getElementById('page-preview');
        if (!this.container) {
            console.error('[PreviewPage] 容器 #page-preview 不存在');
            return;
        }

        /* 从 store 获取已选图片数据 */
        const selectedImage = store.get('selectedImage');

        /* 【增强校验】图片数据必须存在且为 Blob/File 类型 */
        if (!selectedImage || !(selectedImage instanceof Blob)) {
            /* 清理无效状态，防止后续页面读取到脏数据 */
            store.remove('selectedImage');
            store.remove('selectedFile');
            showToast('未选择图片，请先上传', 'warning');
            window.location.hash = '#/';
            return;
        }

        /* 渲染页面结构 */
        this._render();
        /* 缓存 DOM 引用 */
        this._cacheDOM();
        /* 显示预览图 */
        this._showPreview(selectedImage);
        /* 绑定事件 */
        this._bindEvents();

        console.log('[PreviewPage] 预览页初始化完成');
    }

    /**
     * 销毁预览确认页
     * 释放 Object URL、移除事件监听、清空容器
     */
    destroy() {
        /* 释放预览图的 Object URL，防止内存泄漏 */
        if (this._objectUrl) {
            URL.revokeObjectURL(this._objectUrl);
            this._objectUrl = null;
        }

        /* 移除按钮事件 */
        if (this.startBtn) {
            this.startBtn.removeEventListener('click', this._boundHandlers.start);
        }
        if (this.reselectBtn) {
            this.reselectBtn.removeEventListener('click', this._boundHandlers.reselect);
        }

        /* 清空容器 */
        if (this.container) {
            this.container.innerHTML = '';
        }

        /* 重置状态 */
        this._state = RecognizeState.IDLE;
        this._recognizing = false;

        /* 释放引用 */
        this.container = null;
        this.previewImg = null;
        this.startBtn = null;
        this.reselectBtn = null;
        this._boundHandlers = {};

        console.log('[PreviewPage] 预览页已销毁');
    }

    // ==================== 私有方法：渲染 ====================

    /**
     * 渲染预览确认页 HTML 结构
     * 包含大尺寸预览图区域 + 操作按钮组
     * @private
     */
    _render() {
        this.container.innerHTML = `
            <!-- 页面导航栏 -->
            <div class="preview-nav">
                <button class="nav-back-btn" id="previewBackBtn">
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    返回
                </button>
                <h2 class="preview-title">确认图片</h2>
            </div>

            <!-- 预览卡片 -->
            <div class="card preview-card">
                <!-- 图片预览区 (F-1.2.3 图片预览与重新选择) -->
                <div class="preview-image-wrap" id="previewImageWrap">
                    <img id="previewImg" alt="待识别图片" class="preview-image-large">
                </div>

                <!-- 图片信息 -->
                <div class="preview-info" id="previewInfo">
                    <span class="preview-filename" id="previewFilename"></span>
                </div>

                <!-- 操作按钮组 -->
                <div class="btn-group preview-actions">
                    <button class="btn btn-primary" id="startRecognizeBtn">
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="white" stroke-width="2" fill="none">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="M21 21l-4.35-4.35"/>
                        </svg>
                        开始识别
                    </button>
                    <button class="btn btn-secondary" id="reselectBtn">
                        <svg viewBox="0 0 24 24" width="17" height="17" stroke="currentColor" stroke-width="2" fill="none">
                            <polyline points="1 4 1 10 7 10"/>
                            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                        </svg>
                        重新选择
                    </button>
                </div>
            </div>

            <!-- 提示信息 -->
            <div class="preview-tip">
                <p>确认图片清晰后点击「开始识别」，AI 将自动分析垃圾分类</p>
            </div>
        `;
    }

    // ==================== 私有方法：DOM 缓存 ====================

    /**
     * 缓存高频 DOM 元素引用
     * @private
     */
    _cacheDOM() {
        this.previewImg = document.getElementById('previewImg');
        this.startBtn = document.getElementById('startRecognizeBtn');
        this.reselectBtn = document.getElementById('reselectBtn');
    }

    // ==================== 私有方法：预览展示 ====================

    /**
     * 在预览区域显示选中的图片 (F-1.2.3)
     * 支持两种数据格式：base64 字符串或 Blob URL
     *
     * @param {string} imageData - base64 编码图片数据或 Blob URL
     * @private
     */
    _showPreview(imageData) {
        if (!this.previewImg) return;

        /* 判断是否为 base64 格式（data: 开头） */
        if (imageData.startsWith('data:')) {
            // base64 直接作为 src 使用
            this.previewImg.src = imageData;
        } else {
            // 非 base64 时创建 Object URL
            this._objectUrl = URL.createObjectURL(this._base64ToBlob(imageData));
            this.previewImg.src = this._objectUrl;
        }

        /* 显示文件名 */
        const filenameEl = document.getElementById('previewFilename');
        const fileName = store.get('selectedFileName') || '图片文件';
        if (filenameEl) {
            filenameEl.textContent = fileName;
        }
    }

    /**
     * 将 Base64 字符串转换为 Blob 对象
     * 用于创建可释放的 Object URL
     *
     * @param {string} base64 - Base64 编码的图片字符串（含 data URI 前缀）
     * @returns {Blob} 图片 Blob 对象
     * @private
     */
    _base64ToBlob(base64) {
        const arr = base64.split(',');
        const mimeMatch = arr[0].match(/:(.*?);/);
        const mime = mimeMatch ? mimeMatch[1] : 'image/jpeg';
        const bstr = atob(arr[1]);
        let n = bstr.length;
        const u8arr = new Uint8Array(n);
        while (n--) {
            u8arr[n] = bstr.charCodeAt(n);
        }
        return new Blob([u8arr], { type: mime });
    }

    // ==================== 私有方法：事件绑定 ====================

    /**
     * 绑定全部交互事件
     * @private
     */
    _bindEvents() {
        /* 开始识别按钮 — 触发完整识别流水线 */
        this._boundHandlers.start = () => this._handleRecognize();
        if (this.startBtn) {
            this.startBtn.addEventListener('click', this._boundHandlers.start);
        }

        /* 重新选择按钮 — 返回首页重新上传 (F-1.2.3) */
        this._boundHandlers.reselect = () => {
            store.remove('selectedImage');
            store.remove('selectedFileName');
            window.location.hash = '#/';
        };
        if (this.reselectBtn) {
            this.reselectBtn.addEventListener('click', this._boundHandlers.reselect);
        }

        /* 返回导航按钮 */
        const backBtn = document.getElementById('previewBackBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.hash = '#/';
            });
        }
    }

    // ==================== 私有方法：识别核心流水线 ====================

    /**
     * 执行完整的 AI 识别流程
     *
     * 状态机流转 (F-1.2.4)：
     *   IDLE → COMPRESSING → UPLOADING → RECOGNIZING → IDLE(成功)/ERROR(失败)
     *
     * 包含功能点：
     *   - F-1.2.4 上传状态反馈（状态机驱动 UI 更新）
     *   - F-1.4.1 网络异常检测（ApiError 友好提示）
     *   - F-1.4.2 自动降级（E2002/E002 错误码调用 analyzeFallback）
     *
     * @private
     */
    async _handleRecognize() {
        /* 防止重复提交 */
        if (this._recognizing) return;
        this._recognizing = true;

        /* 禁用按钮防止重复点击 */
        if (this.startBtn) this.startBtn.disabled = true;

        try {
            const selectedImage = store.get('selectedImage');

            /* 【防御性校验】参数有效性检查 - 防止无效数据导致 FileReader 异常 */
            if (!selectedImage || !(selectedImage instanceof Blob)) {
                console.warn('[PreviewPage] selectedImage 无效或非 Blob 类型，取消识别');
                showToast('图片数据无效，请重新上传', 'error');
                this._updateState(RecognizeState.ERROR);
                this._recognizing = false;
                if (this.startBtn) this.startBtn.disabled = false;
                return;
            }

            /* ---- 阶段1：压缩图片 ---- */
            this._updateState(RecognizeState.COMPRESSING);
            setLoadingText('压缩中...');
            showLoading('压缩中...');

            const base64Data = await ImageProcessor.toBase64(selectedImage);

            /* ---- 阶段2：上传并识别 ---- */
            this._updateState(RecognizeState.UPLOADING);
            setLoadingText('上传识别中...');

            let result;

            try {
                /* 发送预测请求到后端 API */
                this._updateState(RecognizeState.RECOGNIZING);
                setLoadingText('AI 识别中...');
                result = await api.predict(base64Data);

            } catch (error) {
                /* F-1.4.1 网络异常检测与友好提示 */
                if (error instanceof ApiError) {
                    console.warn(`[PreviewPage] API错误 [${error.code}]: ${error.message}`);

                    /* F-1.4.2 自动降级：特定错误码触发备用分析接口 */
                    if (FALLBACK_ERROR_CODES.has(error.code)) {
                        console.log('[PreviewPage] 触发自动降级模式');
                        setLoadingText('使用备用模式识别...');
                        try {
                            result = await api.analyzeFallback(base64Data);
                        } catch (fallbackError) {
                            throw fallbackError;
                        }
                    } else {
                        /* 其他 API 错误直接抛出 */
                        throw error;
                    }
                } else {
                    /* 网络/未知异常 */
                    throw error;
                }
            }

            /* ---- 阶段3：处理成功结果 ---- */
            this._updateState(RecognizeState.IDLE);
            hideLoading();

            /* 存储识别结果到全局 store */
            store.set('predictResult', result);

            showToast('识别完成', 'success');

            /* 延迟跳转到结果展示页 */
            setTimeout(() => {
                window.location.hash = '#/result';
            }, 300);

        } catch (error) {
            /* ---- 处理失败情况 ---- */
            this._updateState(RecognizeState.ERROR);
            hideLoading();

            console.error('[PreviewPage] 识别失败:', error);

            /* 根据错误类型给出不同提示 (F-1.4.1) */
            let errorMsg = '识别失败，请重试';
            if (error instanceof ApiError) {
                errorMsg = error.userMessage || error.message;
            } else if (error.name === 'TypeError' && !navigator.onLine) {
                errorMsg = '网络连接不可用，请检查网络设置';
            }

            showModal({ title: '识别失败', content: errorMsg, confirmText: '确定' });
            showToast(errorMsg, 'error');

        } finally {
            /* 恢复按钮状态 */
            if (this.startBtn) this.startBtn.disabled = false;
            this._recognizing = false;
        }
    }

    /**
     * 更新当前识别状态（状态机驱动）
     * 可扩展用于日志记录或状态面板展示
     *
     * @param {string} newState - 新状态值（RecognizeState 枚举）
     * @private
     */
    _updateState(newState) {
        const oldState = this._state;
        this._state = newState;
        console.log(`[PreviewPage] 状态流转: ${oldState} → ${newState}`);
    }
}

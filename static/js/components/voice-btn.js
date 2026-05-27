/**
 * @fileoverview 语音识别按钮组件 - VoiceButton
 *
 * ⚠️ **迁移状态**: 待迁移至 BaseComponent 基类
 *
 * @description 基于 Web Speech API (SpeechRecognition) 的语音输入组件
 *              支持 Chrome / Edge / Safari 浏览器，自动降级提示
 *
 * @module components/voice-btn
 * @example
 * import { VoiceButton } from './voice-btn.js';
 * const voiceBtn = new VoiceButton({
 *     btnEl: document.getElementById('voiceBtn'),
 *     onResult: (text) => console.log('识别结果:', text),
 * });
 */

export class VoiceButton {
    /**
     * 构造函数 - 初始化语音识别按钮
     * @param {Object} options - 配置选项
     * @param {HTMLElement} options.btnEl - 按钮 DOM 元素
     * @param {Function} [options.onResult] - 识别结果回调 (text: string) => void
     * @param {Function} [options.onError] - 错误回调 (error: string) => void
     * @param {Function} [options.onStateChange] - 状态变化回调 (isRecording: boolean) => void
     */
    constructor(options = {}) {
        /** @type {HTMLElement} 按钮元素 */
        this.btnEl = options.btnEl;

        /** @type {Function|null} 识别结果回调 */
        this.onResult = options.onResult || null;

        /** @type {Function|null} 错误回调 */
        this.onError = options.onError || null;

        /** @type {Function|null} 状态变化回调 */
        this.onStateChange = options.onStateChange || null;

        /** @type {boolean} 当前是否正在录音 */
        this.isRecording = false;

        /** @type {boolean} 浏览器是否支持 Web Speech API */
        this.supported = false;

        /** @type {SpeechRecognition|null} 语音识别实例 */
        this.recognition = null;

        // 初始化检测和绑定
        this._init();
    }

    /**
     * 初始化语音识别功能
     * 检测浏览器支持并配置识别参数
     * @private
     */
    _init() {
        if (!this.btnEl) {
            console.warn('[VoiceButton] 未提供按钮元素');
            return;
        }

        // 检测浏览器支持情况
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn('[VoiceButton] 当前浏览器不支持 Web Speech API');
            this.supported = false;
            this._setupUnsupported();
            return;
        }

        this.supported = true;

        // 创建语音识别实例
        this.recognition = new SpeechRecognition();

        // 配置识别参数
        this.recognition.continuous = false;       // 单次识别模式（非持续监听）
        this.recognition.interimResults = true;    // 返回临时结果（实时显示）
        this.recognition.lang = 'zh-CN';           // 中文普通话
        this.recognition.maxAlternatives = 1;      // 返回最佳结果

        // 绑定事件处理器
        this.recognition.onstart = () => this._onStart();
        this.recognition.onend = () => this._onEnd();
        this.recognition.onresult = (event) => this._onResult(event);
        this.recognition.onerror = (event) => this._onError(event);

        // 绑定按钮交互事件
        this._bindEvents();

        console.log('[VoiceButton] 语音识别初始化成功');
    }

    /**
     * 设置不支持状态（降级处理）
     * 显示禁用样式并添加提示，同时提供 MediaRecorder 录音上传备选方案
     * @private
     */
    _setupUnsupported() {
        this.btnEl.classList.add('voice-unsupported');
        this.btnEl.title = '您的浏览器不支持语音识别，可使用录音上传功能';
        this.btnEl.setAttribute('aria-disabled', 'true');

        // 创建备选方案的容器和按钮
        const fallbackContainer = document.createElement('div');
        fallbackContainer.className = 'voice-fallback-container';
        fallbackContainer.innerHTML = `
            <div class="voice-fallback-tip">语音识别不可用</div>
            <button class="voice-record-btn" type="button" aria-label="录音上传">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                <span>录音上传</span>
            </button>
            <div class="voice-record-status"></div>
        `;

        // 插入到按钮后面
        this.btnEl.parentNode?.insertBefore(fallbackContainer, this.btnEl.nextSibling);

        // 获取录音按钮并绑定事件
        const recordBtn = fallbackContainer.querySelector('.voice-record-btn');
        const statusEl = fallbackContainer.querySelector('.voice-record-status');

        // 绑定原始按钮点击事件（显示提示），保存引用以便清理
        this._unsupportedClickHandler = () => {
            this._showToast('您的浏览器不支持实时语音识别\n可点击"录音上传"按钮录制音频后发送');
        };
        this.btnEl.addEventListener('click', this._unsupportedClickHandler);

        // 绑定 MediaRecorder 录音按钮事件
        recordBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this._toggleMediaRecording(recordBtn, statusEl);
        });

        console.log('[VoiceButton] 已启用 MediaRecorder 备选录音模式');
    }

    /**
     * 切换 MediaRecorder 录音状态
     * 使用浏览器原生 MediaRecorder API 录制音频，支持 webm/ogg 格式
     * @param {HTMLElement} recordBtn - 录音按钮元素
     * @param {HTMLElement} statusEl - 状态显示元素
     * @private
     */
    async _toggleMediaRecording(recordBtn, statusEl) {
        // 如果正在录音，则停止并上传
        if (this._mediaRecorder && this._isMediaRecording) {
            this._stopMediaRecording(recordBtn, statusEl);
            return;
        }

        // 检查 MediaRecorder 是否可用
        if (!window.MediaRecorder) {
            this._showToast('您的浏览器不支持 MediaRecorder API');
            return;
        }

        try {
            // 请求麦克风权限并获取音频流
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,      // 回声消除
                    noiseSuppression: true,       // 噪声抑制
                    autoGainControl: true,         // 自动增益
                }
            });

            // 确定支持的 MIME 类型（优先使用 webm，兼容性最好）
            const mimeType = this._getSupportedMimeType();
            
            // 创建 MediaRecorder 实例
            this._mediaRecorder = new MediaRecorder(stream, {
                mimeType,
                audioBitsPerSecond: 16000,  // 16kHz 采样率（适合语音）
            });

            // 收集录制的音频数据块
            this._audioChunks = [];

            this._mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this._audioChunks.push(event.data);
                }
            };

            // 录制停止时的回调：组装音频文件并上传
            this._mediaRecorder.onstop = async () => {
                // 停止所有音频轨道
                stream.getTracks().forEach(track => track.stop());

                if (this._audioChunks.length === 0) {
                    statusEl.textContent = '录制失败：未获取到音频数据';
                    return;
                }

                try {
                    // 组装 Blob 对象
                    const audioBlob = new Blob(this._audioChunks, { type: mimeType });
                    
                    // 更新 UI 状态
                    recordBtn.classList.remove('recording');
                    recordBtn.disabled = false;
                    statusEl.textContent = '正在上传...';

                    // 上传音频到后端
                    await this._uploadAudioRecording(audioBlob, mimeType);
                    
                    statusEl.textContent = '上传成功 ✓';
                    setTimeout(() => { statusEl.textContent = ''; }, 3000);
                } catch (uploadErr) {
                    console.error('[VoiceButton] 音频上传失败:', uploadErr);
                    statusEl.textContent = '上传失败，请重试';
                    this.onError?.('upload_failed', '音频上传失败');
                }

                this._isMediaRecording = false;
                this._mediaRecorder = null;
                this._audioChunks = [];
            };

            // 录制错误处理
            this._mediaRecorder.onerror = (event) => {
                console.error('[VoiceButton] MediaRecorder 错误:', event.error);
                stream.getTracks().forEach(track => track.stop());
                recordBtn.classList.remove('recording');
                recordBtn.disabled = false;
                statusEl.textContent = '录制出错';
                this._isMediaRecording = false;
                this._showToast('录制过程出现错误，请重试');
            };

            // 开始录制
            this._mediaRecorder.start(100);  // 每100ms收集一次数据
            this._isMediaRecording = true;

            // 更新 UI 为录音中状态
            recordBtn.classList.add('recording');
            recordBtn.disabled = false;
            statusEl.textContent = '正在录音... 点击停止';

            this.onStateChange?.(true);
            console.log('[VoiceButton] MediaRecorder 开始录制');

        } catch (err) {
            console.error('[VoiceButton] 麦克风权限错误:', err);
            
            // 根据错误类型给出友好提示
            if (err.name === 'NotAllowedError') {
                this._showToast('麦克风权限被拒绝\n请在浏览器设置中允许访问麦克风');
            } else if (err.name === 'NotFoundError') {
                this._showToast('未检测到麦克风设备\n请连接麦克风后重试');
            } else {
                this._showToast(`无法启动录音: ${err.message}`);
            }
            
            this.onError?.('permission_denied', err.message);
        }
    }

    /**
     * 停止 MediaRecorder 录制
     * @param {HTMLElement} recordBtn - 录音按钮元素
     * @param {HTMLElement} statusEl - 状态显示元素
     * @private
     */
    _stopMediaRecording(recordBtn, statusEl) {
        if (this._mediaRecorder && this._isMediaRecording) {
            try {
                statusEl.textContent = '正在保存...';
                this._mediaRecorder.stop();
            } catch (e) {
                console.warn('[VoiceButton] 停止录制异常:', e);
            }
        }
    }

    /**
     * 获取当前浏览器支持的音频 MIME 类型
     * 优先选择 webm 格式（兼容性最佳），回退到 ogg
     * @returns {string} 支持的 MIME 类型字符串
     * @private
     */
    _getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/ogg',
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        // 默认返回（浏览器应至少支持一种）
        return 'audio/webm';
    }

    /**
     * 上传录制的音频到后端服务器
     * 将音频 Blob 通过 POST 请求发送到语音识别接口
     * @param {Blob} audioBlob - 音频数据 Blob 对象
     * @param {string} mimeType - 音频 MIME 类型
     * @returns {Promise<Object>} 后端响应数据
     * @private
     */
    async _uploadAudioRecording(audioBlob, mimeType) {
        // 构建 FormData 对象用于文件上传
        const formData = new FormData();
        
        // 根据 MIME 类型确定文件扩展名
        const ext = mimeType.includes('webm') ? 'webm' : 'ogg';
        const filename = `voice_recording_${Date.now()}.${ext}`;
        
        formData.append('audio', audioBlob, filename);
        formData.append('format', mimeType);

        // 发送 POST 请求到后端语音识别接口
        // 注意：后端接口 /api/voice/correct 可能需要扩展以支持音频文件上传
        // 当前实现先尝试调用该接口，如果失败则提示用户
        const response = await fetch('/api/voice/correct', {
            method: 'POST',
            body: formData,
            // 不设置 Content-Type，让浏览器自动设置 multipart/form-data 边界
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // 处理识别结果
        if (data.success && (data.corrected || data.text)) {
            const recognizedText = data.corrected || data.text;
            console.log('[VoiceButton] 录音识别结果:', recognizedText);
            
            // 调用结果回调
            this.onResult?.(recognizedText, data.changed || false, data.original || recognizedText);
            
            return data;
        } else {
            throw new Error(data.error?.message || '语音识别服务返回异常');
        }
    }

    /**
     * 绑定按钮交互事件
     * 支持点击和长按（移动端友好）
     * @private
     */
    _bindEvents() {
        this._boundClick = () => this.toggle();
        this.btnEl.addEventListener('click', this._boundClick);

        // 长按支持（移动端友好）
        let pressTimer;
        this.btnEl.addEventListener('touchstart', (e) => {
            e.preventDefault();
            pressTimer = setTimeout(() => this.toggle(), 300);
        }, { passive: false });

        this.btnEl.addEventListener('touchend', () => {
            clearTimeout(pressTimer);
        });

        this.btnEl.addEventListener('touchcancel', () => {
            clearTimeout(pressTimer);
        });
    }

    /**
     * 切换录音状态（开始/停止）
     * @public
     */
    toggle() {
        if (!this.supported || !this.recognition) {
            this._showToast('语音识别不可用');
            return;
        }

        if (this.isRecording) {
            this.stop();
        } else {
            this.start();
        }
    }

    /**
     * 开始录音识别
     * @public
     */
    start() {
        if (!this.supported || !this.recognition) return;

        try {
            // 每次重新启动时需要创建新实例（避免状态问题）
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'zh-CN';
            this.recognition.maxAlternatives = 1;

            this.recognition.onstart = () => this._onStart();
            this.recognition.onend = () => this._onEnd();
            this.recognition.onresult = (event) => this._onResult(event);
            this.recognition.onerror = (event) => this._onError(event);

            this.recognition.start();
        } catch (err) {
            console.error('[VoiceButton] 启动失败:', err);
            this._showToast('无法启动语音识别，请检查麦克风权限');
        }
    }

    /**
     * 停止录音识别
     * @public
     */
    stop() {
        if (this.recognition && this.isRecording) {
            try {
                this.recognition.stop();
            } catch (e) {
                console.warn('[VoiceButton] 停止异常:', e);
            }
        }
    }

    /**
     * 录音开始回调
     * 更新 UI 状态为录音中
     * @private
     */
    _onStart() {
        this.isRecording = true;
        this.btnEl.classList.add('recording');
        this.btnEl.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                <rect x="11" y="18" width="2" height="4" fill="currentColor" class="voice-pulse"/>
            </svg>
        `;
        this.btnEl.setAttribute('aria-label', '停止录音');

        this.onStateChange?.(true);
        console.log('[VoiceButton] 录音开始');
    }

    /**
     * 录音结束回调
     * 恢复 UI 状态
     * @private
     */
    _onEnd() {
        this.isRecording = false;
        this.btnEl.classList.remove('recording');
        this.btnEl.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
        `;
        this.btnEl.setAttribute('aria-label', '语音输入');

        this.onStateChange?.(false);
    }

    /**
     * 识别结果回调
     * 提取最终识别文本并调用回调
     * @param {SpeechRecognitionEvent} event - 识别事件对象
     * @private
     */
    _onResult(event) {
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            }
        }

        finalTranscript = finalTranscript.trim();

        if (finalTranscript) {
            console.log('[VoiceButton] 识别结果:', finalTranscript);

            // 调用 ASR 纠错 API 进行后处理
            this._correctAndCallback(finalTranscript);
        }
    }

    /**
     * 调用后端纠错 API 并返回结果
     * @param {string} text - 原始识别文本
     * @private
     */
    async _correctAndCallback(text) {
        try {
            const response = await fetch('/api/voice/correct', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });

            const data = await response.json();

            if (data.success && data.corrected) {
                this.onResult?.(data.corrected, data.changed, data.original);

                // 如果有纠错变更，显示提示
                if (data.changed && data.search_results) {
                    console.log('[VoiceButton] 纠错成功:', data.original, '→', data.corrected);
                }
            } else {
                this.onResult?.(text, false, text);
            }
        } catch (err) {
            // 纠错 API 调用失败时直接使用原始文本
            console.warn('[VoiceButton] 纠错API调用失败，使用原始文本:', err);
            this.onResult?.(text, false, text);
        }
    }

    /**
     * 识别错误回调
     * 根据错误类型给出用户友好的提示
     * @param {Event} event - 错误事件对象
     * @private
     */
    _onError(event) {
        this.isRecording = false;
        this.btnEl.classList.remove('recording');

        const errorTips = {
            'no-speech': '未检测到语音，请重试',
            'audio-capture': '找不到麦克风，请检查设备权限',
            'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许',
            'network': '网络错误，语音服务不可用',
            'aborted': '已取消识别',
            'service-not-allowed': '语音服务被禁止',
        };

        const message = errorTips[event.error] || `语音识别出错: ${event.error}`;
        console.warn('[VoiceButton] 识别错误:', event.error, message);

        this.onError?.(event.error, message);

        // 仅对非中止类错误显示提示
        if (event.error !== 'aborted') {
            this._showToast(message);
        }
    }

    /**
     * 显示轻量提示消息
     * @param {string} message - 提示内容
     * @private
     */
    _showToast(message) {
        // 尝试复用全局 toast（如果存在）
        if (window.showToast) {
            window.showToast(message, 'warning', 3000);
            return;
        }

        // 创建简单的内联提示
        const existing = document.querySelector('.voice-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'voice-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 9999;
            max-width: 80%;
            text-align: center;
            animation: fadeInUp 0.3s ease;
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'fadeOutDown 0.3s ease';
            setTimeout(() => toast.remove(), 280);
        }, 2500);
    }

    /**
     * 销毁组件 - 移除事件绑定和引用
     * 清理 MediaRecorder 资源和动态创建的 DOM 元素
     * @public
     */
    destroy() {
        // 停止语音识别
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {}
            this.recognition = null;
        }

        // 停止并清理 MediaRecorder（备选方案）
        if (this._mediaRecorder && this._isMediaRecording) {
            try {
                this._mediaRecorder.stop();
            } catch (e) {}
            this._mediaRecorder = null;
        }
        this._audioChunks = [];
        this._isMediaRecording = false;

        // 移除动态创建的备选容器
        const fallbackContainer = this.btnEl?.parentNode?.querySelector('.voice-fallback-container');
        if (fallbackContainer) {
            fallbackContainer.remove();
        }

        this.btnEl?.removeEventListener('click', this._boundClick);
        // 清理不支持路径下的点击监听器
        if (this._unsupportedClickHandler) {
            this.btnEl?.removeEventListener('click', this._unsupportedClickHandler);
            this._unsupportedClickHandler = null;
        }
        this._boundClick = null;
        this.onResult = null;
        this.onError = null;
        this.onStateChange = null;
        this.btnEl = null;
    }
}

/* ========== 组件内联样式 ========== */
const VOICE_BTN_STYLES = `
/* ======== VoiceButton 语音按钮样式 ======== */

.voice-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: none;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea, #764ba2);
    cursor: pointer;
    transition: all 0.25s ease;
    flex-shrink: 0;
}

.voice-btn:hover:not(:disabled):not(.voice-unsupported) {
    transform: scale(1.08);
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
}

.voice-btn:active:not(.disabled) {
    transform: scale(0.95);
}

/* 录音中的脉冲动画 */
.voice-btn.recording {
    background: linear-gradient(135deg, #f093fb, #f5576c);
    animation: voicePulse 1.2s ease-in-out infinite;
}

@keyframes voicePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(245, 87, 108, 0.5); }
    50% { box-shadow: 0 0 0 12px rgba(245, 87, 108, 0); }
}

.voice-btn.recording .voice-pulse {
    animation: voiceBar 0.8s ease-in-out infinite;
}

@keyframes voiceBar {
    0%, 100% { transform: scaleY(1); opacity: 1; }
    50% { transform: scaleY(0.5); opacity: 0.5; }
}

/* 不支持状态的禁用样式 */
.voice-btn.voice-unsupported {
    background: #ccc;
    cursor: not-allowed;
    opacity: 0.6;
}

.voice-btn.voice-unsupported:hover {
    transform: none;
    box-shadow: none;
}

/* ========== MediaRecorder 备选录音方案样式 ========== */

/* 备选方案容器 */
.voice-fallback-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    padding: 12px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    border: 1px dashed rgba(255, 255, 255, 0.15);
}

/* 提示文字 */
.voice-fallback-tip {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.5);
    text-align: center;
}

/* 录音上传按钮 */
.voice-record-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: none;
    border-radius: 20px;
    background: linear-gradient(135deg, #11998e, #38ef7d);
    color: white;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.25s ease;
    box-shadow: 0 2px 8px rgba(56, 239, 125, 0.3);
}

.voice-record-btn:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 16px rgba(56, 239, 125, 0.45);
}

.voice-record-btn:active:not(:disabled) {
    transform: scale(0.97);
}

/* 录音中状态 - 使用红色渐变 + 脉冲动画 */
.voice-record-btn.recording {
    background: linear-gradient(135deg, #f093fb, #f5576c);
    animation: voicePulse 1.2s ease-in-out infinite;
    box-shadow: 0 4px 16px rgba(245, 87, 108, 0.4);
}

.voice-record-btn:disabled {
    cursor: not-allowed;
    opacity: 0.7;
}

/* 录音状态文字 */
.voice-record-status {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.65);
    min-height: 16px;
    text-align: center;
}

/* Toast 动画 */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateX(-50%) translateY(10px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

@keyframes fadeOutDown {
    from { opacity: 1; transform: translateX(-50%) translateY(0); }
    to { opacity: 0; transform: translateX(-50%) translateY(10px); }
}
`;

// 自动注入样式
if (!document.getElementById('voice-btn-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'voice-btn-styles';
    styleSheet.textContent = VOICE_BTN_STYLES;
    document.head.appendChild(styleSheet);
}

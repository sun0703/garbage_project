/**
 * VoiceButton - 语音识别按钮组件
 *
 * 功能说明：
 * - 基于 Web Speech API 实现浏览器端语音识别
 * - 点击按钮开始/停止录音，实时转写文字
 * - 录音中显示脉冲动画和实时转写文字
 * - 不兼容浏览器自动降级提示
 * - 支持 MediaRecorder 备选方案（上传音频到后端ASR）
 *
 * 技术实现：
 * - 首选：Web Speech API（SpeechRecognition / webkitSpeechRecognition）
 * - 降级：MediaRecorder + 后端 /api/voice/text 接口
 * - 配置：continuous=false, interimResults=true, lang='zh-CN'
 *
 * @class VoiceButton
 * @example
 * import { VoiceButton } from './voice-btn.js';
 * const voiceBtn = new VoiceButton({
 *     container: '#voiceContainer',
 *     onResult: (text) => { console.log('识别结果:', text); }
 * });
 * voiceBtn.init();
 */

export class VoiceButton {
    constructor(options = {}) {
        this._container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;
        this._onResult = options.onResult || null;
        this._onError = options.onError || null;
        this._onStateChange = options.onStateChange || null;
        this._lang = options.lang || 'zh-CN';
        this._continuous = options.continuous || false;
        this._interimResults = options.interimResults !== false;

        this._element = null;
        this._waveElement = null;
        this._statusElement = null;
        this._recognition = null;
        this._mediaRecorder = null;
        this._audioChunks = [];
        this._isListening = false;
        this._isSupported = false;
        this._supportMode = 'none';
        this._boundHandlers = {};
    }

    init() {
        if (!this._container) {
            console.error('[VoiceButton] 容器元素不存在');
            return;
        }

        this._detectSupport();
        this._render();
        this._cacheDOM();
        this._bindEvents();

        console.log(`[VoiceButton] 初始化完成, 支持模式: ${this._supportMode}`);
    }

    destroy() {
        this.stop();

        if (this._element && this._element.parentNode) {
            this._element.parentNode.removeChild(this._element);
        }

        this._element = null;
        this._waveElement = null;
        this._statusElement = null;
        this._recognition = null;
        this._mediaRecorder = null;
        this._audioChunks = [];
        this._boundHandlers = {};

        console.log('[VoiceButton] 已销毁');
    }

    start() {
        if (this._isListening) return;

        if (this._supportMode === 'speech-api') {
            this._startSpeechAPI();
        } else if (this._supportMode === 'media-recorder') {
            this._startMediaRecorder();
        } else {
            this._showUnsupportedTip();
        }
    }

    stop() {
        if (!this._isListening) return;

        if (this._supportMode === 'speech-api' && this._recognition) {
            this._recognition.stop();
        } else if (this._supportMode === 'media-recorder' && this._mediaRecorder) {
            this._mediaRecorder.stop();
        }

        this._setListening(false);
    }

    isListening() {
        return this._isListening;
    }

    isSupported() {
        return this._supportMode !== 'none';
    }

    getSupportMode() {
        return this._supportMode;
    }

    _detectSupport() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this._isSupported = true;
            this._supportMode = 'speech-api';
            return;
        }

        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder) {
            this._isSupported = true;
            this._supportMode = 'media-recorder';
            return;
        }

        this._isSupported = false;
        this._supportMode = 'none';
    }

    _render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'voice-btn-wrapper';

        wrapper.innerHTML = `
            <button type="button"
                    class="voice-btn"
                    aria-label="语音输入"
                    title="语音输入">
                <span class="voice-btn__icon">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                </span>
                <span class="voice-btn__wave">
                    <span class="voice-btn__wave-bar"></span>
                    <span class="voice-btn__wave-bar"></span>
                    <span class="voice-btn__wave-bar"></span>
                    <span class="voice-btn__wave-bar"></span>
                    <span class="voice-btn__wave-bar"></span>
                </span>
            </button>
            <div class="voice-btn__status" aria-live="polite"></div>
        `;

        this._container.appendChild(wrapper);
        this._element = wrapper;
    }

    _cacheDOM() {
        if (!this._element) return;
        this._waveElement = this._element.querySelector('.voice-btn__wave');
        this._statusElement = this._element.querySelector('.voice-btn__status');
    }

    _bindEvents() {
        const btn = this._element?.querySelector('.voice-btn');
        if (!btn) return;

        this._boundHandlers.click = () => {
            if (this._isListening) {
                this.stop();
            } else {
                this.start();
            }
        };

        btn.addEventListener('click', this._boundHandlers.click);
    }

    _startSpeechAPI() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this._recognition = new SpeechRecognition();
        this._recognition.lang = this._lang;
        this._recognition.continuous = this._continuous;
        this._recognition.interimResults = this._interimResults;
        this._recognition.maxAlternatives = 1;

        this._recognition.onstart = () => {
            this._setListening(true);
            this._setStatus('正在聆听...');
        };

        this._recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            if (interimTranscript) {
                this._setStatus(interimTranscript);
            }

            if (finalTranscript) {
                this._setStatus(finalTranscript);
                this._handleResult(finalTranscript);
            }
        };

        this._recognition.onerror = (event) => {
            this._handleError(event.error, event.message);
        };

        this._recognition.onend = () => {
            this._setListening(false);
            this._setStatus('');
        };

        try {
            this._recognition.start();
        } catch (err) {
            this._handleError('start-failed', err.message);
        }
    }

    async _startMediaRecorder() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this._mediaRecorder = new MediaRecorder(stream);
            this._audioChunks = [];

            this._mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this._audioChunks.push(event.data);
                }
            };

            this._mediaRecorder.onstart = () => {
                this._setListening(true);
                this._setStatus('正在录音...');
            };

            this._mediaRecorder.onstop = async () => {
                this._setListening(false);
                this._setStatus('正在识别...');

                stream.getTracks().forEach(track => track.stop());

                const audioBlob = new Blob(this._audioChunks, { type: 'audio/webm' });
                await this._sendAudioToBackend(audioBlob);

                this._setStatus('');
            };

            this._mediaRecorder.onerror = (event) => {
                this._handleError('media-recorder', event.error?.message || '录音失败');
                this._setListening(false);
            };

            this._mediaRecorder.start();

            setTimeout(() => {
                if (this._isListening && this._mediaRecorder?.state === 'recording') {
                    this._mediaRecorder.stop();
                }
            }, 10000);

        } catch (err) {
            if (err.name === 'NotAllowedError') {
                this._handleError('not-allowed', '麦克风权限被拒绝');
            } else if (err.name === 'NotFoundError') {
                this._handleError('audio-capture', '未找到麦克风设备');
            } else {
                this._handleError('media-recorder', err.message);
            }
        }
    }

    async _sendAudioToBackend(audioBlob) {
        try {
            const { api } = await import('../api.js');
            const result = await api.voiceToText(audioBlob);
            const text = result.text || '';

            if (text) {
                this._handleResult(text);
            } else {
                this._handleError('no-speech', '未能识别语音内容');
            }
        } catch (err) {
            this._handleError('network', '语音识别服务不可用');
        }
    }

    _handleResult(text) {
        const cleaned = this._cleanTranscript(text);
        if (!cleaned) return;

        if (typeof this._onResult === 'function') {
            this._onResult(cleaned);
        }

        this._element?.dispatchEvent(new CustomEvent('voice:result', {
            bubbles: true,
            detail: { text: cleaned }
        }));
    }

    _handleError(errorCode, message) {
        this._setListening(false);

        const errorMessages = {
            'no-speech': '未检测到语音，请再试一次',
            'audio-capture': '未找到麦克风，请检查设备',
            'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许',
            'network': '网络错误，语音识别需要网络连接',
            'aborted': '语音识别已取消',
            'service-not-allowed': '语音服务不可用',
            'start-failed': '语音识别启动失败，请重试',
            'media-recorder': '录音失败，请重试'
        };

        const userMessage = errorMessages[errorCode] || message || '语音识别出错，请重试';

        this._setStatus(userMessage, true);

        if (typeof this._onError === 'function') {
            this._onError(errorCode, userMessage);
        }

        this._element?.dispatchEvent(new CustomEvent('voice:error', {
            bubbles: true,
            detail: { code: errorCode, message: userMessage }
        }));

        setTimeout(() => {
            if (this._statusElement) {
                this._statusElement.textContent = '';
                this._statusElement.classList.remove('voice-btn__status--error');
            }
        }, 3000);
    }

    _cleanTranscript(text) {
        return text
            .replace(/[吗呢吧啊哦呀嘛咯哈嘿嗯]+$/g, '')
            .replace(/^(这个|那个|请问|我想问|我想知道)/g, '')
            .replace(/(是什么|属于什么|怎么分|怎么分类|分类|垃圾)$/g, '')
            .trim();
    }

    _setListening(listening) {
        this._isListening = listening;
        const btn = this._element?.querySelector('.voice-btn');
        if (btn) {
            btn.classList.toggle('voice-btn--listening', listening);
            btn.setAttribute('aria-label', listening ? '停止语音输入' : '语音输入');
        }
        if (this._waveElement) {
            this._waveElement.classList.toggle('voice-btn__wave--active', listening);
        }
        if (typeof this._onStateChange === 'function') {
            this._onStateChange(listening);
        }
    }

    _setStatus(text, isError = false) {
        if (!this._statusElement) return;
        this._statusElement.textContent = text;
        this._statusElement.classList.toggle('voice-btn__status--error', isError);
        this._statusElement.classList.toggle('voice-btn__status--visible', !!text);
    }

    _showUnsupportedTip() {
        const isFirefox = navigator.userAgent.includes('Firefox');
        const tip = isFirefox
            ? '当前浏览器不支持语音识别，建议使用 Chrome 或 Edge 浏览器'
            : '您的浏览器不支持语音识别功能，请使用 Chrome 或 Edge 浏览器';

        if (typeof this._onError === 'function') {
            this._onError('unsupported', tip);
        }

        this._setStatus(tip, true);
        setTimeout(() => {
            if (this._statusElement) {
                this._statusElement.textContent = '';
                this._statusElement.classList.remove('voice-btn__status--error', 'voice-btn__status--visible');
            }
        }, 4000);
    }
}

const VOICE_BTN_STYLES = `
.voice-btn-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    position: relative;
}

.voice-btn {
    width: 48px;
    height: 48px;
    border: none;
    border-radius: var(--radius-full, 9999px);
    background: linear-gradient(135deg, var(--primary, #2D9B5E), var(--primary-light, #3DB974));
    color: white;
    cursor: pointer;
    transition: all var(--transition, 0.25s cubic-bezier(0.4, 0, 0.2, 1));
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(45, 155, 94, 0.25);
    flex-shrink: 0;
    position: relative;
    overflow: hidden;
    -webkit-tap-highlight-color: transparent;
}

.voice-btn:hover {
    opacity: 0.92;
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(45, 155, 94, 0.32);
}

.voice-btn:active {
    transform: scale(0.95);
}

.voice-btn:focus-visible {
    outline: 3px solid var(--primary, #2D9B5E);
    outline-offset: 2px;
}

.voice-btn svg {
    width: 20px;
    height: 20px;
    fill: white;
}

.voice-btn__icon {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.25s ease;
}

.voice-btn--listening .voice-btn__icon {
    opacity: 0;
}

.voice-btn--listening {
    background: linear-gradient(135deg, #E74C3C, #C0392B);
    box-shadow: 0 4px 12px rgba(231, 76, 60, 0.35);
    animation: voicePulse 1.2s infinite;
}

@keyframes voicePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.35); }
    50% { box-shadow: 0 0 0 14px rgba(231, 76, 60, 0); }
}

.voice-btn__wave {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    z-index: 1;
    opacity: 0;
    transition: opacity 0.25s ease;
}

.voice-btn__wave--active {
    opacity: 1;
}

.voice-btn__wave-bar {
    width: 3px;
    height: 8px;
    background: white;
    border-radius: 2px;
    animation: waveBar 0.8s ease-in-out infinite;
}

.voice-btn__wave-bar:nth-child(1) { animation-delay: 0s; height: 6px; }
.voice-btn__wave-bar:nth-child(2) { animation-delay: 0.1s; height: 12px; }
.voice-btn__wave-bar:nth-child(3) { animation-delay: 0.2s; height: 18px; }
.voice-btn__wave-bar:nth-child(4) { animation-delay: 0.1s; height: 12px; }
.voice-btn__wave-bar:nth-child(5) { animation-delay: 0s; height: 6px; }

@keyframes waveBar {
    0%, 100% { transform: scaleY(0.4); }
    50% { transform: scaleY(1); }
}

.voice-btn__status {
    font-size: 0.75rem;
    color: var(--text-secondary, #5A6776);
    text-align: center;
    max-width: 200px;
    min-height: 0;
    overflow: hidden;
    transition: all 0.25s ease;
    opacity: 0;
    line-height: 1.3;
}

.voice-btn__status--visible {
    opacity: 1;
    min-height: 1.2em;
}

.voice-btn__status--error {
    color: var(--cat-hazardous, #dc3545);
}

@media (prefers-reduced-motion: reduce) {
    .voice-btn,
    .voice-btn__wave-bar {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
    .voice-btn:hover {
        transform: none;
    }
}
`;

if (!document.getElementById('voice-btn-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'voice-btn-styles';
    styleSheet.textContent = VOICE_BTN_STYLES;
    document.head.appendChild(styleSheet);
}

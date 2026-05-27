import { store } from '../store.js';
import { api } from '../api.js';
import { showToast } from '../utils/ui.js';

const DEFAULT_SETTINGS = {
    mode: 'fast',
    show_on_leaderboard: true,
    notifications: {
        checkin_reminder: true,
        quiz_reminder: true,
        event_notifications: true
    }
};

export class SettingsPage {
    container = null;
    _settings = { ...DEFAULT_SETTINGS };
    _boundHandlers = {};
    _hasChanges = false;

    init() {
        this.container = document.getElementById('page-settings');
        this._render();
        this._loadSettings();
    }

    _render() {
        const content = this.container.querySelector('.page__content');
        content.innerHTML = `
            <div class="settings-header">
                <button class="btn btn-ghost settings-back" id="settingsBackBtn">← 返回</button>
                <h2 class="settings-title">⚙️ 偏好设置</h2>
            </div>

            <div class="settings-section card">
                <h3 class="settings-section__title">识别模式</h3>
                <div class="settings-option">
                    <div class="settings-option__info">
                        <span class="settings-option__label">默认识别模式</span>
                        <span class="settings-option__desc">选择识别结果的展示详细程度</span>
                    </div>
                    <select class="settings-select" id="settingsMode">
                        <option value="fast">快速模式</option>
                        <option value="detailed">详细模式</option>
                    </select>
                </div>
            </div>

            <div class="settings-section card">
                <h3 class="settings-section__title">隐私设置</h3>
                <div class="settings-option">
                    <div class="settings-option__info">
                        <span class="settings-option__label">排行榜可见性</span>
                        <span class="settings-option__desc">开启后你的昵称和积分将显示在排行榜中</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="settingsLeaderboard" checked>
                        <span class="toggle__slider"></span>
                    </label>
                </div>
            </div>

            <div class="settings-section card">
                <h3 class="settings-section__title">通知设置</h3>
                <div class="settings-option">
                    <div class="settings-option__info">
                        <span class="settings-option__label">打卡提醒</span>
                        <span class="settings-option__desc">每日提醒您完成环保打卡</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="settingsCheckinReminder" checked>
                        <span class="toggle__slider"></span>
                    </label>
                </div>
                <div class="settings-option">
                    <div class="settings-option__info">
                        <span class="settings-option__label">答题提醒</span>
                        <span class="settings-option__desc">每日推送环保知识问答</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="settingsQuizReminder" checked>
                        <span class="toggle__slider"></span>
                    </label>
                </div>
                <div class="settings-option">
                    <div class="settings-option__info">
                        <span class="settings-option__label">活动通知</span>
                        <span class="settings-option__desc">有新活动时接收通知</span>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="settingsEventNotifications" checked>
                        <span class="toggle__slider"></span>
                    </label>
                </div>
            </div>

            <div class="settings-actions">
                <button class="btn btn-primary btn-block" id="settingsSaveBtn">保存设置</button>
                <button class="btn btn-secondary btn-block" id="settingsResetBtn">恢复默认</button>
            </div>
        `;

        this._bindEvents();
    }

    _bindEvents() {
        this._boundHandlers.back = () => {
            if (this._hasChanges) {
                if (confirm('有未保存的更改，确定要离开吗？')) {
                    window.location.hash = '#/profile';
                }
            } else {
                window.location.hash = '#/profile';
            }
        };
        document.getElementById('settingsBackBtn').addEventListener('click', this._boundHandlers.back);

        const selects = this.container.querySelectorAll('select');
        selects.forEach(select => {
            const handler = () => {
                this._hasChanges = true;
            };
            select.addEventListener('change', handler);
            this._boundHandlers['select_' + select.id] = handler;
        });

        const toggles = this.container.querySelectorAll('input[type="checkbox"]');
        toggles.forEach(toggle => {
            const handler = () => {
                this._hasChanges = true;
            };
            toggle.addEventListener('change', handler);
            this._boundHandlers['toggle_' + toggle.id] = handler;
        });

        this._boundHandlers.save = () => this._saveSettings();
        document.getElementById('settingsSaveBtn').addEventListener('click', this._boundHandlers.save);

        this._boundHandlers.reset = () => this._resetSettings();
        document.getElementById('settingsResetBtn').addEventListener('click', this._boundHandlers.reset);
    }

    _loadSettings() {
        const saved = localStorage.getItem('ecosort_settings');
        if (saved) {
            try {
                this._settings = { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
            } catch (e) {
                this._settings = { ...DEFAULT_SETTINGS };
            }
        }
        this._applySettingsToUI();
    }

    _applySettingsToUI() {
        const modeSelect = document.getElementById('settingsMode');
        if (modeSelect) {
            modeSelect.value = this._settings.mode || 'fast';
        }

        const leaderboardToggle = document.getElementById('settingsLeaderboard');
        if (leaderboardToggle) {
            leaderboardToggle.checked = this._settings.show_on_leaderboard !== false;
        }

        const checkinToggle = document.getElementById('settingsCheckinReminder');
        if (checkinToggle) {
            checkinToggle.checked = this._settings.notifications?.checkin_reminder !== false;
        }

        const quizToggle = document.getElementById('settingsQuizReminder');
        if (quizToggle) {
            quizToggle.checked = this._settings.notifications?.quiz_reminder !== false;
        }

        const eventToggle = document.getElementById('settingsEventNotifications');
        if (eventToggle) {
            eventToggle.checked = this._settings.notifications?.event_notifications !== false;
        }

        this._hasChanges = false;
    }

    _collectSettingsFromUI() {
        return {
            mode: document.getElementById('settingsMode')?.value || 'fast',
            show_on_leaderboard: document.getElementById('settingsLeaderboard')?.checked ?? true,
            notifications: {
                checkin_reminder: document.getElementById('settingsCheckinReminder')?.checked ?? true,
                quiz_reminder: document.getElementById('settingsQuizReminder')?.checked ?? true,
                event_notifications: document.getElementById('settingsEventNotifications')?.checked ?? true
            }
        };
    }

    async _saveSettings() {
        const newSettings = this._collectSettingsFromUI();
        const saveBtn = document.getElementById('settingsSaveBtn');
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';

        try {
            localStorage.setItem('ecosort_settings', JSON.stringify(newSettings));
            this._settings = newSettings;
            this._hasChanges = false;

            try {
                await api.updateUserSettings(newSettings);
            } catch (e) {
                console.info('同步到服务器失败，使用本地设置');
            }

            showToast('设置已保存', 'success');
        } catch (e) {
            console.error('保存设置失败:', e);
            showToast('保存失败，请重试', 'error');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = '保存设置';
        }
    }

    _resetSettings() {
        if (confirm('确定要恢复所有设置为默认值吗？')) {
            this._settings = { ...DEFAULT_SETTINGS };
            this._applySettingsToUI();
            localStorage.setItem('ecosort_settings', JSON.stringify(this._settings));
            showToast('已恢复默认设置', 'success');
        }
    }

    destroy() {
        document.getElementById('settingsBackBtn')?.removeEventListener('click', this._boundHandlers.back);
        document.getElementById('settingsSaveBtn')?.removeEventListener('click', this._boundHandlers.save);
        document.getElementById('settingsResetBtn')?.removeEventListener('click', this._boundHandlers.reset);

        const selects = this.container.querySelectorAll('select');
        selects.forEach(select => {
            select.removeEventListener('change', this._boundHandlers['select_' + select.id]);
        });

        const toggles = this.container.querySelectorAll('input[type="checkbox"]');
        toggles.forEach(toggle => {
            toggle.removeEventListener('change', this._boundHandlers['toggle_' + toggle.id]);
        });

        this._boundHandlers = {};
    }
}

export function getUserSettings() {
    const saved = localStorage.getItem('ecosort_settings');
    if (saved) {
        try {
            return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
        } catch (e) {
            return { ...DEFAULT_SETTINGS };
        }
    }
    return { ...DEFAULT_SETTINGS };
}

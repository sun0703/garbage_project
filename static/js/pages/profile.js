import { store } from '../store.js';
import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';

export class ProfilePage {
    container = null;
    _user = null;
    _boundHandlers = {};

    init() {
        this.container = document.getElementById('page-profile');
        this._render();
        this._loadUserData();
    }

    _render() {
        const content = this.container.querySelector('.page__content');
        content.innerHTML = `
            <div class="profile-header">
                <div id="profileAvatar" class="profile-avatar">
                    <div class="avatar-placeholder-lg">?</div>
                </div>
                <div class="profile-info">
                    <h2 id="profileName" class="profile-name">未登录</h2>
                    <p id="profileUsername" class="profile-username">点击下方登录</p>
                </div>
            </div>

            <div id="profileStats" class="profile-stats card">
                <div class="stat-block">
                    <span class="stat-value" id="statPoints">0</span>
                    <span class="stat-label">积分</span>
                </div>
                <div class="stat-block">
                    <span class="stat-value" id="statCheckins">0</span>
                    <span class="stat-label">打卡</span>
                </div>
                <div class="stat-block">
                    <span class="stat-value" id="statQuiz">0</span>
                    <span class="stat-label">答对</span>
                </div>
            </div>

            <div id="profileActions" class="profile-actions">
                <button class="btn btn-primary btn-block" id="profileLoginBtn">登录 / 注册</button>
            </div>

            <div id="checkinHistory" class="profile-section">
                <h3 class="section-title">打卡记录</h3>
                <div id="checkinRecords" class="checkin-records">
                    <p class="no-data">登录后查看打卡记录</p>
                </div>
            </div>
        `;
    }

    async _loadUserData() {
        try {
            const data = await api.getMe();
            if (data.success && data.user) {
                this._user = data.user;
                this._updateProfile(data.user);
                this._loadCheckinHistory();
            }
        } catch (e) {
            console.info('用户未登录');
        }

        this._boundHandlers.login = () => window.location.hash = '#/community';
        document.getElementById('profileLoginBtn')?.addEventListener('click', this._boundHandlers.login);
    }

    _updateProfile(user) {
        const nameEl = document.getElementById('profileName');
        const usernameEl = document.getElementById('profileUsername');
        const avatarEl = document.getElementById('profileAvatar');
        const pointsEl = document.getElementById('statPoints');
        const checkinsEl = document.getElementById('statCheckins');
        const quizEl = document.getElementById('statQuiz');
        const actionsEl = document.getElementById('profileActions');

        const safeNickname = escapeHtml(user.nickname || user.username || '');
        const safeUsername = escapeHtml(user.username || '');
        const safeAvatar = escapeHtml(user.avatar || '');
        const safeInitial = escapeHtml((user.nickname || user.username || '?')[0]);
        const isSafeUrl = (url) => /^https?:/.test(url);

        if (nameEl) nameEl.textContent = user.nickname || user.username;
        if (usernameEl) usernameEl.textContent = `@${user.username}`;
        if (avatarEl) {
            if (user.avatar && isSafeUrl(user.avatar)) {
                avatarEl.innerHTML = `<img src="${safeAvatar}" alt="头像" class="avatar-img-lg">`;
            } else {
                avatarEl.innerHTML = `<div class="avatar-placeholder-lg">${safeInitial}</div>`;
            }
        }
        if (pointsEl) pointsEl.textContent = user.points || 0;
        if (checkinsEl) checkinsEl.textContent = user.checkin_count || 0;
        if (quizEl) quizEl.textContent = user.quiz_correct || 0;

        if (actionsEl) {
            actionsEl.innerHTML = `
                <button class="btn btn-secondary btn-block" id="profileLogoutBtn">退出登录</button>
            `;
            this._boundHandlers.logout = () => this._handleLogout();
            document.getElementById('profileLogoutBtn')?.addEventListener('click', this._boundHandlers.logout);
        }
    }

    async _loadCheckinHistory() {
        const recordsEl = document.getElementById('checkinRecords');
        if (!recordsEl || !this._user) return;

        try {
            const data = await api.getCheckinHistory();
            if (data.success && data.records.length > 0) {
                recordsEl.innerHTML = data.records.slice(0, 10).map(r => {
                    const date = new Date(r.created_at * 1000);
                    const dateStr = `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
                    return `
                        <div class="checkin-record">
                            <span class="record-date">${dateStr}</span>
                            <span class="record-category">${escapeHtml(r.category || '日常打卡')}</span>
                            <span class="record-points">+${r.points_earned}</span>
                        </div>
                    `;
                }).join('');
            } else {
                recordsEl.innerHTML = '<p class="no-data">暂无打卡记录</p>';
            }
        } catch (e) {
            recordsEl.innerHTML = '<p class="no-data">加载失败</p>';
        }
    }

    async _handleLogout() {
        try {
            await api.logout();
            this._user = null;
            this._render();
            this._loadUserData();
        } catch (e) {
            console.error('退出失败:', e);
        }
    }

    destroy() {
        document.getElementById('profileLoginBtn')?.removeEventListener('click', this._boundHandlers.login);
        document.getElementById('profileLogoutBtn')?.removeEventListener('click', this._boundHandlers.logout);
    }
}

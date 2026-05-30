// 个人中心 — 用户信息/等级/成就/设置入口

import { store } from '../store.js';
import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';
import { showToast } from '../utils/ui.js';
import { icon } from '../utils/icons.js';

const LEVELS = [
    { level: 1, name: '环保新人', icon: icon('sprout', 20), threshold: 0 },
    { level: 2, name: '环保达人', icon: icon('leaf', 20), threshold: 50 },
    { level: 3, name: '分类专家', icon: icon('treePine', 20), threshold: 200 },
    { level: 4, name: '绿色先锋', icon: icon('trophy', 20), threshold: 500 },
    { level: 5, name: '环保大使', icon: icon('crown', 20), threshold: 1000 },
];

function calcLevel(points) {
    let current = LEVELS[0];
    for (const lv of LEVELS) {
        if (points >= lv.threshold) current = lv;
        else break;
    }
    return current;
}

function calcLevelProgress(points) {
    const lv = calcLevel(points);
    const idx = LEVELS.findIndex(l => l.level === lv.level);
    if (idx >= LEVELS.length - 1) return 100;
    const next = LEVELS[idx + 1];
    const range = next.threshold - lv.threshold;
    const progress = range > 0 ? ((points - lv.threshold) / range) * 100 : 100;
    return Math.min(100, Math.max(0, progress));
}

export class ProfilePage {
    container = null;
    _user = null;
    _boundHandlers = {};
    _activeTab = 'checkin';

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

            <div class="profile-level-bar card hidden" id="profileLevelBar">
                <div class="level-bar-header">
                    <span class="level-badge" id="levelBadge">${icon('sprout', 16)} Lv.1</span>
                    <span class="level-name" id="levelName">环保新人</span>
                    <span class="level-progress-text" id="levelProgressText">0/50</span>
                </div>
                <div class="level-progress-track">
                    <div class="level-progress-fill" id="levelProgressFill" style="width:0%"></div>
                </div>
            </div>

            <div id="profileStats" class="profile-stats card">
                <div class="stat-block stat-block--clickable" id="statBlockPoints">
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

            <div class="profile-quick-grid hidden" id="profileQuickGrid">
                <div class="quick-item" data-action="points">
                    <div class="quick-item-icon">${icon('diamond', 24)}</div>
                    <span class="quick-item-label">积分明细</span>
                </div>
                <div class="quick-item" data-action="checkin">
                    <div class="quick-item-icon">${icon('mapPin', 24)}</div>
                    <span class="quick-item-label">打卡记录</span>
                </div>
                <div class="quick-item" data-action="quiz">
                    <div class="quick-item-icon">${icon('brain', 24)}</div>
                    <span class="quick-item-label">答题记录</span>
                </div>
                <div class="quick-item" data-action="settings">
                    <div class="quick-item-icon">${icon('settings', 24)}</div>
                    <span class="quick-item-label">设置</span>
                </div>
            </div>

            <div id="profileActions" class="profile-actions">
                <button class="btn btn-primary btn-block" id="profileLoginBtn">登录 / 注册</button>
            </div>

            <div id="profileDetailSection" class="profile-section hidden">
                <div class="profile-tabs">
                    <button class="profile-tab active" data-tab="checkin">打卡记录</button>
                    <button class="profile-tab" data-tab="points">积分流水</button>
                </div>
                <div id="checkinRecords" class="checkin-records">
                    <p class="no-data">加载中...</p>
                </div>
                <div id="pointsRecords" class="checkin-records hidden">
                    <p class="no-data">加载中...</p>
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
                this._showLoggedIn();
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

        const safeNickname = escapeHtml(user.nickname || user.username || '');
        const safeUsername = escapeHtml(user.username || '');
        const safeAvatar = escapeHtml(user.avatar || '');
        const safeInitial = escapeHtml((user.nickname || user.username || '?')[0]);
        const isSafeUrl = (url) => /^https?:/.test(url);

        // 角色标识展示（需求 F-4.1.3）
        const roleMap = { admin: '管理员', user: '用户', moderator: '版主' };
        const roleLabel = roleMap[user.role] || '用户';
        const roleClass = user.role === 'admin' ? 'profile-role--admin' : 'profile-role--user';

        if (nameEl) nameEl.innerHTML = `${safeNickname} <span class="profile-role-badge ${roleClass}">${roleLabel}</span>`;
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

        this._updateLevelBar(user.points || 0);
    }

    _updateLevelBar(points) {
        const bar = document.getElementById('profileLevelBar');
        if (!bar) return;
        bar.classList.remove('hidden');

        const lv = calcLevel(points);
        const progress = calcLevelProgress(points);
        const idx = LEVELS.findIndex(l => l.level === lv.level);
        const nextLv = idx < LEVELS.length - 1 ? LEVELS[idx + 1] : null;

        const badgeEl = document.getElementById('levelBadge');
        const nameEl = document.getElementById('levelName');
        const progressTextEl = document.getElementById('levelProgressText');
        const fillEl = document.getElementById('levelProgressFill');

        if (badgeEl) badgeEl.textContent = `${lv.icon} Lv.${lv.level}`;
        if (nameEl) nameEl.textContent = lv.name;
        if (progressTextEl) {
            progressTextEl.textContent = nextLv
                ? `${points - lv.threshold}/${nextLv.threshold - lv.threshold}`
                : '已满级';
        }
        if (fillEl) {
            fillEl.style.width = `${progress}%`;
            if (progress >= 100) fillEl.classList.add('level-progress-fill--done');
            else fillEl.classList.remove('level-progress-fill--done');
        }
    }

    _showLoggedIn() {
        document.getElementById('profileQuickGrid')?.classList.remove('hidden');
        document.getElementById('profileDetailSection')?.classList.remove('hidden');

        const actionsEl = document.getElementById('profileActions');
        if (actionsEl) {
            actionsEl.innerHTML = `
                <button class="btn btn-secondary btn-block" id="profileLogoutBtn">退出登录</button>
            `;
            this._boundHandlers.logout = () => this._doLogout();
            document.getElementById('profileLogoutBtn')?.addEventListener('click', this._boundHandlers.logout);
        }

        this._bindTabs();
        this._bindQuickGrid();
        this._bindStatClick();
    }

    _bindTabs() {
        const tabs = this.container.querySelectorAll('.profile-tab');
        tabs.forEach(tab => {
            const handler = () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this._activeTab = tab.dataset.tab;

                const checkinEl = document.getElementById('checkinRecords');
                const pointsEl = document.getElementById('pointsRecords');
                if (this._activeTab === 'checkin') {
                    checkinEl?.classList.remove('hidden');
                    pointsEl?.classList.add('hidden');
                } else {
                    checkinEl?.classList.add('hidden');
                    pointsEl?.classList.remove('hidden');
                }

                if (this._activeTab === 'points') this._loadPointsHistory();
            };
            tab.addEventListener('click', handler);
            this._boundHandlers['tab_' + tab.dataset.tab] = handler;
        });
    }

    _bindQuickGrid() {
        const items = this.container.querySelectorAll('.quick-item');
        items.forEach(item => {
            const handler = () => {
                const action = item.dataset.action;
                if (action === 'points') {
                    this._switchTab('points');
                } else if (action === 'checkin') {
                    this._switchTab('checkin');
                } else if (action === 'quiz') {
                    window.location.hash = '#/community';
                } else if (action === 'settings') {
                    window.location.hash = '#/settings';
                }
            };
            item.addEventListener('click', handler);
            this._boundHandlers['quick_' + item.dataset.action] = handler;
        });
    }

    _bindStatClick() {
        const pointsBlock = document.getElementById('statBlockPoints');
        if (pointsBlock) {
            const handler = () => this._switchTab('points');
            pointsBlock.addEventListener('click', handler);
            this._boundHandlers.statPoints = handler;
        }
    }

    _switchTab(tabName) {
        const tabs = this.container.querySelectorAll('.profile-tab');
        tabs.forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tabName);
        });
        this._activeTab = tabName;

        const checkinEl = document.getElementById('checkinRecords');
        const pointsEl = document.getElementById('pointsRecords');
        if (tabName === 'checkin') {
            checkinEl?.classList.remove('hidden');
            pointsEl?.classList.add('hidden');
        } else {
            checkinEl?.classList.add('hidden');
            pointsEl?.classList.remove('hidden');
        }
        if (tabName === 'points') this._loadPointsHistory();
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

    async _loadPointsHistory() {
        const recordsEl = document.getElementById('pointsRecords');
        if (!recordsEl || !this._user) return;

        try {
            const data = await api.getPointsHistory(1, 50);
            const records = data.records || (Array.isArray(data) ? data : []);
            if (records.length > 0) {
                recordsEl.innerHTML = records.map(r => {
                    const date = new Date(r.created_at * 1000);
                    const dateStr = `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
                    const typeLabel = { checkin: '打卡', quiz: '答题', prediction: '识别' }[r.type] || r.type;
                    const sign = r.amount >= 0 ? '+' : '';
                    return `
                        <div class="points-record">
                            <div class="points-record-left">
                                <span class="points-record-type">${escapeHtml(typeLabel)}</span>
                                <span class="points-record-desc">${escapeHtml(r.description || '')}</span>
                            </div>
                            <div class="points-record-right">
                                <span class="points-record-amount points-${r.amount >= 0 ? 'earn' : 'spend'}">${sign}${r.amount}</span>
                                <span class="points-record-balance">余额: ${r.balance_after}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                recordsEl.innerHTML = '<p class="no-data">暂无积分流水</p>';
            }
        } catch (e) {
            recordsEl.innerHTML = '<p class="no-data">加载失败</p>';
        }
    }

    async _doLogout() {
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
        document.getElementById('statBlockPoints')?.removeEventListener('click', this._boundHandlers.statPoints);

        const tabs = this.container?.querySelectorAll('.profile-tab');
        tabs?.forEach(tab => {
            tab.removeEventListener('click', this._boundHandlers['tab_' + tab.dataset.tab]);
        });

        const items = this.container?.querySelectorAll('.quick-item');
        items?.forEach(item => {
            item.removeEventListener('click', this._boundHandlers['quick_' + item.dataset.action]);
        });
    }
}

import { store } from '../store.js';
import { api } from '../api.js';

export class CommunityPage {
    container = null;
    _user = null;
    _quiz = null;
    _quizAnswered = false;
    _boundHandlers = {};

    init() {
        this.container = document.getElementById('page-community');
        this._render();
        this._loadUserData();
        this._loadDailyQuiz();
        this._loadActivities();
        this._loadTodayCheckin();
    }

    _render() {
        const content = this.container.querySelector('.page__content');
        content.innerHTML = `
            <div class="community-header">
                <h2 class="community-title">环保社区</h2>
            </div>

            <div id="userCard" class="card community-user-card">
                <div class="user-card-placeholder">
                    <svg viewBox="0 0 24 24" width="40" height="40" fill="#ccc"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                    <p>登录后参与社区互动</p>
                    <button class="btn btn-primary btn-sm" id="loginBtn">登录 / 注册</button>
                </div>
            </div>

            <div class="community-section">
                <h3 class="section-title">每日打卡</h3>
                <div id="checkinCard" class="card checkin-card">
                    <div class="checkin-info">
                        <div class="checkin-icon">🌱</div>
                        <div class="checkin-text">
                            <p class="checkin-desc">每日打卡获得 5 积分</p>
                            <p class="checkin-status" id="checkinStatus">加载中...</p>
                        </div>
                    </div>
                    <button class="btn btn-primary" id="checkinBtn" disabled>打卡</button>
                </div>
            </div>

            <div class="community-section">
                <h3 class="section-title">每日问答</h3>
                <div id="quizCard" class="card quiz-card">
                    <div class="quiz-loading">加载中...</div>
                </div>
            </div>

            <div class="community-section">
                <h3 class="section-title">环保活动</h3>
                <div id="activityList" class="activity-list">
                    <div class="activity-loading">加载中...</div>
                </div>
            </div>
        `;
    }

    async _loadUserData() {
        try {
            const data = await api.getMe();
            if (data.success && data.user) {
                this._user = data.user;
                this._renderUserCard(data.user);
            }
        } catch (e) {
            /* UNAUTH(401) 是预期行为：用户未登录，完全静默不输出任何日志 */
            if (e.code !== 'UNAUTH') {
                console.info('用户未登录');
            }
        }

        this._boundHandlers.login = () => this._showLoginModal();
        document.getElementById('loginBtn')?.addEventListener('click', this._boundHandlers.login);
    }

    _renderUserCard(user) {
        const card = document.getElementById('userCard');
        if (!card) return;
        card.innerHTML = `
            <div class="user-card-info">
                <div class="user-avatar">
                    ${user.avatar ? `<img src="${user.avatar}" alt="头像">` : `<div class="avatar-placeholder">${(user.nickname || user.username)[0]}</div>`}
                </div>
                <div class="user-detail">
                    <h3 class="user-nickname">${user.nickname || user.username}</h3>
                    <div class="user-stats">
                        <span class="stat-item">🏆 ${user.points || 0} 积分</span>
                        <span class="stat-item">📅 ${user.checkin_count || 0} 次打卡</span>
                        <span class="stat-item">✅ ${user.quiz_correct || 0}/${user.quiz_total || 0} 答题</span>
                    </div>
                </div>
            </div>
            <button class="btn btn-secondary btn-sm" id="logoutBtn">退出</button>
        `;

        this._boundHandlers.logout = () => this._handleLogout();
        document.getElementById('logoutBtn')?.addEventListener('click', this._boundHandlers.logout);
    }

    async _loadTodayCheckin() {
        const statusEl = document.getElementById('checkinStatus');
        const btn = document.getElementById('checkinBtn');
        if (!statusEl || !btn) return;

        /* 登录状态预检：用户未登录时直接展示降级 UI，避免发起 401 请求 */
        if (!store.get('currentUser')) {
            statusEl.textContent = '请登录后打卡';
            btn.disabled = true;
            return;
        }

        try {
            const data = await api.getTodayCheckin();
            if (data.success && data.checked_in) {
                statusEl.textContent = '今日已打卡 ✓';
                btn.disabled = true;
                btn.textContent = '已打卡';
                btn.classList.add('btn-disabled');
            } else {
                statusEl.textContent = '今日尚未打卡';
                btn.disabled = false;
                this._boundHandlers.checkin = () => this._handleCheckin();
                btn.addEventListener('click', this._boundHandlers.checkin);
            }
        } catch (e) {
            statusEl.textContent = '请登录后打卡';
            btn.disabled = true;
        }
    }

    async _handleCheckin() {
        const btn = document.getElementById('checkinBtn');
        if (btn) btn.disabled = true;
        try {
            const data = await api.checkin();
            if (data.success) {
                const statusEl = document.getElementById('checkinStatus');
                if (statusEl) statusEl.textContent = `打卡成功！+${data.checkin.points_earned} 积分`;
                if (btn) { btn.textContent = '已打卡'; btn.classList.add('btn-disabled'); }
                this._loadUserData();
            } else {
                alert(data.error?.message || '打卡失败');
                if (btn) btn.disabled = false;
            }
        } catch (e) {
            alert('打卡失败，请稍后重试');
            if (btn) btn.disabled = false;
        }
    }

    async _loadDailyQuiz() {
        const quizCard = document.getElementById('quizCard');
        if (!quizCard) return;

        try {
            const data = await api.getDailyQuiz();
            if (data.success && data.quiz) {
                this._quiz = data.quiz;
                this._quizAnswered = false;
                this._renderQuiz(data.quiz);
            } else {
                quizCard.innerHTML = '<p class="quiz-done">今日题目已全部完成，明天再来！🎉</p>';
            }
        } catch (e) {
            quizCard.innerHTML = '<p class="quiz-error">加载题目失败</p>';
        }
    }

    _renderQuiz(quiz) {
        const quizCard = document.getElementById('quizCard');
        if (!quizCard) return;

        const labels = ['A', 'B', 'C', 'D'];
        quizCard.innerHTML = `
            <div class="quiz-question">
                <span class="quiz-difficulty">${'⭐'.repeat(quiz.difficulty || 1)}</span>
                <p class="quiz-text">${quiz.question}</p>
            </div>
            <div class="quiz-options">
                ${quiz.options.map((opt, i) => `
                    <button class="quiz-option" data-index="${i}">
                        <span class="option-label">${labels[i]}</span>
                        <span class="option-text">${opt}</span>
                    </button>
                `).join('')}
            </div>
            <div id="quizResult" class="quiz-result" style="display:none"></div>
        `;

        quizCard.querySelectorAll('.quiz-option').forEach(btn => {
            btn.addEventListener('click', () => {
                if (this._quizAnswered) return;
                this._quizAnswered = true;
                this._handleQuizAnswer(parseInt(btn.dataset.index));
            });
        });
    }

    async _handleQuizAnswer(selected) {
        if (!this._quiz) return;

        const options = document.querySelectorAll('.quiz-option');
        options.forEach(btn => btn.style.pointerEvents = 'none');

        try {
            const data = await api.answerQuiz(this._quiz.id, selected);
            const resultEl = document.getElementById('quizResult');

            if (data.success) {
                const r = data.result;
                options.forEach(btn => {
                    const idx = parseInt(btn.dataset.index);
                    if (idx === r.correct_answer) {
                        btn.classList.add('option-correct');
                    } else if (idx === selected && !r.is_correct) {
                        btn.classList.add('option-wrong');
                    }
                });

                if (resultEl) {
                    resultEl.style.display = 'block';
                    resultEl.innerHTML = `
                        <div class="quiz-result-inner ${r.is_correct ? 'result-correct' : 'result-wrong'}">
                            <p class="result-status">${r.is_correct ? '✅ 回答正确！' : '❌ 回答错误'}</p>
                            ${r.points_earned > 0 ? `<p class="result-points">+${r.points_earned} 积分</p>` : ''}
                            <p class="result-explanation">${r.explanation}</p>
                        </div>
                    `;
                }
                this._loadUserData();
            }
        } catch (e) {
            alert('提交答案失败');
            options.forEach(btn => btn.style.pointerEvents = 'auto');
            this._quizAnswered = false;
        }
    }

    async _loadActivities() {
        const listEl = document.getElementById('activityList');
        if (!listEl) return;

        try {
            const data = await api.getActivities('open');
            if (data.success && data.activities.length > 0) {
                const formatTime = (ts) => {
                    if (!ts) return '';
                    const d = new Date(ts * 1000);
                    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                };
                listEl.innerHTML = data.activities.map(a => `
                    <div class="activity-card card" data-activity-id="${a.id}">
                        <div class="activity-card-header">
                            <h4 class="activity-title">${a.title}</h4>
                            <span class="activity-status activity-open">报名中</span>
                        </div>
                        <p class="activity-desc">${a.description.substring(0, 80)}${a.description.length > 80 ? '...' : ''}</p>
                        <div class="activity-meta">
                            <span>📍 ${a.location}</span>
                            <span>👥 ${a.current_participants}/${a.max_participants || '不限'}</span>
                            <span>🏢 ${a.organizer}</span>
                        </div>
                        <button class="btn btn-primary btn-sm activity-signup-btn" data-id="${a.id}">立即报名</button>
                        <div class="activity-detail" style="display:none">
                            <div class="activity-detail-inner">
                                <p class="activity-full-desc">${a.description || '暂无描述'}</p>
                                <div class="activity-detail-meta">
                                    <p>⏰ 时间：${formatTime(a.start_time)} ~ ${formatTime(a.end_time)}</p>
                                    <p>📍 地点：${a.location}</p>
                                    <p>👥 人数上限：${a.max_participants || '不限'}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');

                listEl.querySelectorAll('.activity-card').forEach(card => {
                    card.addEventListener('click', (e) => {
                        if (e.target.closest('.activity-signup-btn')) return;
                        const detail = card.querySelector('.activity-detail');
                        if (detail) detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
                    });
                });

                const checkSignedMap = {};
                try {
                    for (const a of data.activities) {
                        const res = await api.checkActivitySignup(a.id);
                        checkSignedMap[a.id] = res.success && res.signed_up;
                    }
                } catch(e) {}

                listEl.querySelectorAll('.activity-signup-btn').forEach(btn => {
                    const actId = btn.dataset.id;
                    if (checkSignedMap[actId]) {
                        btn.textContent = '取消报名';
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-danger');
                    }
                    btn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const isCancel = btn.textContent === '取消报名';
                        btn.disabled = true;
                        btn.textContent = isCancel ? '取消中...' : '报名中...';
                        try {
                            let res;
                            if (isCancel) {
                                res = await api.cancelActivitySignup(actId);
                                if (res.success) {
                                    btn.textContent = '立即报名';
                                    btn.classList.remove('btn-danger');
                                    btn.classList.add('btn-primary');
                                }
                            } else {
                                res = await api.signupActivity(actId);
                                if (res.success) {
                                    btn.textContent = '取消报名';
                                    btn.classList.remove('btn-primary');
                                    btn.classList.add('btn-danger');
                                }
                            }
                            if (!res.success) {
                                alert(res.error?.message || (isCancel ? '取消失败' : '报名失败'));
                                btn.textContent = isCancel ? '取消报名' : '立即报名';
                            }
                            btn.disabled = false;
                        } catch (err) {
                            alert(isCancel ? '取消失败，请稍后重试' : '报名失败，请稍后重试');
                            btn.disabled = false;
                            btn.textContent = isCancel ? '取消报名' : '立即报名';
                        }
                    });
                });
            } else {
                listEl.innerHTML = '<p class="no-data">暂无活动</p>';
            }
        } catch (e) {
            listEl.innerHTML = '<p class="no-data">加载活动失败</p>';
        }
    }

    _showLoginModal() {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-card">
                <div class="modal-tabs">
                    <button class="modal-tab active" data-tab="login">登录</button>
                    <button class="modal-tab" data-tab="register">注册</button>
                </div>
                <div id="loginForm" class="modal-form">
                    <div class="form-group">
                        <label>用户名</label>
                        <input type="text" id="loginUsername" class="form-input" placeholder="请输入用户名" autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label>密码</label>
                        <input type="password" id="loginPassword" class="form-input" placeholder="请输入密码" autocomplete="current-password">
                    </div>
                    <div class="form-group form-group-row">
                        <label class="checkbox-label">
                            <input type="checkbox" id="loginRemember"> 记住我（7天内免登录）
                        </label>
                    </div>
                    <button class="btn btn-primary btn-block" id="submitLogin">登录</button>
                    <p class="form-error" id="loginError" style="display:none"></p>
                </div>
                <div id="registerForm" class="modal-form" style="display:none">
                    <div class="form-group">
                        <label>用户名</label>
                        <input type="text" id="regUsername" class="form-input" placeholder="3-20个字符" autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label>密码</label>
                        <input type="password" id="regPassword" class="form-input" placeholder="6-32个字符" autocomplete="new-password">
                    </div>
                    <div class="form-group">
                        <label>昵称</label>
                        <input type="text" id="regNickname" class="form-input" placeholder="选填" autocomplete="nickname">
                    </div>
                    <button class="btn btn-primary btn-block" id="submitRegister">注册</button>
                    <p class="form-error" id="regError" style="display:none"></p>
                </div>
                <button class="modal-close" id="closeModal">&times;</button>
            </div>
        `;
        document.body.appendChild(overlay);

        overlay.querySelectorAll('.modal-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                overlay.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const isLogin = tab.dataset.tab === 'login';
                document.getElementById('loginForm').style.display = isLogin ? 'block' : 'none';
                document.getElementById('registerForm').style.display = isLogin ? 'none' : 'block';
            });
        });

        document.getElementById('closeModal').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

        document.getElementById('submitLogin').addEventListener('click', async () => {
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            const remember = document.getElementById('loginRemember')?.checked || false;
            const errEl = document.getElementById('loginError');
            if (!username || !password) { errEl.textContent = '请填写用户名和密码'; errEl.style.display = 'block'; return; }
            try {
                const data = await api.login(username, password, remember);
                if (data.success) {
                    overlay.remove();
                    this._user = data.user;
                    this._renderUserCard(data.user);
                    this._loadTodayCheckin();
                } else {
                    errEl.textContent = data.error?.message || '登录失败';
                    errEl.style.display = 'block';
                }
            } catch (e) {
                errEl.textContent = '登录失败，请稍后重试';
                errEl.style.display = 'block';
            }
        });

        document.getElementById('submitRegister').addEventListener('click', async () => {
            const username = document.getElementById('regUsername').value.trim();
            const password = document.getElementById('regPassword').value;
            const nickname = document.getElementById('regNickname').value.trim();
            const errEl = document.getElementById('regError');
            if (!username || !password) { errEl.textContent = '请填写用户名和密码'; errEl.style.display = 'block'; return; }
            if (username.length < 3) { errEl.textContent = '用户名至少3个字符'; errEl.style.display = 'block'; return; }
            if (password.length < 6) { errEl.textContent = '密码至少6个字符'; errEl.style.display = 'block'; return; }
            try {
                const data = await api.register(username, password, nickname);
                if (data.success) {
                    overlay.remove();
                    this._user = data.user;
                    this._renderUserCard(data.user);
                    this._loadTodayCheckin();
                } else {
                    errEl.textContent = data.error?.message || '注册失败';
                    errEl.style.display = 'block';
                }
            } catch (e) {
                errEl.textContent = '注册失败，请稍后重试';
                errEl.style.display = 'block';
            }
        });
    }

    async _handleLogout() {
        try {
            await api.logout();
            this._user = null;
            this._render();
            this._loadUserData();
            this._loadTodayCheckin();
            this._loadDailyQuiz();
            this._loadActivities();
        } catch (e) {
            console.error('退出失败:', e);
        }
    }

    destroy() {
        document.getElementById('loginBtn')?.removeEventListener('click', this._boundHandlers.login);
        document.getElementById('logoutBtn')?.removeEventListener('click', this._boundHandlers.logout);
        document.getElementById('checkinBtn')?.removeEventListener('click', this._boundHandlers.checkin);
    }
}

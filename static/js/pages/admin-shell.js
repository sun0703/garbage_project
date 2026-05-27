import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';

export class AdminShell {
    container = null;
    _adminUser = null;
    _currentPage = 'dashboard';
    _pageInstance = null;

    _navItems = [
        { id: 'dashboard', label: '数据仪表盘', icon: '\u{1F4CA}' },
        { id: 'users', label: '用户管理', icon: '\u{1F465}' },
        { id: 'content', label: '内容管理', icon: '\u{1F4DD}' },
        { id: 'points', label: '投放点维护', icon: '\u{1F4CD}' },
        { id: 'models', label: '模型管理', icon: '\u{1F916}' },
        { id: 'activities', label: '活动管理', icon: '\u{1F389}' },
    ];

    constructor(options = {}) {
        this._api = options.api || api;
    }

    init() {
        this.container = document.getElementById('page-admin');
        if (!this.container) {
            console.warn('[AdminShell] 找不到 #page-admin 容器，初始化中断');
            return;
        }

        document.body.setAttribute('data-admin-active', '');
        this._renderNav();
        this._checkAuth();
    }

    async _checkAuth() {
        try {
            const d = await this._api.adminCheck();
            const user = d.user || d.data || d;
            if (user && (user.username || user.nickname)) {
                this._adminUser = user;
                this._renderSidebarUser();
                this._loadPage('dashboard');
            }
        } catch (_) {
            this._showLogin();
        }
    }

    _renderNav() {
        const nav = document.getElementById('adminNav');
        if (!nav) return;

        nav.innerHTML = this._navItems.map(item => `
            <button class="admin-nav__item ${item.id === this._currentPage ? 'active' : ''}"
                    data-page="${item.id}">
                <span>${item.icon}</span> ${item.label}
            </button>
        `).join('');

        nav.querySelectorAll('.admin-nav__item').forEach(btn => {
            btn.addEventListener('click', () => this._loadPage(btn.dataset.page));
        });
    }

    _renderSidebarUser() {
        const el = document.getElementById('adminSidebarUser');
        if (!el || !this._adminUser) return;

        const displayName = this._adminUser.nickname || this._adminUser.username || '管理员';

        el.innerHTML = `
            <div style="padding:12px 20px;border-top:1px solid rgba(255,255,255,0.1);font-size:13px;color:rgba(255,255,255,0.7)">
                \u{1F464} ${escapeHtml(displayName)}<br>
                <span style="font-size:11px;opacity:0.6">管理员</span>
            </div>
        `;
    }

    async _loadPage(pageId) {
        if (pageId === this._currentPage && this._pageInstance) return;

        this._currentPage = pageId;
        this._renderNav();

        const content = document.getElementById('adminPageContent');
        if (!content) {
            console.warn('[AdminShell] 找不到 #adminPageContent 渲染容器');
            return;
        }

        if (this._pageInstance && typeof this._pageInstance.destroy === 'function') {
            try {
                this._pageInstance.destroy();
            } catch (err) {
                console.warn('[AdminShell] 子页面销毁异常:', err);
            }
            this._pageInstance = null;
        }

        content.innerHTML = '<div class="admin-loading">\u23F3 加载中...</div>';

        try {
            const mod = await import(`./admin/${pageId}.js`);
            const PageClass = mod.default || Object.values(mod)[0];

            if (!PageClass) {
                throw new Error(`模块 ${pageId}.js 未导出页面类`);
            }

            this._pageInstance = new PageClass({ api: this._api, container: content });

            if (typeof this._pageInstance.init === 'function') {
                this._pageInstance.init();
            }
        } catch (err) {
            console.error(`[AdminShell] 页面加载失败 (${pageId}):`, err);
            content.innerHTML = `
                <div style="color:#dc3545;padding:40px;text-align:center">
                    <p style="font-size:18px;margin-bottom:8px">\u26A0\uFE0F 页面加载失败</p>
                    <p style="color:#999;font-size:13px">${err.message}</p>
                </div>
            `;
        }
    }

    _showLogin() {
        const content = document.getElementById('adminPageContent');
        if (!content) return;

        content.innerHTML = `
            <div style="max-width:380px;margin:80px auto;background:#fff;border-radius:16px;padding:32px;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
                <h2 style="text-align:center;margin-bottom:24px;font-size:20px;color:var(--text-primary)">
                    \u{1F510} 管理员登录
                </h2>
                <form onsubmit="return false;" autocomplete="on">
                <div class="admin-form-group">
                    <input id="adminLoginUser" class="admin-input"
                           placeholder="用户名" value="" autocomplete="username">
                </div>
                <div class="admin-form-group">
                    <input id="adminLoginPwd" class="admin-input"
                           type="password" placeholder="密码" value="" autocomplete="current-password">
                </div>
                <button type="submit" id="adminLoginBtn" class="admin-btn admin-btn-primary" style="width:100%;padding:12px">
                    登 录
                </button>
                <p id="adminLoginError" style="color:#dc3545;font-size:13px;text-align:center;margin-top:12px;display:none"></p>
                </form>
            </div>
        `;

        const loginBtn = document.getElementById('adminLoginBtn');

        const handleLogin = async () => {
            const usernameEl = document.getElementById('adminLoginUser');
            const passwordEl = document.getElementById('adminLoginPwd');
            const errorEl = document.getElementById('adminLoginError');

            const username = usernameEl ? usernameEl.value.trim() : '';
            const password = passwordEl ? passwordEl.value.trim() : '';

            if (!username || !password) {
                if (errorEl) {
                    errorEl.style.display = 'block';
                    errorEl.textContent = '请输入用户名和密码';
                }
                return;
            }

            loginBtn.disabled = true;
            loginBtn.textContent = '登录中...';

            try {
                const d = await this._api.adminLogin(username, password);
                const user = d.user || d;
                if (user) {
                    this._adminUser = user;
                    this._renderSidebarUser();
                    this._loadPage('dashboard');
                } else {
                    if (errorEl) {
                        errorEl.style.display = 'block';
                        errorEl.textContent = '用户名或密码错误';
                    }
                }
            } catch (err) {
                if (errorEl) {
                    errorEl.style.display = 'block';
                    errorEl.textContent = '网络错误，请检查后端服务是否启动';
                }
            } finally {
                loginBtn.disabled = false;
                loginBtn.textContent = '登 录';
            }
        };

        loginBtn.addEventListener('click', handleLogin);

        const handleKey = (e) => {
            if (e.key === 'Enter') handleLogin();
        };
        document.getElementById('adminLoginUser')?.addEventListener('keypress', handleKey);
        document.getElementById('adminLoginPwd')?.addEventListener('keypress', handleKey);
    }

    destroy() {
        document.body.removeAttribute('data-admin-active');

        if (this._pageInstance && typeof this._pageInstance.destroy === 'function') {
            try {
                this._pageInstance.destroy();
            } catch (err) {
                console.warn('[AdminShell] destroy 子页面异常:', err);
            }
        }
        this._pageInstance = null;
    }
}

/*
 * Hash路由器
 * 监听hashchange做页面切换，支持 :param 动态参数和 ?query 查询参数
 * 路由按注册顺序匹配，先注册的优先
 */

// 页面标识 → DOM元素ID
const PAGE_ID_MAP = Object.freeze({
    home:      'page-home',
    preview:   'page-preview',
    result:    'page-result',
    search:    'page-search',
    guide:     'page-guide',
    history:   'page-history',
    item:      'page-item',
    map:       'page-map',
    community: 'page-community',
    profile:   'page-profile',
    settings:  'page-settings',
    stats:     'page-stats',
    admin:     'page-admin',
});

const DEFAULT_ROUTE = '/home';
const ROOT_REDIRECT = '/home';

class Router {
    constructor() {
        // Map保证插入顺序，先注册优先匹配
        this._routes = new Map();
        this._currentPath = '';
        this._boundHandler = null;

        // 先注册一套兜底路由，app.js可以clearRoutes()后重新注册
        this._registerBuiltInRoutes();
    }

    // 兜底路由，只做CSS视图切换，不管页面生命周期
    _registerBuiltInRoutes() {
        this.register('/', (params, query) => this._switchPage('home'));
        this.register('/home', (params, query) => this._switchPage('home'));
        this.register('/preview', (params, query) => this._switchPage('preview'));
        this.register('/result', (params, query) => this._switchPage('result'));
        this.register('/search', (params, query) => this._switchPage('search'));
        this.register('/guide', (params, query) => this._switchPage('guide'));
        this.register('/history', (params, query) => this._switchPage('history'));
        this.register('/item/:keyword', (params, query) => this._switchPage('item', { keyword: params.keyword, query }));
        this.register('/map', (params, query) => this._switchPage('map'));
        this.register('/community', (params, query) => this._switchPage('community'));
        this.register('/profile', (params, query) => this._switchPage('profile'));
    }

    // 路径模板转正则，/item/:id → /^\/item\/([^/]+)$/
    _pathToRegex(path) {
        const escaped = path.replace(/[.+^${}()|[\]\\]/g, '\\$&');

        const paramKeys = [];
        const patternStr = escaped.replace(/:(\w+)/g, (_, key) => {
            paramKeys.push(key);
            return '([^/]+)';
        });

        return {
            pattern: new RegExp(`^${patternStr}$`),
            paramKeys
        };
    }

    // 从hash里解析查询参数 #/search?q=塑料瓶&page=1 → {q:'塑料瓶', page:'1'}
    _parseQuery(hash) {
        const queryIndex = hash.indexOf('?');
        if (queryIndex === -1) return {};

        const queryString = hash.slice(queryIndex + 1);
        if (!queryString.trim()) return {};

        const params = {};
        const pairs = queryString.split('&');

        for (const pair of pairs) {
            const eqIndex = pair.indexOf('=');
            if (eqIndex === -1) continue;

            const rawKey = pair.slice(0, eqIndex);
            const rawValue = pair.slice(eqIndex + 1);

            try {
                params[decodeURIComponent(rawKey)] = decodeURIComponent(rawValue);
            } catch (_e) {
                console.warn(`[Router] 查询参数解码失败: ${pair}`);
            }
        }

        return params;
    }

    // 提取纯路径，去掉#和查询串
    _extractPath(hash) {
        let path = hash.replace(/^#/, '');
        const qIndex = path.indexOf('?');
        if (qIndex !== -1) {
            path = path.slice(0, qIndex);
        }
        return path.startsWith('/') ? path : `/${path}`;
    }

    // 切换页面显示，通过CSS active类控制
    _switchPage(pageKey, extraData = {}) {
        const targetId = PAGE_ID_MAP[pageKey];
        if (!targetId) {
            console.warn(`[Router] 未知的页面标识: "${pageKey}"，请检查PAGE_ID_MAP`);
            return;
        }

        // 先把所有.page的active去掉
        const allPages = document.querySelectorAll('.page');
        for (const page of allPages) {
            page.classList.remove('active');
        }

        // 再给目标加上active
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
            targetEl.classList.add('active');
            this._dispatchPageEvent(pageKey, extraData);
        } else {
            // DOM还没挂载，可能懒加载场景，先警告不炸
            console.warn(
                `[Router] 目标页面DOM元素未找到: id="${targetId}"，` +
                `请确保HTML中存在 <div class="page" id="${targetId}">`
            );
        }

        this._currentPath = pageKey;
    }

    // 派发页面切换事件，给埋点、标题更新等外部模块用
    _dispatchPageEvent(pageKey, extraData) {
        const event = new CustomEvent('router:pagechange', {
            bubbles: true,
            detail: {
                page: pageKey,
                path: this._currentPath,
                timestamp: Date.now(),
                ...extraData
            }
        });
        document.dispatchEvent(event);
    }

    // 按注册顺序找第一个匹配的路由
    _matchRoute(path) {
        for (const [pattern, routeInfo] of this._routes) {
            const match = pattern.exec(path);
            if (match) {
                const params = {};
                routeInfo.paramKeys.forEach((key, index) => {
                    params[key] = match[index + 1];
                });

                return {
                    handler: routeInfo.handler,
                    params
                };
            }
        }
        return null;
    }

    // hashchange的核心处理
    _onHashChange() {
        const hash = window.location.hash || `#${ROOT_REDIRECT}`;

        const path = this._extractPath(hash);
        const query = this._parseQuery(hash);

        // #/ 和 # 都跳首页
        const actualPath = (path === '/' || path === '') ? ROOT_REDIRECT : path;

        const matched = this._matchRoute(actualPath);

        if (matched) {
            try {
                matched.handler(matched.params, query);
            } catch (err) {
                console.error(`[Router] 路由处理器执行错误 (path="${actualPath}"):`, err);
            }
        } else {
            // 没匹配到就回首页
            console.warn(`[Router] 未注册的路由: "${actualPath}"，将跳转到首页`);
            this.navigate(ROOT_REDIRECT);
        }
    }

    /* ---- 公共方法 ---- */

    // 注册路由，支持链式调用
    register(path, handler) {
        if (typeof path !== 'string' || !path.trim()) {
            throw new TypeError('[Router] register: path必须是非空字符串');
        }
        if (typeof handler !== 'function') {
            throw new TypeError('[Router] register: handler必须是函数');
        }

        const { pattern, paramKeys } = this._pathToRegex(path);
        this._routes.set(pattern, { handler, paramKeys });

        return this;
    }

    // 清空路由表，app.js接管路由时先调这个
    clearRoutes() {
        this._routes.clear();
        return this;
    }

    // 编程式导航，改hash触发hashchange
    navigate(path) {
        const normalizedPath = path.startsWith('#') ? path : `#${path}`;

        if (window.location.hash !== normalizedPath) {
            window.location.hash = normalizedPath;
        } else {
            // hash没变但需要强制刷新（比如首次加载）
            this._onHashChange();
        }
    }

    start() {
        this._boundHandler = this._onHashChange.bind(this);
        window.addEventListener('hashchange', this._boundHandler);

        // 启动时立即执行一次
        this._onHashChange();

        console.log('[Router] 路由器已启动，已注册', this._routes.size, '条路由规则');
    }

    stop() {
        if (this._boundHandler) {
            window.removeEventListener('hashchange', this._boundHandler);
            this._boundHandler = null;
        }
    }

    getCurrentPath() {
        return this._currentPath;
    }

    getRouteCount() {
        return this._routes.size;
    }
}

export { Router };
export { PAGE_ID_MAP };

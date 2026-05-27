/**
 * @fileoverview Hash路由器模块 - 基于URL hash的前端路由管理
 * @description 实现SPA单页应用的路由分发系统，通过监听hashchange事件
 *              实现页面视图切换，支持路径参数(:id)和查询参数(?q=xxx)。
 *              采用RegExp匹配机制，按注册顺序优先匹配首个命中规则。
 *
 * ## 核心机制
 * - **路由存储**: 使用 Map<RegExp, RouteInfo> 保证插入顺序，实现先注册优先语义
 * - **参数捕获**: 通过 :param 占位符语法，编译为正则捕获组
 * - **视图切换**: CSS类名方案（移除所有.page的active → 添加目标active）
 * - **事件驱动**: hashchange事件触发 → 解析path/query → 匹配路由 → 执行handler
 *
 * ## 生命周期
 * 1. `new Router()` → 构造函数自动注册内置兜底路由
 * 2. `router.clearRoutes()` → 可选：清除内置路由，由app.js接管完整生命周期
 * 3. `router.register(path, handler)` → 注册自定义路由处理器
 * 4. `router.start()` → 绑定hashchange监听，执行首屏渲染
 * 5. `router.navigate(path)` → 编程式导航（或用户点击改变hash）
 * 6. `router.stop()` → 移除监听（卸载/测试清理）
 *
 * @module router
 * @author Frontend Architect
 * @version 1.0.0
 * @see {@link module:store} 状态管理模块（路由切换时同步currentPage）
 */

// ==================== 常量定义 ====================

/**
 * 页面DOM元素ID与路由path的映射关系
 * 每个路由对应一个带有.page类的容器元素，通过切换active类实现显示隐藏
 *
 * @type {Object<string, string>}
 * @constant
 */
const PAGE_ID_MAP = Object.freeze({
    home:      'page-home',       // 首页：拍照上传 + 搜索入口
    preview:   'page-preview',    // 预览确认页：图片裁剪/确认
    result:    'page-result',     // 结果展示页：AI识别结果
    search:    'page-search',     // 搜索结果页：关键词匹配列表
    guide:     'page-guide',      // 分类指南页：四类垃圾说明
    history:   'page-history',    // 历史记录页：过往识别记录
    item:      'page-item',       // 物品详情页：处理步骤+易混淆对比
    map:       'page-map',        // 投放点地图页
    community: 'page-community',  // 社区活动页
    profile:   'page-profile',    // 个人中心页
    settings:  'page-settings',  // 偏好设置页
    stats:     'page-stats',     // 数据统计页
    admin:     'page-admin',     // 管理后台页
});

/** 默认首页路由路径 */
const DEFAULT_ROUTE = '/home';

/** 根路径重定向目标 */
const ROOT_REDIRECT = '/home';

// ==================== Router 类定义 ====================

/**
 * Hash前端路由器 - 管理单页应用的所有页面导航
 *
 * 核心设计：
 * 1. 路由表基于Map<RegExp, Function>存储，支持动态参数捕获
 * 2. 通过hashchange事件驱动视图切换，无需后端路由配合
 * 3. 视图切换采用CSS类名方案：移除所有.page的active，添加目标的active
 * 4. 支持参数化路由（如 /item/:id）和查询字符串解析
 *
 * 匹配优先级：按照register()注册顺序，首个命中的RegExp生效（先注册优先）
 *
 * @example
 * import { Router } from './router.js';
 *
 * const router = new Router();
 *
 * // 注册路由处理器
 * router.register('/home', (params, query) => {
 *     console.log('进入首页', params, query);
 * });
 * router.register('/search', (params, query) => {
 *     console.log('搜索关键词:', query.q);
 * });
 *
 * // 启动路由监听
 * router.start();
 *
 * // 编程式导航
 * router.navigate('/result');
 */
class Router {
    /**
     * 构造函数 - 初始化路由表和内部状态
     *
     * @constructor
     */
    constructor() {
        /**
         * @type {Map<RegExp, {handler: Function, paramKeys: Array<string>}>}
         * 路由表 - 键为正则表达式，值为处理器和参数键名数组
         * 使用Map保证插入顺序，实现先注册优先匹配语义
         */
        this._routes = new Map();

        /** @type {string} 当前激活的路由路径缓存 */
        this._currentPath = '';

        /** @type {Function|null} hashchange事件的绑定引用（用于销毁） */
        this._boundHandler = null;

        /* 注册内置基础路由作为安全兜底 */
        this._registerBuiltInRoutes();
    }

    // ==================== 内置路由注册 ====================

    /**
     * 注册内置基础路由 —— 安全兜底方案
     *
     * 每个路由对应的处理器仅执行 CSS 视图切换（_switchPage），
     * 不包含页面模块懒加载和生命周期管理。
     * 若外部（如 app.js）需要更完整的生命周期控制，
     * 应先调用 clearRoutes() 清除内置路由，再按需重新注册。
     *
     * @private
     * @returns {void}
     */
    _registerBuiltInRoutes() {
        /* 根路径重定向到首页 */
        this.register('/', (params, query) => this._switchPage('home'));

        /* 核心功能页面路由 */
        this.register('/home', (params, query) => this._switchPage('home'));
        this.register('/preview', (params, query) => this._switchPage('preview'));
        this.register('/result', (params, query) => this._switchPage('result'));
        this.register('/search', (params, query) => this._switchPage('search'));
        this.register('/guide', (params, query) => this._switchPage('guide'));
        this.register('/history', (params, query) => this._switchPage('history'));

        /* 动态参数路由：物品详情页 */
        this.register('/item/:keyword', (params, query) => this._switchPage('item', { keyword: params.keyword, query }));

        /* 辅助功能页面路由 */
        this.register('/map', (params, query) => this._switchPage('map'));
        this.register('/community', (params, query) => this._switchPage('community'));
        this.register('/profile', (params, query) => this._switchPage('profile'));
    }

    // ==================== 私有方法 ====================

    /**
     * 将路由路径字符串转换为匹配用正则表达式
     * 支持 :param 风格的动态参数捕获
     *
     * 转换规则：
     * - "/home"          → /^\/home$/
     * - "/item/:id"      → /^\/item\/([^/]+)$/
     * - "/user/:id/post/:postId" → /^\/user\/([^/]+)\/post\/([^/]+)$/
     *
     * @private
     * @param {string} path - 路由路径模板（可含 :param 占位符）
     * @returns {{pattern: RegExp, paramKeys: Array<string>}} 正则和捕获的参数名数组
     *
     * @example
     * const { pattern, paramKeys } = this._pathToRegex('/item/:id');
     * // pattern: /^\/item\/([^/]+)$/
     * // paramKeys: ['id']
     */
    _pathToRegex(path) {
        /* 转义正则特殊字符（排除:和/） */
        const escaped = path.replace(/[.+^${}()|[\]\\]/g, '\\$&');

        /* 将 :param 替换为捕获组 ([^/]+)，并收集参数名 */
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

    /**
     * 解析URL hash中的查询参数为键值对对象
     *
     * 支持格式：
     * - #/search?q=塑料瓶&page=1  → { q:'塑料瓶', page:'1' }
     * - #/home                     → {}
     * - #/search?empty=            → { empty:'' }
     *
     * @private
     * @param {string} hash - 完整的URL hash字符串（含#前缀）
     * @returns {Object<string, string>} 查询参数键值对对象
     *
     * @example
     * this._parseQuery('#/search?q=test&lang=zh')
     * // => { q: 'test', lang: 'zh' }
     */
    _parseQuery(hash) {
        const queryIndex = hash.indexOf('?');
        if (queryIndex === -1) return {};

        /* 截取?后面的部分并进行URL解码 */
        const queryString = hash.slice(queryIndex + 1);
        if (!queryString.trim()) return {};

        const params = {};
        const pairs = queryString.split('&');

        for (const pair of pairs) {
            const eqIndex = pair.indexOf('=');
            if (eqIndex === -1) continue; /* 无=号的键忽略 */

            const rawKey = pair.slice(0, eqIndex);
            const rawValue = pair.slice(eqIndex + 1);

            try {
                params[decodeURIComponent(rawKey)] = decodeURIComponent(rawValue);
            } catch (_e) {
                /* URL解码失败时跳过该参数 */
                console.warn(`[Router] 查询参数解码失败: ${pair}`);
            }
        }

        return params;
    }

    /**
     * 从完整hash中提取纯路径部分（去掉#前缀和查询字符串）
     *
     * 解析流程：
     * 1. 移除开头的 '#' 字符
     * 2. 定位 '?' 分隔符，截取其左侧部分（排除查询参数）
     * 3. 规范化结果：确保以 '/' 开头（处理空hash或无前缀情况）
     *
     * @private
     * @param {string} hash - 完整hash如 '#/home?q=x' 或 '#/item/123'
     * @returns {string} 纯路径如 '/home' 或 '/item/123'，始终以 '/' 开头
     *
     * @example
     * this._extractPath('#/home')           // '/home'
     * this._extractPath('#/search?q=塑料瓶') // '/search'
     * this._extractPath('#')                // '/'
     * this._extractPath('')                 // '/'
     */
    _extractPath(hash) {
        /* 步骤1：移除#号前缀 */
        let path = hash.replace(/^#/, '');
        /* 步骤2：移除查询字符串部分（?及之后的所有内容） */
        const qIndex = path.indexOf('?');
        if (qIndex !== -1) {
            path = path.slice(0, qIndex);
        }
        /* 步骤3：确保规范化路径始终以/开头，防止空字符串导致匹配异常 */
        return path.startsWith('/') ? path : `/${path}`;
    }

    /**
     * 执行视图切换 - 核心渲染逻辑
     *
     * 采用CSS类名方案实现SPA页面切换，无需重新加载页面。
     * 切换流程：
     * 1. 通过 PAGE_ID_MAP 查找目标页面对应的DOM元素ID
     * 2. 遍历所有 .page 元素，移除其 active 类（隐藏当前可见页面）
     * 3. 为目标页面的DOM元素添加 active 类（显示新页面）
     * 4. 触发自定义 DOM 事件 'router:pagechange'，允许其他模块响应
     *
     * 容错设计：
     * - 目标 pageKey 未在 PAGE_ID_MAP 中注册时输出警告并提前返回
     * - 目标DOM元素尚未挂载（懒加载场景）时输出警告但不抛异常
     *
     * @private
     * @param {string} pageKey - 目标页面标识（对应PAGE_ID_MAP的key），如 'home'、'result'
     * @param {Object} [extraData={}] - 额外数据传递给页面事件（如搜索关键词、路由参数）
     * @returns {void}
     *
     * @example
     * // 基础用法：切换到首页
     * this._switchPage('home');
     *
     * // 带额外数据：切换到物品详情页并传递关键词
     * this._switchPage('item', { keyword: '塑料瓶', query: {} });
     */
    _switchPage(pageKey, extraData = {}) {
        /* 步骤1：通过映射表获取目标页面的DOM ID */
        const targetId = PAGE_ID_MAP[pageKey];
        if (!targetId) {
            console.warn(`[Router] 未知的页面标识: "${pageKey}"，请检查PAGE_ID_MAP`);
            return;
        }

        /* 步骤2：查找DOM中所有.page容器元素 */
        const allPages = document.querySelectorAll('.page');

        /* 步骤3：批量移除所有页面的active状态（CSS display:none） */
        for (const page of allPages) {
            page.classList.remove('active');
        }

        /* 步骤4：激活目标页面（CSS display:block） */
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
            targetEl.classList.add('active');

            /* 步骤5：派发自定义事件，允许统计埋点、标题更新等外部模块响应 */
            this._dispatchPageEvent(pageKey, extraData);
        } else {
            /* 目标DOM尚未挂载时仅警告，不抛异常（可能为懒加载/动态渲染场景） */
            console.warn(
                `[Router] 目标页面DOM元素未找到: id="${targetId}"，` +
                `请确保HTML中存在 <div class="page" id="${targetId}">`
            );
        }

        /* 更新内部路径缓存，供getCurrentPath()查询 */
        this._currentPath = pageKey;
    }

    /**
     * 派发页面切换的自定义DOM事件
     *
     * 使用 CustomEvent API 在 document 上派发 'router:pagechange' 事件，
     * 其他模块可通过 addEventListener('router:pagechange', handler) 做出响应，
     * 典型用途包括：页面标题更新、统计埋点上报、权限校验等。
     *
     * 事件对象结构（event.detail）：
     * - page: string - 新页面标识
     * - path: string - 当前路由路径缓存
     * - timestamp: number - 切换发生的时间戳（Date.now()）
     * - ...extraData - 调用方传入的额外数据（如搜索关键词）
     *
     * @private
     * @param {string} pageKey - 新页面标识（如 'home'、'item'）
     * @param {Object} extraData - 附带数据，会合并到 event.detail 中
     * @returns {void}
     *
     * @example
     * // 外部模块监听示例：
     * document.addEventListener('router:pagechange', (e) => {
     *     console.log(`页面切换到: ${e.detail.page}`, e.detail);
     * });
     */
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

    /**
     * 在路由表中查找第一个匹配当前路径的处理规则
     * 遍历顺序即注册顺序（Map保证），实现优先级控制
     *
     * @private
     * @param {string} path - 待匹配的纯路径（不含#和查询串）
     * @returns {{ handler: Function, params: Object } | null} 匹配结果；无匹配返回null
     */
    _matchRoute(path) {
        for (const [pattern, routeInfo] of this._routes) {
            const match = pattern.exec(path);
            if (match) {
                /* 提取捕获组的值并与参数名配对 */
                const params = {};
                routeInfo.paramKeys.forEach((key, index) => {
                    params[key] = match[index + 1]; /* index 0是完整匹配 */
                });

                return {
                    handler: routeInfo.handler,
                    params
                };
            }
        }
        return null; /* 无任何路由匹配 */
    }

    /**
     * hashchange事件处理器 - 路由系统的核心调度函数
     *
     * 由 window.addEventListener('hashchange', ...) 触发，
     * 也被 start() 首次调用和 navigate() 强制刷新时直接调用。
     *
     * 处理流程（管道模式）：
     * 1. **读取**: 获取当前 window.location.hash，空hash时使用默认重定向路径
     * 2. **解析**: 调用 _extractPath() 提取纯路径 + _parseQuery() 提取查询参数
     * 3. **规范化**: 根路径 '/' 或空字符串统一重定向到 DEFAULT_ROUTE
     * 4. **匹配**: 遍历路由表（Map有序遍历），用 RegExp.exec() 查找首个命中规则
     * 5. **派发**: 匹配成功则调用 handler(params, query)；失败则回退到默认首页
     *
     * 错误处理：
     * - handler 执行异常时捕获并输出 console.error，不阻断后续路由
     * - 无匹配路由时输出警告并自动 navigate 到 ROOT_REDIRECT
     *
     * @private
     * @returns {void}
     */
    _onHashChange() {
        /* 步骤1：获取当前hash，空hash时回退到根重定向目标 */
        const hash = window.location.hash || `#${ROOT_REDIRECT}`;

        /* 步骤2：分别提取路径和查询参数 */
        const path = this._extractPath(hash);
        const query = this._parseQuery(hash);

        /* 步骤3：根路径特殊处理 —— #/ 和 # 统一重定向到默认首页 */
        const actualPath = (path === '/' || path === '') ? ROOT_REDIRECT : path;

        /* 步骤4：在路由表中按注册顺序查找第一个匹配项（先注册优先） */
        const matched = this._matchRoute(actualPath);

        if (matched) {
            try {
                /* 步骤5a：匹配成功 → 调用路由处理器，传入路径参数和查询参数对象 */
                matched.handler(matched.params, query);
            } catch (err) {
                /* 单个路由处理器异常不应影响整个路由系统运行 */
                console.error(`[Router] 路由处理器执行错误 (path="${actualPath}"):`, err);
            }
        } else {
            /* 步骤5b：无任何路由匹配 → 回退到404处理（当前策略为跳转首页） */
            console.warn(`[Router] 未注册的路由: "${actualPath}"，将跳转到首页`);
            this.navigate(ROOT_REDIRECT);
        }
    }

    // ==================== 公共API ====================

    /**
     * 注册一条路由规则
     *
     * 将路径模板和对应的处理函数关联存入路由表。
     * 支持两种路径格式：
     * - 静态路径：'/home'、'/result'
     * - 参数路径：'/item/:id'、'/archive/:year/:month'
     *
     * @public
     * @param {string} path - 路径模板（不含#前缀）
     * @param {Function} handler - 路由处理器，签名：(params, query) => void
     *   @param {Object} handler.params - 路径参数对象（来自 :param 捕获）
     *   @param {Object} handler.query - 查询参数对象（来自 ?key=value）
     * @returns {this} 支持链式调用
     *
     * @throws {TypeError} 当 path 不是非空字符串时抛出
     * @throws {TypeError} 当 handler 不是函数时抛出
     *
     * @example
     * // 静态路由
     * router.register('/about', (params, query) => {
     *     renderAboutPage();
     * });
     *
     * // 动态参数路由
     * router.register('/detail/:id', (params, query) => {
     *     loadDetail(params.id);  // params.id 来自URL中的实际值
     * });
     *
     * // 链式注册
     * router
     *     .register('/home', renderHome)
     *     .register('/about', renderAbout)
     *     .register('/contact', renderContact);
     */
    register(path, handler) {
        if (typeof path !== 'string' || !path.trim()) {
            throw new TypeError('[Router] register: path必须是非空字符串');
        }
        if (typeof handler !== 'function') {
            throw new TypeError('[Router] register: handler必须是函数');
        }

        /* 将路径转为正则表达式和参数键数组 */
        const { pattern, paramKeys } = this._pathToRegex(path);

        /* 存入路由表 */
        this._routes.set(pattern, { handler, paramKeys });

        /* 支持链式调用 */
        return this;
    }

    /**
     * 清空路由表 —— 移除所有已注册的路由规则
     *
     * 典型使用场景：外部（如 app.js）需要接管路由控制权时，
     * 先清除构造函数自动注册的内置路由，再按需重新注册
     * 具有完整生命周期管理的处理函数。
     *
     * @public
     * @returns {this} 支持链式调用
     *
     * @example
     * router.clearRoutes()
     *       .register('/home', myHandler)
     *       .register('/search', myHandler);
     */
    clearRoutes() {
        this._routes.clear();
        return this;
    }

    /**
     * 编程式导航到指定路由
     *
     * 更新浏览器地址栏的hash，触发hashchange事件，
     * 进而调用_onHashChange完成视图切换。
     * 也可直接用于初始化时的首屏渲染。
     *
     * @public
     * @param {string} path - 目标路径（不含#前缀），如 '/home'、'/search?q=xxx'
     * @returns {void}
     *
     * @throws 该方法本身不抛异常，但触发的路由处理器可能抛出异常（由_onHashChange捕获）
     *
     * @example
     * // 基础导航
     * router.navigate('/result');
     *
     * // 带查询参数的导航
     * router.navigate('/search?q=塑料瓶');
     *
     * // 应用启动时根据当前hash初始化首屏
     * router.navigate(window.location.hash.slice(1) || '/home');
     */
    navigate(path) {
        /* 规范化路径：确保以#开头 */
        const normalizedPath = path.startsWith('#') ? path : `#${path}`;

        /* 仅当hash确实发生变化时才更新，避免冗余触发 */
        if (window.location.hash !== normalizedPath) {
            window.location.hash = normalizedPath;
        } else {
            /* hash未变但需要强制刷新（如首次加载） */
            this._onHashChange();
        }
    }

    /**
     * 启动路由器 - 开始监听hashchange事件
     * 必须在DOM就绪后调用（通常放在app.js的启动流程中）
     *
     * @public
     * @returns {void}
     *
     * @throws 该方法本身不抛异常，但首次执行 _onHashChange() 时可能因路由处理器异常输出错误日志
     *
     * @example
     * // 在app.js中调用
     * const router = new Router();
     * router.start(); // 开始监听
     */
    start() {
        /* 绑定this上下文后保存引用，便于后续removeEventListener */
        this._boundHandler = this._onHashChange.bind(this);
        window.addEventListener('hashchange', this._boundHandler);

        /* 启动时立即执行一次，处理初始hash */
        this._onHashChange();

        console.log('[Router] 路由器已启动，已注册', this._routes.size, '条路由规则');
    }

    /**
     * 停止路由器 - 移除hashchange事件监听
     * 用于应用卸载或单元测试清理场景
     *
     * @public
     * @returns {void}
     *
     * @throws 该方法不会抛异常；若路由器未启动（_boundHandler为null），则静默跳过
     */
    stop() {
        if (this._boundHandler) {
            window.removeEventListener('hashchange', this._boundHandler);
            this._boundHandler = null;
        }
    }

    /**
     * 获取当前激活的路由路径
     *
     * @public
     * @returns {string} 当前路径标识（如 'home'、'result'）
     */
    getCurrentPath() {
        return this._currentPath;
    }

    /**
     * 获取已注册的路由数量（调试用途）
     *
     * @public
     * @returns {number} 路由表中规则总数
     */
    getRouteCount() {
        return this._routes.size;
    }
}

// ==================== 模块导出 ====================

/** 导出Router类供实例化和使用 */
export { Router };

/** 导出页面映射常量，方便外部扩展自定义页面 */
export { PAGE_ID_MAP };

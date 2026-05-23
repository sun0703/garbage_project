/**
 * @fileoverview Hash路由器模块 - 基于URL hash的前端路由管理
 * @description 实现SPA单页应用的路由分发系统，通过监听hashchange事件
 *              实现页面视图切换，支持路径参数(:id)和查询参数(?q=xxx)。
 *              采用RegExp匹配机制，按注册顺序优先匹配首个命中规则。
 * @module router
 * @author Frontend Architect
 * @version 1.0.0
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
    home:     'page-home',       // 首页：拍照上传 + 搜索入口
    preview:  'page-preview',    // 预览确认页：图片裁剪/确认
    result:   'page-result',     // 结果展示页：AI识别结果
    search:   'page-search',     // 搜索结果页：关键词匹配列表
    guide:    'page-guide',      // 分类指南页：四类垃圾说明
    history:  'page-history'     // 历史记录页：过往识别记录
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

        /* 路由由 app.js 统一注册，此处不再预注册 */
    }

    // ==================== 私有方法 ====================

    /**
     * 注册内置路由表 - 应用启动时自动调用
     * 定义校园垃圾分类SPA的全部6个页面路由及对应处理逻辑
     *
     * @private
     * @returns {void}
     */
    _registerBuiltInRoutes() {
        /*
         * 首页路由：#/ 或 #/home
         * 应用的主入口，包含拍照上传、搜索框等核心交互组件
         */
        this.register('/', () => this._switchPage('home'));
        this.register('/home', () => this._switchPage('home'));

        /*
         * 预览确认页：#/preview
         * 用户选择图片后进入此页进行确认/裁剪后再提交识别
         */
        this.register('/preview', () => this._switchPage('preview'));

        /*
         * 结果展示页：#/result
         * AI模型返回识别结果后的展示页面，含分类标签、置信度、投放指引
         */
        this.register('/result', () => this._switchPage('result'));

        /*
         * 搜索结果页：#/search?q=xxx
         * 关键词搜索的结果列表展示，支持查询参数传递搜索词
         */
        this.register('/search', (params, query) => {
            /* 将查询参数中的q值透传给页面处理器 */
            this._switchPage('search', { query: query.q || '' });
        });

        /*
         * 分类指南页：#/guide
         * 展示四类垃圾分类的标准说明、常见物品列表、投放注意事项
         */
        this.register('/guide', () => this._switchPage('guide'));

        /*
         * 历史记录页：#/history
         * 展示用户过往的识别历史，支持重新查看和删除操作
         */
        this.register('/history', () => this._switchPage('history'));
    }

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
     * @private
     * @param {string} hash - 完整hash如 '#/home?q=x'
     * @returns {string} 纯路径如 '/home'
     */
    _extractPath(hash) {
        /* 移除#号前缀 */
        let path = hash.replace(/^#/, '');
        /* 移除查询字符串部分 */
        const qIndex = path.indexOf('?');
        if (qIndex !== -1) {
            path = path.slice(0, qIndex);
        }
        /* 确保以/开头 */
        return path.startsWith('/') ? path : `/${path}`;
    }

    /**
     * 执行视图切换 - 核心渲染逻辑
     *
     * 切换流程：
     * 1. 查找DOM中所有 .page 元素
     * 2. 全部移除 active 类（隐藏当前页）
     * 3. 为目标页面的 .page 元素添加 active 类（显示新页面）
     * 4. 若目标页面不存在则给出警告但不阻断执行
     *
     * @private
     * @param {string} pageKey - 目标页面标识（对应PAGE_ID_MAP的key）
     * @param {Object} [extraData={}] - 额外数据传递给页面（如搜索关键词）
     * @returns {void}
     */
    _switchPage(pageKey, extraData = {}) {
        /* 获取目标页面的DOM ID */
        const targetId = PAGE_ID_MAP[pageKey];
        if (!targetId) {
            console.warn(`[Router] 未知的页面标识: "${pageKey}"，请检查PAGE_ID_MAP`);
            return;
        }

        /* 查找所有页面容器 */
        const allPages = document.querySelectorAll('.page');

        /* 第一步：移除所有页面的active状态 */
        for (const page of allPages) {
            page.classList.remove('active');
        }

        /* 第二步：激活目标页面 */
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
            targetEl.classList.add('active');

            /* 触发自定义事件，允许其他模块响应页面切换 */
            this._dispatchPageEvent(pageKey, extraData);
        } else {
            /* 目标DOM尚未挂载时仅警告，不抛异常（可能懒加载场景） */
            console.warn(
                `[Router] 目标页面DOM元素未找到: id="${targetId}"，` +
                `请确保HTML中存在 <div class="page" id="${targetId}">`
            );
        }

        /* 更新当前路径缓存 */
        this._currentPath = pageKey;
    }

    /**
     * 派发页面切换的自定义DOM事件
     * 其他模块可通过监听 'router:pagechange' 事件做出响应
     *
     * @private
     * @param {string} pageKey - 新页面标识
     * @param {Object} extraData - 附带数据
     * @returns {void}
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
     * hashchange事件处理器 - 由addEventListener触发
     * 解析新的hash并分派给对应的路由处理器
     *
     * @private
     * @returns {void}
     */
    _onHashChange() {
        const hash = window.location.hash || `#${ROOT_REDIRECT}`;
        const path = this._extractPath(hash);
        const query = this._parseQuery(hash);

        /* 根路径特殊处理：#/ 和 # 重定向到默认首页 */
        const actualPath = (path === '/' || path === '') ? ROOT_REDIRECT : path;

        /* 在路由表中查找匹配项 */
        const matched = this._matchRoute(actualPath);

        if (matched) {
            try {
                /* 调用路由处理器，传入路径参数和查询参数 */
                matched.handler(matched.params, query);
            } catch (err) {
                console.error(`[Router] 路由处理器执行错误 (path="${actualPath}"):`, err);
            }
        } else {
            /* 未匹配任何路由：回退到404处理或默认首页 */
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

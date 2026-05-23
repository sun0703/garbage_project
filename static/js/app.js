/**
 * @fileoverview 应用主入口模块 - SPA启动引导与全局初始化
 * @description 校园垃圾分类单页应用的顶层入口文件，负责：
 *              1. 实例化核心模块（Router / Store / ApiClient）
 *              2. 绑定全局错误捕获与降级处理
 *              3. 渲染全局UI组件（导航栏/标签栏）
 *              4. 注册路由规则并管理页面生命周期
 *              5. 启动首屏路由渲染
 *              6. 暴露全局调试接口
 *
 * 加载方式：在HTML中通过 <script type="module" src="/static/js/app.js"></script> 引入
 * @module app
 * @version 1.1.0
 */

// ==================== 模块依赖导入 ====================

import { Router } from './router.js';
import { store, Store, DEFAULT_STATE } from './store.js';
import { api, ApiClient, ApiError } from './api.js';

/*
 * 全局UI组件导入（安全加载模式）
 * 组件使用实例方法模式：new Component().render(selector)
 */
let NavBarClass = null;
let TabBarClass = null;

try {
    const mod = await import('./components/nav-bar.js');
    NavBarClass = mod.NavBar || mod.default;
} catch (_e) {
    console.info('[App] NavBar组件未找到，跳过导航栏渲染');
}

try {
    const mod = await import('./components/tab-bar.js');
    TabBarClass = mod.TabBar || mod.default;
} catch (_e) {
    console.info('[App] TabBar组件未找到，跳过标签栏渲染');
}

/*
 * 页面模块导入（懒加载，按需实例化）
 * 每个页面类必须实现 init() 和 destroy() 生命周期方法
 */
const PageModules = {};

async function loadPage(name, path) {
    if (PageModules[name]) return PageModules[name];
    try {
        const mod = await import(path);
        PageModules[name] = mod.default || Object.values(mod)[0];
        return PageModules[name];
    } catch (e) {
        console.error(`[App] 页面模块加载失败: ${name}`, e);
        return null;
    }
}

// ==================== 应用配置 ====================

const APP_CONFIG = Object.freeze({
    apiBaseURL: '',
    showErrorAlert: true,
    logLevel: 'info',
    exposeDebugAPI: true,
    appName: '校园垃圾分类AI助手'
});

// ==================== 全局实例创建 ====================

api.baseURL = APP_CONFIG.apiBaseURL;
const router = new Router();

/**
 * 当前活跃的页面实例（用于调用destroy()生命周期）
 * @type {Object|null}
 */
let activePageInstance = null;

// ==================== 全局错误处理 ====================

function handleGlobalError(event) {
    event.preventDefault();
    const errorMsg = event.message || '发生未知错误';
    store.setState('error', errorMsg);
    store.setState('isLoading', false);
    if (APP_CONFIG.logLevel !== 'silent') {
        console.error(`[${APP_CONFIG.appName}] 全局错误:`, errorMsg);
        console.error(event.error);
    }
}

function handleUnhandledRejection(event) {
    event.preventDefault();
    const reason = event.reason;
    if (reason instanceof ApiError) {
        store.setState('error', `[${reason.code}] ${reason.message}`);
    } else if (reason instanceof Error) {
        store.setState('error', reason.message);
    } else {
        store.setState('error', String(reason) || '操作失败，请重试');
    }
    store.setState('isLoading', false);
}

// ==================== UI组件渲染 ====================

/** 导航栏组件实例 @type {Object|null} */
let navBarInstance = null;

/** 标签栏组件实例 @type {Object|null} */
let tabBarInstance = null;

function initGlobalComponents() {
    /* 导航栏：使用实例化模式 new NavBar(options).render('#navBar') */
    if (NavBarClass) {
        try {
            navBarInstance = new NavBarClass({ title: APP_CONFIG.appName });
            navBarInstance.render('#navBar');
            if (APP_CONFIG.logLevel !== 'silent') {
                console.info('[App] 导航栏已渲染 -> #navBar');
            }
        } catch (err) {
            console.error('[App] 导航栏渲染失败:', err);
        }
    }

    /* 标签栏：使用实例化模式 new TabBar(options).render('#tabBar') */
    if (TabBarClass) {
        try {
            tabBarInstance = new TabBarClass({ activeIndex: 0 });
            tabBarInstance.render('#tabBar');
            if (APP_CONFIG.logLevel !== 'silent') {
                console.info('[App] 标签栏已渲染 -> #tabBar');
            }
        } catch (err) {
            console.error('[App] 标签栏渲染失败:', err);
        }
    }
}

// ==================== 路由注册与页面生命周期管理 ====================

/**
 * 创建页面路由处理器工厂函数
 * 负责管理页面的 init/destroy 生命周期，
 * 确保每次切换页面时正确清理旧页面并初始化新页面
 *
 * @param {string} pageName - 页面名称标识
 * @param {string} modulePath - 页面模块的导入路径
 * @returns {Function} 路由处理器函数，签名 (params, query) => void
 */
function createPageHandler(pageName, modulePath) {
    return async function handlePageEnter(params, query) {
        /* 销毁当前活跃页面（调用destroy()释放事件监听和资源） */
        if (activePageInstance && typeof activePageInstance.destroy === 'function') {
            try {
                activePageInstance.destroy();
            } catch (e) {
                console.warn(`[App] 页面销毁异常 (${store.getState('currentPage')}):`, e);
            }
            activePageInstance = null;
        }

        /* 更新Store中的当前页面状态 */
        store.setState('currentPage', pageName);

        /* 切换CSS可见性：还原所有.page → 激活目标页 */
        document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
        const pageEl = document.getElementById(`page-${pageName}`);
        if (pageEl) pageEl.classList.add('active');

        /* 动态导入并实例化目标页面 */
        const PageClass = await loadPage(pageName, modulePath);
        if (!PageClass) {
            console.error(`[App] 页面模块不存在: ${pageName}`);
            return;
        }

        /* 创建页面实例并调用初始化 */
        try {
            activePageInstance = new PageClass({ store, api, router, params, query });

            if (typeof activePageInstance.init === 'function') {
                activePageInstance.init();
            }

            if (APP_CONFIG.logLevel === 'debug') {
                console.log(`[App] 页面已切换: ${pageName}`, { params, query });
            }
        } catch (e) {
            console.error(`[App] 页面初始化失败 (${pageName}):`, e);
            store.setState('error', `页面加载失败: ${e.message}`);
        }

        /* 同步TabBar激活状态 */
        if (tabBarInstance && typeof tabBarInstance.setActiveTab === 'function') {
            const tabIndex = { home: 0, search: 1, guide: 2, history: 3 }[pageName];
            if (tabIndex !== undefined) {
                tabBarInstance.setActiveTab(tabIndex);
            }
        }
    };
}

/**
 * 注册全部应用路由规则
 * 每条路由绑定一个页面处理器，负责对应页面的完整生命周期
 *
 * @param {Router} router - 路由器实例
 * @returns {void}
 */
function registerAllRoutes(router) {
    router
        /* 首页：拍照上传 + 搜索入口 */
        .register('/home', createPageHandler('home', './pages/home.js'))
        .register('/', createPageHandler('home', './pages/home.js'))

        /* 预览确认页：图片预览 + 开始识别 */
        .register('/preview', createPageHandler('preview', './pages/camera.js'))

        /* 结果展示页：AI识别结果卡片 */
        .register('/result', createPageHandler('result', './pages/result.js'))

        /* 搜索结果页：关键词模糊搜索列表 */
        .register('/search', createPageHandler('search', './pages/search.js'))

        /* 分类指南页：四类垃圾标准说明 */
        .register('/guide', createPageHandler('guide', './pages/guide.js'))

        /* 历史记录页：过往识别记录列表 */
        .register('/history', createPageHandler('history', './pages/history.js'));

    if (APP_CONFIG.logLevel !== 'silent') {
        console.log(`[App] 已注册 ${router.getRouteCount()} 条路由规则`);
    }
}

// ==================== 应用启动入口 ====================

function bootstrap() {
    /* 第一步：绑定全局错误捕获 */
    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    /* 第二步：渲染全局UI组件（NavBar / TabBar）*/
    initGlobalComponents();

    /* 第三步：注册所有路由规则（含页面生命周期管理） */
    registerAllRoutes(router);

    /* 第四步：启动路由系统（触发首屏渲染） */
    router.start();

    /* 第五步：暴露全局调试接口 */
    if (APP_CONFIG.exposeDebugAPI) {
        window.__app__ = Object.freeze({
            router,
            store,
            api,
            config: APP_CONFIG,
            navigate: (path) => router.navigate(path),
            get activePage() { return activePageInstance; }
        });

        if (APP_CONFIG.logLevel !== 'silent') {
            console.info(
                `%c[${APP_CONFIG.appName}] 应用已启动 %c调试接口: window.__app__`,
                'color:#2D9B5E;font-weight:bold;',
                'color:#666;'
            );
        }
    }

    /* 第六步：标记应用就绪 */
    document.documentElement.classList.add('app-ready');

    if (APP_CONFIG.logLevel !== 'silent') {
        console.info(`[App] ${APP_CONFIG.appName} 初始化完成 (v1.1.0)`);
    }
}

/* ES Module 自动执行启动 */
bootstrap();

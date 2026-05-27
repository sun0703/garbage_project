// 应用主入口 - SPA启动引导

import { Router } from './router.js';
import { store, Store, DEFAULT_STATE } from './store.js';
import { api, ApiClient, ApiError } from './api.js';
import { config } from './config.js';
import { initTheme } from './pages/settings.js';

/*
 * 全局UI组件（安全加载，找不到就跳过）
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

// 页面模块懒加载缓存
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

// 从config.js集中拿配置，方便多环境切换
const APP_CONFIG = Object.freeze({
    apiBaseURL: config.api.baseURL,
    showErrorAlert: config.debug.showErrorAlert,
    logLevel: config.debug.logLevel,
    exposeDebugAPI: config.debug.exposeDebugAPI,
    appName: config.app.name,
});

api.baseURL = APP_CONFIG.apiBaseURL;
const router = new Router();

// 当前活跃的页面实例，切换时调destroy()
let activePageInstance = null;

// 全局错误捕获
function catchGlobalError(event) {
    event.preventDefault();
    const errorMsg = event.message || '发生未知错误';
    store.setState('error', errorMsg);
    store.setState('isLoading', false);
    if (APP_CONFIG.logLevel !== 'silent') {
        console.error(`[${APP_CONFIG.appName}] 全局错误:`, errorMsg);
        console.error(event.error);
    }
}

function catchRejection(event) {
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

let navBarInstance = null;
let tabBarInstance = null;

function initGlobalComponents() {
    if (NavBarClass) {
        try {
            navBarInstance = new NavBarClass({ container: '#navBar', title: APP_CONFIG.appName });
            navBarInstance.init();
            if (APP_CONFIG.logLevel !== 'silent') {
                console.info('[App] 导航栏已渲染 -> #navBar');
            }
        } catch (err) {
            console.error('[App] 导航栏渲染失败:', err);
        }
    }

    if (TabBarClass) {
        try {
            tabBarInstance = new TabBarClass({ container: '#tabBar', activeIndex: 0 });
            tabBarInstance.init();
            if (APP_CONFIG.logLevel !== 'silent') {
                console.info('[App] 标签栏已渲染 -> #tabBar');
            }
        } catch (err) {
            console.error('[App] 标签栏渲染失败:', err);
        }
    }
}

// 页面路由处理器工厂，管理init/destroy生命周期
function createPageHandler(pageName, modulePath) {
    return async function enterPage(params, query) {
        // 先销毁旧页面
        if (activePageInstance && typeof activePageInstance.destroy === 'function') {
            try {
                activePageInstance.destroy();
            } catch (e) {
                console.warn(`[App] 页面销毁异常 (${store.getState('currentPage')}):`, e);
            }
            activePageInstance = null;
        }

        store.setState('currentPage', pageName);

        // CSS切换页面可见性
        document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
        const pageEl = document.getElementById(`page-${pageName}`);
        if (pageEl) pageEl.classList.add('active');

        // 动态导入并实例化目标页面
        const PageClass = await loadPage(pageName, modulePath);
        if (!PageClass) {
            console.error(`[App] 页面模块不存在: ${pageName}`);
            return;
        }

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

        // 同步TabBar高亮
        if (tabBarInstance && typeof tabBarInstance.setActiveTab === 'function') {
            const tabIndex = config.tabIndexMap[pageName];
            if (tabIndex !== undefined) {
                tabBarInstance.setActiveTab(tabIndex);
            }
        }
    };
}

// 注册所有路由，每条路由绑一个页面处理器
function registerAllRoutes(router) {
    router
        .clearRoutes()
        .register('/home', createPageHandler('home', './pages/home.js'))
        .register('/', createPageHandler('home', './pages/home.js'))
        .register('/preview', createPageHandler('preview', './pages/camera.js'))
        .register('/result', createPageHandler('result', './pages/result.js'))
        .register('/search', createPageHandler('search', './pages/search.js'))
        .register('/guide', createPageHandler('guide', './pages/guide.js'))
        .register('/history', createPageHandler('history', './pages/history.js'))
        .register('/item/:keyword', createPageHandler('item', './pages/item-detail.js'))
        .register('/map', createPageHandler('map', './pages/map.js'))
        .register('/community', createPageHandler('community', './pages/community.js'))
        .register('/profile', createPageHandler('profile', './pages/profile.js'))
        .register('/settings', createPageHandler('settings', './pages/settings.js'))
        .register('/stats', createPageHandler('stats', './pages/stats.js'))
        .register('/admin', createPageHandler('admin', './pages/admin-shell.js'));

    if (APP_CONFIG.logLevel !== 'silent') {
        console.log(`[App] 已注册 ${router.getRouteCount()} 条路由规则`);
    }
}

function bootstrap() {
    // 防止热重载或脚本重复加载导致双重初始化
    if (window.__APP_BOOTSTRAPPED__) {
        console.warn('[App] 检测到重复初始化请求，已跳过');
        return;
    }
    window.__APP_BOOTSTRAPPED__ = true;

    // 尽早初始化主题，避免闪烁
    initTheme();

    window.addEventListener('error', catchGlobalError);
    window.addEventListener('unhandledrejection', catchRejection);

    initGlobalComponents();
    registerAllRoutes(router);
    router.start();

    // 暴露调试接口，上线前记得关
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

    document.documentElement.classList.add('app-ready');

    if (APP_CONFIG.logLevel !== 'silent') {
        console.info(`[App] ${APP_CONFIG.appName} 初始化完成 (v${config.app.version})`);
    }
}

bootstrap();

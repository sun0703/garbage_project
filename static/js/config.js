/*
 * 全局配置
 * 所有可调参数集中在这，改环境不用到处翻代码
 */

export const config = {
    // 后端接口相关
    api: {
        baseURL: '',
        timeout: 10000,
        retryTimes: 3,
    },

    app: {
        name: '垃圾分类助手',
        version: '1.0.0',
        defaultMode: 'quick',
        maxHistoryCount: 50, // 超过这个数就裁掉旧的
    },

    // 界面交互参数
    ui: {
        toastDuration: 2500,
        loadingDelay: 500, // 太快闪一下反而难受，延迟500ms再显示loading
        animationDuration: 300,
    },

    storage: {
        prefix: 'ecosort',
        maxSize: 4 * 1024 * 1024, // 4MB，别存太大
    },

    router: {
        defaultRoute: '#/home',
        notFoundRoute: '#/home', // 找不到路由就回首页
    },

    debug: {
        showErrorAlert: true,
        logLevel: 'info',
        exposeDebugAPI: true, // 上线前记得关掉
    },

    // 页面名 → TabBar索引的映射，切换页面时同步高亮用
    tabIndexMap: {
        home: 0,
        search: 1,
        map: 2,
        community: 3,
        profile: 4,
    },
};

export default config;

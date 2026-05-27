/**
 * 应用全局配置 - 集中管理所有可配置项，便于多环境部署和调优
 *
 * @fileoverview 配置中心模块 - 统一管理应用运行时参数
 * @description 将散落在各模块中的硬编码值（API地址、超时时间、默认配置、魔法数字等）
 *              集中到单一配置对象中，实现：
 *              1. 多环境切换（开发/测试/生产）仅需修改此文件
 *              2. 运行时调优（超时、重试次数等）有统一入口
 *              3. 消除魔法数字，提升代码可读性
 * @module config
 * @version 1.0.0
 */

export const config = {
    /**
     * API通信相关配置
     * @type {Object}
     * @property {string} baseURL - API基础路径前缀（同源部署时留空）
     * @property {number} timeout - 默认请求超时时间（毫秒）
     * @property {number} retryTimes - 失败自动重试次数
     */
    api: {
        baseURL: '',
        timeout: 10000,
        retryTimes: 3,
    },

    /**
     * 应用基础信息与行为配置
     * @type {Object}
     * @property {string} name - 应用显示名称（用于导航栏标题等）
     * @property {string} version - 当前应用版本号
     * @property {string} defaultMode - 默认操作模式（quick/camera/manual）
     * @property {number} maxHistoryCount - 历史记录最大保存条数
     */
    app: {
        name: '校园垃圾分类助手',
        version: '1.0.0',
        defaultMode: 'quick',
        maxHistoryCount: 50,
    },

    /**
     * UI交互相关配置
     * @type {Object}
     * @property {number} toastDuration - Toast提示自动消失时间（毫秒）
     * @property {number} loadingDelay - Loading动画延迟显示时间（毫秒），防止闪烁
     * @property {number} animationDuration - CSS过渡动画时长（毫秒）
     */
    ui: {
        toastDuration: 2500,
        loadingDelay: 500,
        animationDuration: 300,
    },

    /**
     * 本地存储相关配置
     * @type {Object}
     * @property {string} prefix - localStorage键名前缀，避免命名冲突
     * @property {number} maxSize - 单条存储数据最大体积限制（字节）
     */
    storage: {
        prefix: 'ecosort',
        maxSize: 4 * 1024 * 1024,
    },

    /**
     * 路由系统配置
     * @type {Object}
     * @property {string} defaultRoute - 首屏默认路由路径
     * @property {string} notFoundRoute - 未匹配路由时的回退路径
     */
    router: {
        defaultRoute: '#/home',
        notFoundRoute: '#/home',
    },

    /**
     * 调试与日志配置
     * @type {Object}
     * @property {boolean} showErrorAlert - 是否以alert形式展示错误（生产环境建议关闭）
     * @property {string} logLevel - 日志级别：'debug' | 'info' | 'warn' | 'silent'
     * @property {boolean} exposeDebugAPI - 是否暴露window.__app__调试接口
     */
    debug: {
        showErrorAlert: true,
        logLevel: 'info',
        exposeDebugAPI: true,
    },

    /**
     * TabBar标签页索引映射表
     * 用于页面切换时同步底部标签栏的激活状态
     * @type {Object<string, number>}
     */
    tabIndexMap: {
        home: 0,
        search: 1,
        map: 2,
        community: 3,
        profile: 4,
    },
};

export default config;

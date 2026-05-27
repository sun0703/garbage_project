/**
 * @fileoverview 全局状态管理模块 - 基于发布订阅模式的轻量级Store
 * @description 管理校园垃圾分类SPA的所有共享状态，包括当前页面、
 *              选中图片、识别结果、搜索结果、历史记录等核心数据。
 *              采用细粒度订阅机制，仅触发对应key的回调，避免无效渲染。
 *
 * ## 架构设计
 * - **单一数据源**: 所有状态集中管理，避免组件间props drilling
 * - **细粒度订阅**: 按key维度订阅变更，减少不必要的回调触发
 * - **不可变更新**: setState通过浅拷贝保证引用变化，便于依赖追踪
 * - **线程安全**: JavaScript单线程特性天然保证读写一致性
 *
 * ## 推荐API vs 废弃API
 * | 操作     | 推荐方法（当前标准）    | 废弃方法（兼容保留）  |
 * |----------|------------------------|----------------------|
 * | 读取状态 | `getState(key)`        | ~~`get(key)`~~       |
 * | 写入状态 | `setState(key, value)` | ~~`set(key, value)`~~ |
 * | 删除状态 | `setState(key, null)`  | ~~`remove(key)`~~    |
 *
 * @module store
 * @author Frontend Architect
 * @version 1.0.0
 * @see {@link module:config} 全局配置模块
 */

// ==================== 默认状态初始值 ====================

/** @type {Object} 状态字段默认值映射表，用于reset时快速恢复 */
const DEFAULT_STATE = Object.freeze({
    currentPage: 'home',
    selectedImage: null,
    selectedFile: null,
    selectedFileName: '',        /* 当前选中文件的显示名称，上传时由 home.js 设置 */
    predictResult: null,
    searchResults: [],
    searchQuery: '',             /* 当前搜索关键词，首页搜索框输入时同步 */
    historyList: [],
    isLoading: false,
    error: null,
    isDemoMode: false,
    currentUser: null,
    currentItemKeyword: '',
    achievements: [],            /* 用户成就列表 */
    pointsHistory: [],           /* 积分变动历史 */
    statsSummary: null,          /* 数据统计概览 */
    leaderboard: [],             /* 排行榜数据 */
    adminDashboard: null         /* 管理后台仪表盘数据 */
});

// ==================== Store 类定义 ====================

/**
 * 全局状态管理器 - 发布订阅模式实现
 *
 * 核心设计原则：
 * 1. 单一数据源：所有状态集中管理，避免组件间props drilling
 * 2. 细粒度订阅：按key维度订阅变更，减少不必要的回调触发
 * 3. 不可变更新：setState通过浅拷贝保证引用变化，便于依赖追踪
 * 4. 线程安全：JavaScript单线程特性天然保证读写一致性
 *
 * @example
 * // 基础用法示例
 * import { Store } from './store.js';
 * const store = new Store();
 *
 * // 订阅特定状态变更
 * store.subscribe('isLoading', (val) => console.log('加载状态:', val));
 *
 * // 更新状态并自动通知订阅者
 * store.setState('isLoading', true);
 *
 * // 读取当前状态
 * console.log(store.getState('isLoading')); // true
 */
class Store {
    /**
     * 构造函数 - 初始化内部状态容器和监听器注册表
     * @constructor
     */
    constructor() {
        /** @type {Object<string, *>} 内部状态对象，存储所有全局数据 */
        this._state = {};

        /**
         * @type {Map<string, Set<Function>>}
         * 监听器注册表 - key为状态字段名，Set存储该字段的订阅回调集合
         * 使用Set保证同一回调不会重复注册
         */
        this._listeners = new Map();

        // 将默认状态深拷贝到内部状态中
        this._initState();
    }

    // ==================== 私有方法 ====================

    /**
     * 初始化/重置内部状态为默认值
     * @private
     * @returns {void}
     */
    _initState() {
        /* 遍历默认值映射表，逐键复制到_state中 */
        for (const [key, value] of Object.entries(DEFAULT_STATE)) {
            /* 数组和对象类型需要浅拷贝，防止外部修改影响默认值常量 */
            this._state[key] = Array.isArray(value)
                ? [...value]
                : value !== null && typeof value === 'object'
                    ? { ...value }
                    : value;
        }
    }

    /**
     * 触发指定key的所有订阅回调
     * @private
     * @param {string} key - 发生变更的状态字段名
     * @param {*} newValue - 变更后的新值
     * @returns {void}
     */
    _emit(key, newValue) {
        const callbacks = this._listeners.get(key);
        if (!callbacks || callbacks.size === 0) return; // 无订阅者则跳过

        /* 使用Array.from创建快照再遍历，防止遍历过程中回调修改了Set */
        const snapshot = Array.from(callbacks);
        for (const cb of snapshot) {
            try {
                cb(newValue, key); // 传递新值和key，方便通用回调判断来源
            } catch (err) {
                /* 单个回调异常不应阻断其他回调执行 */
                console.error(`[Store] 订阅回调执行错误 (key="${key}"):`, err);
            }
        }
    }

    // ==================== 公共API - 读取 ====================

    /**
     * 获取指定状态的当前值
     *
     * @public
     * @param {string} key - 状态字段名，必须是DEFAULT_STATE中已定义的合法key
     * @returns {*} 该字段的当前值；若key不存在则返回undefined
     *
     * @example
     * const page = store.getState('currentPage');   // 'home'
     * const result = store.getState('predictResult'); // null | object
     */
    getState(key) {
        if (!Object.prototype.hasOwnProperty.call(DEFAULT_STATE, key)) {
            console.warn(`[Store] getState: 未注册的状态字段 "${key}"`);
        }
        return this._state[key];
    }

    /**
     * 获取整个状态的只读副本（调试用途）
     *
     * @public
     * @returns {Readonly<Object<string, *>>} 当前完整状态的冻结副本
     *
     * @example
     * console.log(store.getAllState());
     */
    getAllState() {
        return Object.freeze({ ...this._state });
    }

    // ==================== 公共API - 写入 ====================

    /**
     * 更新指定状态字段并触发对应的订阅回调
     *
     * 设计要点：
     * - 仅当新旧值严格不等（!==）时才触发通知，避免循环更新
     * - 自动同步更新currentPage到_store，保持状态一致性
     *
     * @public
     * @param {string} key - 要更新的状态字段名
     * @param {*} value - 新值
     * @returns {*} 返回设置的新值
     *
     * @throws {TypeError} 当key不是字符串时会抛出类型错误
     *
     * @example
     * store.setState('isLoading', true);           // 触发 isLoading 订阅者
     * store.setState('predictResult', { label: '塑料瓶' }); // 触发 predictResult 订阅者
     */
    setState(key, value) {
        if (typeof key !== 'string' || key.trim() === '') {
            throw new TypeError('[Store] setState: key必须是非空字符串');
        }

        const oldValue = this._state[key];
        this._state[key] = value;

        /* 引用不相等时才派发事件，避免相同值重复渲染 */
        if (oldValue !== value) {
            this._emit(key, value);
        }

        return value;
    }

    /**
     * @deprecated 自 v1.0.0 起废弃，请使用 {@link Store#getState} 替代
     *
     * 为兼容旧页面代码保留的 short-hand 别名方法。
     * 该方法仅是对 getState() 的直接代理，无任何额外逻辑。
     *
     * @public
     * @param {string} key - 状态字段名
     * @returns {*} 该字段的当前值
     *
     * @example
     * // 废弃写法（不推荐）
     * const page = store.get('currentPage');
     *
     * // 推荐替换为
     * const page = store.getState('currentPage');
     */
    get(key) { return this.getState(key); }

    /**
     * @deprecated 自 v1.0.0 起废弃，请使用 {@link Store#setState} 替代
     *
     * 为兼容旧页面代码保留的 short-hand 别名方法。
     * 该方法仅是对 setState() 的直接代理，无任何额外逻辑。
     *
     * @public
     * @param {string} key - 要更新的状态字段名
     * @param {*} value - 新值
     * @returns {*} 返回设置的新值
     *
     * @example
     * // 废弃写法（不推荐）
     * store.set('isLoading', true);
     *
     * // 推荐替换为
     * store.setState('isLoading', true);
     */
    set(key, value) { return this.setState(key, value); }

    /**
     * @deprecated 自 v1.0.0 起废弃，请使用 {@link Store#setState} 配合 null 值替代
     *
     * 为兼容旧页面代码保留的 short-hand 别名方法。
     * 等效于 setState(key, null)，将指定状态字段重置为null。
     *
     * @public
     * @param {string} key - 要清除的状态字段名
     * @returns {*} 返回 null（设置后的值）
     *
     * @example
     * // 废弃写法（不推荐）
     * store.remove('predictResult');
     *
     * // 推荐替换为
     * store.setState('predictResult', null);
     */
    remove(key) { return this.setState(key, null); }

    /**
     * 批量更新多个状态字段（原子操作）
     * 所有字段更新完毕后统一触发回调，适用于关联状态同时变更场景
     *
     * @public
     * @param {Object<string, *>} partial - 包含多个key-value的状态片段对象
     * @returns {void}
     *
     * @example
     * store.batchUpdate({
     *     isLoading: false,
     *     predictResult: { category: '可回收物', confidence: 0.95 },
     *     error: null
     * });
     */
    batchUpdate(partial) {
        if (!partial || typeof partial !== 'object') {
            console.warn('[Store] batchUpdate: 参数必须是非空对象');
            return;
        }

        /* 先收集所有变更，最后统一触发 */
        const changedKeys = [];
        for (const [key, value] of Object.entries(partial)) {
            if (this._state[key] !== value) {
                this._state[key] = value;
                changedKeys.push(key);
            }
        }

        /* 按顺序触发所有变更的回调 */
        for (const key of changedKeys) {
            this._emit(key, this._state[key]);
        }
    }

    /**
     * 重置所有状态到初始值（清除用户数据）
     * 常用于"重新开始"、"退出登录"等场景
     *
     * @public
     * @returns {void}
     */
    reset() {
        const oldState = { ...this._state };
        this._initState();

        /* 对每个发生变化的key都触发通知 */
        for (const key of Object.keys(oldState)) {
            if (oldState[key] !== this._state[key]) {
                this._emit(key, this._state[key]);
            }
        }
    }

    // ==================== 公共API - 订阅管理 ====================

    /**
     * 订阅指定状态字段的变更
     *
     * @public
     * @param {string} key - 要监听的状态字段名
     * @param {Function} callback - 状态变更时的回调函数，签名：(newValue, key) => void
     * @returns {Function} 取消订阅的函数（遵循unsubscribe模式，方便清理）
     *
     * @example
     * // 方式一：手动取消订阅
     * const unsub = store.subscribe('isLoading', (v) => toggleSpinner(v));
     * // 不再需要时调用 unsub();
     *
     * // 方式二：配合组件卸载自动清理
     * useEffect(() => {
     *     return store.subscribe('predictResult', renderResult);
     * }, []);
     */
    subscribe(key, callback) {
        if (typeof callback !== 'function') {
            throw new TypeError('[Store] subscribe: callback必须是函数');
        }

        /* 确保该key的Set已初始化 */
        if (!this._listeners.has(key)) {
            this._listeners.set(key, new Set());
        }

        this._listeners.get(key).add(callback);

        /* 返回取消订阅的闭包函数，符合业界最佳实践 */
        return () => this.unsubscribe(key, callback);
    }

    /**
     * 取消订阅指定状态字段的某个回调
     *
     * @public
     * @param {string} key - 状态字段名
     * @param {Function} callback - 之前注册时要移除的那个回调函数引用
     * @returns {boolean} 是否成功找到并移除了该回调
     *
     * @example
     * const handler = (v) => console.log(v);
     * store.subscribe('isLoading', handler);
     * store.unsubscribe('isLoading', handler); // true
     */
    unsubscribe(key, callback) {
        const callbacks = this._listeners.get(key);
        if (!callbacks) return false;

        const removed = callbacks.delete(callback);

        /* 当某key没有任何订阅者时，清理空Set以释放内存 */
        if (callbacks.size === 0) {
            this._listeners.delete(key);
        }

        return removed;
    }

    /**
     * 清除指定key的所有订阅者（或全部清除）
     *
     * @public
     * @param {string} [key] - 可选，指定要清除的字段名；省略则清除所有
     * @returns {void}
     *
     * @example
     * store.clearListeners('isLoading');  // 仅清除 isLoading 的订阅
     * store.clearListeners();             // 清除所有订阅（应用销毁时用）
     */
    clearListeners(key) {
        if (key) {
            this._listeners.delete(key);
        } else {
            this._listeners.clear();
        }
    }
}

// ==================== 模块导出 ====================

/** 导出Store类供其他模块实例化使用 */
export { Store };

/** 导出默认状态常量，方便外部做校验或对比 */
export { DEFAULT_STATE };

/** 导出Store单例实例，供各页面直接使用 */
const store = new Store();
export { store };

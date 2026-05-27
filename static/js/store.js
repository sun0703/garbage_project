/*
 * 全局状态管理 - 发布订阅模式
 * 所有页面共享的数据都在这，按key订阅变更，不相关的不会触发
 */

// 默认状态，reset的时候用
const DEFAULT_STATE = Object.freeze({
    currentPage: 'home',
    selectedImage: null,
    selectedFile: null,
    selectedFileName: '',        // 上传时由home.js设置
    predictResult: null,
    searchResults: [],
    searchQuery: '',             // 首页搜索框输入时同步过来
    historyList: [],
    isLoading: false,
    error: null,
    isDemoMode: false,
    currentUser: null,
    currentItemKeyword: '',
    achievements: [],
    pointsHistory: [],
    statsSummary: null,
    leaderboard: [],
    adminDashboard: null
});

class Store {
    constructor() {
        this._state = {};
        // key → Set<callback>，Set去重
        this._listeners = new Map();
        this._initState();
    }

    // 把默认值拷贝到_state里，数组和对象要浅拷贝防止改到常量
    _initState() {
        for (const [key, value] of Object.entries(DEFAULT_STATE)) {
            this._state[key] = Array.isArray(value)
                ? [...value]
                : value !== null && typeof value === 'object'
                    ? { ...value }
                    : value;
        }
    }

    // 通知某个key的所有订阅者
    _emit(key, newValue) {
        const callbacks = this._listeners.get(key);
        if (!callbacks || callbacks.size === 0) return;

        // 先拍个快照再遍历，防止回调里改了Set
        const snapshot = Array.from(callbacks);
        for (const cb of snapshot) {
            try {
                cb(newValue, key);
            } catch (err) {
                // 一个回调炸了不能影响其他的
                console.error(`[Store] 订阅回调执行错误 (key="${key}"):`, err);
            }
        }
    }

    /* ---- 读取 ---- */

    getState(key) {
        if (!Object.prototype.hasOwnProperty.call(DEFAULT_STATE, key)) {
            console.warn(`[Store] getState: 未注册的状态字段 "${key}"`);
        }
        return this._state[key];
    }

    // 调试用，拿一份只读快照
    getAllState() {
        return Object.freeze({ ...this._state });
    }

    /* ---- 写入 ---- */

    setState(key, value) {
        if (typeof key !== 'string' || key.trim() === '') {
            throw new TypeError('[Store] setState: key必须是非空字符串');
        }

        const oldValue = this._state[key];
        this._state[key] = value;

        // 值没变就不通知，避免循环更新
        if (oldValue !== value) {
            this._emit(key, value);
        }

        return value;
    }

    /** @deprecated 用 getState 代替 */
    get(key) { return this.getState(key); }

    /** @deprecated 用 setState 代替 */
    set(key, value) { return this.setState(key, value); }

    /** @deprecated 用 setState(key, null) 代替 */
    remove(key) { return this.setState(key, null); }

    // 批量更新，全部改完再统一通知
    batchUpdate(partial) {
        if (!partial || typeof partial !== 'object') {
            console.warn('[Store] batchUpdate: 参数必须是非空对象');
            return;
        }

        const changedKeys = [];
        for (const [key, value] of Object.entries(partial)) {
            if (this._state[key] !== value) {
                this._state[key] = value;
                changedKeys.push(key);
            }
        }

        for (const key of changedKeys) {
            this._emit(key, this._state[key]);
        }
    }

    // 重置所有状态到初始值，退出登录时用
    reset() {
        const oldState = { ...this._state };
        this._initState();

        for (const key of Object.keys(oldState)) {
            if (oldState[key] !== this._state[key]) {
                this._emit(key, this._state[key]);
            }
        }
    }

    /* ---- 订阅管理 ---- */

    // 返回取消订阅的函数，方便清理
    subscribe(key, callback) {
        if (typeof callback !== 'function') {
            throw new TypeError('[Store] subscribe: callback必须是函数');
        }

        if (!this._listeners.has(key)) {
            this._listeners.set(key, new Set());
        }

        this._listeners.get(key).add(callback);

        return () => this.unsubscribe(key, callback);
    }

    unsubscribe(key, callback) {
        const callbacks = this._listeners.get(key);
        if (!callbacks) return false;

        const removed = callbacks.delete(callback);

        // 空Set清掉，省点内存
        if (callbacks.size === 0) {
            this._listeners.delete(key);
        }

        return removed;
    }

    // 不传key就清全部
    clearListeners(key) {
        if (key) {
            this._listeners.delete(key);
        } else {
            this._listeners.clear();
        }
    }
}

export { Store };
export { DEFAULT_STATE };

const store = new Store();
export { store };

/**
 * SearchHistory - 搜索历史管理工具
 *
 * 功能说明：
 * - 基于 localStorage 持久化搜索历史
 * - 最多保存 20 条记录
 * - 去重：相同关键词只保留最新一条
 * - 按时间倒序排列
 * - 支持清空全部历史
 *
 * @class SearchHistory
 */

const STORAGE_KEY = 'garbage_search_history';
const MAX_ITEMS = 20;

export class SearchHistory {
    static getAll() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            const data = JSON.parse(raw);
            return Array.isArray(data) ? data : [];
        } catch {
            return [];
        }
    }

    static add(query) {
        if (!query || !query.trim()) return;

        const trimmed = query.trim();
        let history = this.getAll();

        history = history.filter(item => item.query !== trimmed);

        history.unshift({
            query: trimmed,
            timestamp: Date.now()
        });

        if (history.length > MAX_ITEMS) {
            history = history.slice(0, MAX_ITEMS);
        }

        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
        } catch {
            // localStorage 满了，静默失败
        }
    }

    static remove(query) {
        if (!query) return;

        let history = this.getAll();
        history = history.filter(item => item.query !== query.trim());

        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
        } catch {
            // 静默失败
        }
    }

    static clear() {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // 静默失败
        }
    }

    static getRecent(count = 5) {
        return this.getAll().slice(0, count);
    }
}

/**
 * @fileoverview localStorage 本地存储封装模块
 * @description 提供带命名空间前缀的localStorage操作接口，
 *              专注于垃圾分类识别历史记录的增删查清等管理功能
 * @module utils/storage
 */

/** 历史记录最大存储条数 */
const MAX_HISTORY_COUNT = 50;

/**
 * localStorage 存储管理类
 *
 * @class Storage
 * @description 封装带前缀隔离的localStorage读写操作，
 *              主要用于识别历史记录的持久化管理。
 *              所有键名自动拼接prefix前缀，避免与其他应用数据冲突。
 *
 * @example
 * import { Storage } from './utils/storage.js';
 *
 * // 创建实例（默认前缀 'ecosort'）
 * const storage = new Storage();
 *
 * // 保存一条识别记录
 * storage.saveHistory({
 *   thumbnail: 'data:image/jpeg;base64,...',
 *   category: '可回收物',
 *   category_id: 1,
 *   confidence: 0.92,
 *   item_name: '塑料瓶',
 *   bin_color: '#007bff'
 * });
 *
 * // 获取最近20条记录
 * const recent = storage.getHistory(20);
 */
export class Storage {

  /**
   * 存储键名常量：识别历史记录
   * @static
   * @type {string}
   */
  static KEY = {
    HISTORY: 'history'
  };

  /**
   * 构造函数：初始化存储实例
   *
   * @param {string} [prefix='ecosort'] - localStorage键名前缀，用于多应用/多环境隔离
   * @description 实例化时仅保存前缀值，不执行任何IO操作。
   *              最终存储键格式为：{prefix}_{key}，如 ecosort_history
   *
   * @example
   * const defaultStorage = new Storage();           // 前缀: ecosort
   * const customStorage = new Storage('myapp_v2');  // 前缀: myapp_v2
   */
  constructor(prefix = 'ecosort') {
    /** @private 存储键名前缀 */
    this._prefix = prefix;
  }

  /**
   * 拼接完整的存储键名（内部方法）
   *
   * @private
   * @param {string} key - 原始键名
   * @returns {string} 拼接前缀后的完整键名，格式为 {prefix}_{key}
   * @description 所有公开方法通过此方法获取最终存储键，
   *              确保键名统一且不与外部数据冲突
   */
  _getKey(key) {
    return `${this._prefix}_${key}`;
  }

  /**
   * 生成唯一记录ID
   *
   * @private
   * @returns {string} 基于时间戳+随机数的短ID字符串
   * @description 组合方式：Date.now().toString(36) + 随机8位字符
   *              输出示例："l3k2j1h9g4f2d7xq5m"
   */
  _generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 8);
  }

  /**
   * 从localStorage安全读取JSON数据
   *
   * @private
   * @param {string} key - 存储键名（已含前缀）
   * @returns {*} 解析后的数据对象，读取失败或无数据时返回默认值
   * @description 内部辅助方法：统一处理JSON解析异常和数据缺失场景
   */
  _read(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      // JSON解析失败时返回null并输出警告
      console.warn(`[Storage] 读取 ${key} 失败:`, error.message);
      return null;
    }
  }

  /**
   * 安全写入JSON数据到localStorage
   *
   * @private
   * @param {string} key - 存储键名（已含前缀）
   * @param {*} data - 待序列化的数据
   * @returns {boolean} 写入是否成功
   * @description 内部辅助方法：统一处理序列化和存储容量异常
   */
  _write(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (error) {
      // 通常为存储满或隐私模式限制
      console.error(`[Storage] 写入 ${key} 失败:`, error.message);
      return false;
    }
  }

  /**
   * 保存一条识别历史记录
   *
   * @param {Object} record - 识别记录数据（不含id和timestamp，由本方法自动补充）
   * @param {string} record.thumbnail - 缩略图Base64 DataURL字符串
   * @param {string} record.category - 垃圾分类名称（如"可回收物"）
   * @param {number} record.category_id - 分类ID（1-4对应四类垃圾）
   * @param {number} record.confidence - 模型识别置信度（0-1之间的小数）
   * @param {string} record.item_name - 识别出的物品名称
   * @param {string} record.bin_color - 对应垃圾桶颜色十六进制值
   * @returns {void}
   *
   * @description 完整处理流程：
   *   1. 自动生成唯一ID和当前时间戳
   *   2. 追加到现有历史列表头部
   *   3. 容量控制：超过50条时删除最旧的记录
   *   4. 持久化写入localStorage
   *
   * 存储的完整记录结构：
   * ```json
   * {
   *   "id": "l3k2j1h9g4f2",
   *   "thumbnail": "data:image/jpeg;base64,...",
   *   "category": "可回收物",
   *   "category_id": 1,
   *   "confidence": 0.92,
   *   "item_name": "塑料瓶",
   *   "bin_color": "#007bff",
   *   "timestamp": 1716240000000
   * }
   * ```
   *
   * @example
   * const storage = new Storage();
   * storage.saveHistory({
   *   thumbnail: await ImageProcessor.toThumbnail(file),
   *   category: '可回收物',
   *   category_id: 1,
   *   confidence: 0.92,
   *   item_name: '塑料瓶',
   *   bin_color: '#007bff'
   * });
   */
  saveHistory(record) {
    const key = this._getKey(Storage.KEY.HISTORY);

    // 读取现有历史列表（不存在则初始化空数组）
    let history = this._read(key) || [];

    // 构建完整记录：补充ID和时间戳
    const fullRecord = {
      id: this._generateId(),
      timestamp: Date.now(),
      ...record
    };

    // 新记录插入到数组头部（最新的在前面）
    history.unshift(fullRecord);

    // 容量控制：超出上限时截断尾部最旧记录
    if (history.length > MAX_HISTORY_COUNT) {
      history = history.slice(0, MAX_HISTORY_COUNT);
    }

    // 持久化写入
    this._write(key, history);
  }

  /**
   * 获取历史记录列表
   *
   * @param {number} [limit=50] - 最大返回条数，用于分页或限制加载量
   * @returns {Array<Object>} 历史记录数组，按时间倒序排列（最新在前）
   *          每条记录包含完整字段：id, thumbnail, category, category_id,
   *          confidence, item_name, bin_color, timestamp
   *
   * @description 从localStorage读取全部历史记录并返回指定数量的最新条目。
   *              数据已按timestamp降序排列，无需额外排序。
   *              返回的是数据副本，修改返回值不影响原始存储。
   *
   * @example
   * const storage = new Storage();
   *
   * // 获取全部历史（最多50条）
   * const allRecords = storage.getHistory();
   *
   * // 仅获取最近10条用于首页展示
   * const recent10 = storage.getHistory(10);
   */
  getHistory(limit = 50) {
    const key = this._getKey(Storage.KEY.HISTORY);
    const history = this._read(key) || [];

    // 返回指定数量的副本（已按插入顺序倒序）
    return history.slice(0, limit);
  }

  /**
   * 删除指定ID的历史记录
   *
   * @param {string} id - 记录的唯一标识符（由saveHistory自动生成的id字段）
   * @returns {boolean} 是否成功找到并删除了该记录
   *
   * @description 根据记录ID精确匹配并移除单条历史记录，
   *              删除后立即持久化更新后的列表。
   *              若ID对应的记录不存在则返回false但不抛出异常
   *
   * @example
   * const storage = new Storage();
   * const success = storage.deleteHistory('l3k2j1h9g4f2');
   * if (success) {
   *   showToast('记录已删除', 'success');
   * } else {
   *   showToast('未找到该记录', 'warning');
   * }
   */
  deleteHistory(id) {
    const key = this._getKey(Storage.KEY.HISTORY);
    let history = this._read(key) || [];

    // 查找目标记录在数组中的索引
    const index = history.findIndex((item) => item.id === id);

    // 未找到则直接返回false
    if (index === -1) return false;

    // 从数组中移除该记录
    history.splice(index, 1);

    // 更新存储
    this._write(key, history);
    return true;
  }

  /**
   * 清空全部历史记录
   *
   * @returns {void}
   * @description 将历史记录键的值重置为空数组。
   *              此操作不可恢复，调用前应使用confirm()进行二次确认
   *
   * @example
   * if (await confirm('确定要清空所有识别历史吗？')) {
   *   storage.clearHistory();
   *   showToast('历史记录已清空', 'success');
   * }
   */
  clearHistory() {
    const key = this._getKey(Storage.KEY.HISTORY);
    this._write(key, []);
  }

  /**
   * 获取历史记录总数
   *
   * @returns {number} 当前存储的历史记录条数，无记录时返回0
   * @description 用于界面显示计数（如"共12条记录"）或条件判断。
   *              不加载完整数据，仅返回数组长度，性能开销极小
   *
   * @example
   * const count = storage.getHistoryCount();
   * document.querySelector('.history-count').textContent = `共${count}条记录`;
   */
  getHistoryCount() {
    const key = this._getKey(Storage.KEY.HISTORY);
    const history = this._read(key) || [];
    return history.length;
  }
}

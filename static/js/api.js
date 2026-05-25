/**
 * @fileoverview API客户端封装模块 - 统一HTTP请求与错误处理
 * @description 封装校园垃圾分类后端所有RESTful接口的调用逻辑，
 *              包含统一请求/响应拦截、超时控制、错误码映射、
 *              降级分析等能力。基于原生Fetch API + AbortController实现。
 * @module api
 * @author Frontend Architect
 * @version 1.0.0
 */

// ==================== 常量定义 ====================

/** 默认请求超时时间（毫秒） */
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * API业务错误码与中文提示的映射表
 * 按照阶段一API契约文档定义，覆盖所有已知服务端错误场景
 *
 * @type {Readonly<Object<string, {message: string, status: number}>>}
 * @constant
 */
const ERROR_CODE_MAP = Object.freeze({
    E001: { message: '图片格式无效，请上传JPG/PNG格式的图片', status: 400 },
    E002: { message: '模型未就绪，请稍后重试或联系管理员', status: 503 },
    E004: { message: '请求的资源不存在', status: 404 },
    E005: { message: '操作过于频繁，请稍后再试', status: 429 },
    E003: { message: 'AI推理过程出错，请稍后重试', status: 500 },
    E006: { message: '服务器繁忙，请稍后重试', status: 500 }
});

// ==================== ApiError 类 ====================

/**
 * API调用异常类 - 统一封装网络层和业务层的错误信息
 *
 * 继承自原生Error，额外携带：
 * - code: 业务错误码（如E001）或系统级标识（NETWORK/TIMEOUT）
 * - statusCode: HTTP状态码（网络异常时为0）
 * - rawResponse: 原始响应对象（调试用）
 *
 * @extends Error
 *
 * @example
 * try {
 *     await api.predict(imageBase64);
 * } catch (err) {
 *     if (err instanceof ApiError) {
 *         console.log(err.code);      // 'E001'
 *         console.log(err.message);   // '图片格式无效...'
 *         console.log(err.statusCode);// 400
 *     }
 * }
 */
class ApiError extends Error {
    /**
     * 构造API错误实例
     *
     * @constructor
     * @param {string} code - 错误编码（业务码如E001 / 系统码如NETWORK/TIMEOUT）
     * @param {string} message - 用户可读的错误描述
     * @param {number} [statusCode=0] - HTTP状态码；网络错误时传0
     * @param {Response|null} [rawResponse=null] - 原始Fetch Response对象
     */
    constructor(code, message, statusCode = 0, rawResponse = null) {
        super(message);
        /** @type {string} 错误唯一标识符 */
        this.code = code;
        /** @type {number} HTTP状态码 */
        this.statusCode = statusCode;
        /** @type {Response|null} 原始响应对象 */
        this.rawResponse = rawResponse;
        /** @type {string} 固定类名标识，便于instanceof判断 */
        this.name = 'ApiError';
    }
}

// ==================== ApiClient 类 ====================

/**
 * RESTful API客户端 - 封装所有后端接口调用
 *
 * 核心职责：
 * 1. 统一请求头、超时控制、凭证管理
 * 2. 分层错误处理：网络错误 → HTTP错误 → 业务错误
 * 3. 业务方法封装：predict/search/getCategories/batchPredict/analyzeFallback
 * 4. 降级策略：主接口失败时自动切换到备用分析接口
 *
 * 设计模式：Facade外观模式 - 对外暴露简洁的业务方法，
 * 隐藏Fetch/Ajax/AbortController等底层细节
 *
 * @example
 * import { ApiClient } from './api.js';
 *
 * const api = new ApiClient();           // baseURL默认空字符串（同源部署）
 * const api = new ApiClient('/api/v1'); // 指定基础路径前缀
 *
 * // 调用识别接口
 * const result = await api.predict(base64Image);
 */
class ApiClient {
    /**
     * 构造API客户端实例
     *
     * @constructor
     * @param {string} [baseURL=''] - API基础路径前缀，同源部署时留空即可
     */
    constructor(baseURL = '') {
        /** @type {string} API基础路径，所有请求自动拼接此前缀 */
        this.baseURL = baseURL;
        /** @type {number} 当前请求超时配置（毫秒），允许运行时调整 */
        this.timeout = REQUEST_TIMEOUT_MS;
    }

    // ==================== 核心请求方法 ====================

    /**
     * 通用HTTP请求方法 - 所有业务方法的底层实现
     *
     * 处理流程：
     * 1. 拼接完整URL（baseURL + path）
     * 2. 设置统一请求头（Content-Type: application/json）
     * 3. 创建AbortController实现超时控制
     * 4. 发起fetch请求并等待响应
     * 5. 根据响应状态分类处理：
     *    - 2xx: 解析JSON并返回data字段
     *    - 网络错误(TypeError): 转为"连接失败"提示
     *    - 超时(AbortError): 转为"请求超时"提示
     *    - 4xx/5xx: 提取业务错误码并翻译为中文
     *
     * @public
     * @async
     * @param {'GET'|'POST'|'PUT'|'DELETE'|'PATCH'} method - HTTP请求方法
     * @param {string} path - 接口路径（不含baseURL前缀），如 '/api/predict'
     * @param {Object} [options={}] - 请求选项
     * @param {Object} [options.body] - 请求体对象（POST/PUT/PATCH时使用）
     * @param {Object} [options.headers] - 额外请求头（合并到默认头中）
     * @param {number} [options.timeout] - 本次请求自定义超时时间（毫秒）
     * @returns {Promise<*>} 成功时resolve响应体中的data部分
     * @throws {ApiError} 任何异常均包装为ApiError抛出
     *
     * @example
     * // POST请求示例
     * const data = await api.request('POST', '/api/predict', {
     *     body: { image: base64String }
     * });
     *
     * // GET请求示例
     * const categories = await api.request('GET', '/api/categories');
     */
    async request(method, path, options = {}) {
        /* ---------- 第一步：构建请求参数 ---------- */
        const url = `${this.baseURL}${path}`;
        const reqTimeout = options.timeout || this.timeout;

        /* 创建超时控制器 */
        const controller = new AbortController();
        const timerId = setTimeout(() => controller.abort(), reqTimeout);

        /* 合并请求头：默认JSON + 用户自定义头 */
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        /* 组装fetch初始化参数 */
        const init = {
            method,
            headers,
            signal: controller.signal
        };

        /* 仅在有body且非GET/HEAD时才添加请求体 */
        if (options.body && !['GET', 'HEAD'].includes(method.toUpperCase())) {
            init.body = JSON.stringify(options.body);
        }

        /* ---------- 第二步：发起请求并处理响应 ---------- */
        try {
            const response = await fetch(url, init);
            clearTimeout(timerId); // 成功获取响应，清除超时定时器

            /* 解析响应体JSON（无论成功失败都需要读取） */
            let responseData;
            try {
                responseData = await response.json();
            } catch (parseErr) {
                /* JSON解析失败（如返回了HTML错误页），构造兜底结构 */
                responseData = {
                    success: false,
                    error: { code: 'E006', message: `服务器返回非JSON数据(HTTP ${response.status})` }
                };
            }

            /* ---------- 第三步：按状态码分支处理 ---------- */
            if (!response.ok) {
                return this._handleHttpError(response, responseData);
            }

            /* 2xx成功：优先提取data/result字段，兼容裸数据格式 */
            if (responseData.data !== undefined) return responseData.data;
            if (responseData.result !== undefined) return responseData.result;
            return responseData;

        } catch (err) {
            clearTimeout(timerId);

            /* 区分超时取消和网络故障两类底层异常 */
            if (err.name === 'AbortError') {
                throw new ApiError(
                    'TIMEOUT',
                    '请求超时，请稍后重试',
                    0,
                    null
                );
            }

            /* TypeError通常表示网络断开、DNS失败、CORS拦截等 */
            if (err instanceof TypeError) {
                throw new ApiError(
                    'NETWORK',
                    '网络连接失败，请检查后端服务是否启动',
                    0,
                    null
                );
            }

            /* 其他未知异常原样包装后抛出 */
            throw new ApiError('UNKNOWN', err.message || '未知网络错误', 0, null);
        }
    }

    /**
     * 处理HTTP层面错误（4xx/5xx状态码）
     * 从响应体中提取业务错误码，匹配预定义映射表生成友好提示
     *
     * @private
     * @param {Response} response - Fetch Response对象
     * @param {Object} responseData - 已解析的JSON响应体
     * @throws {ApiError} 总是抛出包装后的ApiError
     * @returns {never}
     */
    _handleHttpError(response, responseData) {
        const status = response.status;

        /* ---------- 401 未授权特殊处理 ---------- */
        /* 401 是预期的业务行为（用户未登录），不应视为异常错误。
         * 浏览器会对 Failed to load resource 始终显示红色 [error]，
         * 此处仅抛出带有 UNAUTH 标识的 ApiError，供调用方静默处理，
         * 不额外输出 console.error 避免双重噪音。 */
        if (status === 401) {
            throw new ApiError(
                'UNAUTH',
                '未授权，请先登录',
                401,
                response
            );
        }

        /* 尝试从响应体中提取业务错误码 */
        const serverCode = responseData?.error?.code || '';
        const serverMsg = responseData?.error?.message || '';

        /* 在预定义映射表中查找对应提示 */
        const mapped = ERROR_CODE_MAP[serverCode];

        if (mapped) {
            /* 已知业务错误码：使用预定义的中文消息 */
            throw new ApiError(serverCode, mapped.message, status, response);
        }

        /* 未注册的错误码：优先使用服务端返回的消息，否则根据状态码范围生成 */
        const fallbackMessage = serverMsg || this._getDefaultMessage(status);
        throw new ApiError(serverCode || `HTTP_${status}`, fallbackMessage, status, response);
    }

    /**
     * 根据HTTP状态码生成兜底错误消息
     * 用于服务端返回了未知错误码时的降级提示
     *
     * @private
     * @param {number} status - HTTP状态码
     * @returns {string} 用户可读的错误描述
     */
    _getDefaultMessage(status) {
        if (status >= 400 && status < 500) {
            return `请求参数有误（HTTP ${status}），请检查输入后重试`;
        }
        if (status >= 500) {
            return `服务器内部错误（HTTP ${status}），请稍后重试`;
        }
        return `请求失败（HTTP ${status}）`;
    }

    // ==================== 业务API方法 ====================

    /**
     * AI垃圾识别接口 - 上传图片进行智能分类
     *
     * 向后端发送Base64编码的图片数据，
     * 返回AI模型的识别结果（类别、置信度、投放指引等）
     *
     * @public
     * @async
     * @param {string} imageBase64 - 图片的Data URL或纯Base64字符串（含data:image前缀）
     * @returns {Promise<Object>} 识别结果对象，结构如下：
     *   @property {string} category - 垃圾分类名称（可回收物/有害垃圾/厨余垃圾/其他垃圾）
     *   @property {string} label_cn - 物品中文名称
     *   @property {number} confidence - 置信度（0~1之间的小数）
     *   @property {string} bin_color - 分类对应的展示颜色（十六进制色值）
     *   @property {string} guidance - 投放指引文案
     *   @property {number} inference_time_ms - 模型推理耗时（毫秒）
     * @throws {ApiError} 图片无效(E001)、模型未就绪(E002)、网络错误等
     *
     * @example
     * try {
     *     const result = await api.predict(selectedImageData);
     *     console.log(result.category);       // '可回收物'
     *     console.log(result.confidence);     // 0.92
     *     console.log(result.label_cn);       // '塑料瓶'
     * } catch (err) {
     *     console.error(err.message);         // '图片格式无效...'
     * }
     */
    async predict(imageBase64) {
        if (!imageBase64 || typeof imageBase64 !== 'string') {
            throw new ApiError('E001', '图片数据不能为空', 400);
        }

        return this.request('POST', '/api/predict', {
            body: { image: imageBase64 },
            timeout: 45_000 // 识别接口可能较慢，给予更长超时
        });
    }

    /**
     * 垃圾名称搜索接口 - 通过关键词模糊查询垃圾分类信息
     *
     * @public
     * @async
     * @param {string} query - 用户输入的搜索关键词（如"塑料瓶"、"电池"）
     * @returns {Promise<Array<Object>>} 匹配结果列表，每项结构：
     *   @property {string} label - 物品名称
     *   @property {string} category - 所属分类
     *   @property {string} bin_icon - 分类图标字符
     *   @property {number} similarity_score - 相似度百分比（0~100整数）
     * @throws {ApiError} 查询为空、网络错误等
     *
     * @example
     * const results = await api.search('塑料瓶');
     * // [{ label:'塑料瓶', category:'可回收物', similarity_score:98 }, ...]
     */
    async search(query) {
        if (!query || typeof query !== 'string') {
            throw new ApiError('E001', '搜索关键词不能为空', 400);
        }

        return this.request('GET', `/api/search?query=${encodeURIComponent(query.trim())}`);
    }

    /**
     * 获取全量垃圾分类目录
     *
     * 返回系统中支持的所有垃圾分类及其典型物品清单，
     * 用于首页展示、搜索联想、分类指南页面等场景
     *
     * @public
     * @async
     * @returns {Promise<Object>} 分类目录数据，结构如下：
     *   @property {Array<Object>} categories - 分类列表
     *     @property {string} categories[].name - 分类名称
     *     @property {string} categories[].color - 展示颜色
     *     @property {Array<string>} categories[].items - 该分类下的典型物品
     *   @property {number} total - 物品总数
     * @throws {ApiError} 网络错误、服务不可用等
     *
     * @example
     * const catalog = await api.getCategories();
     * catalog.categories.forEach(cat => {
     *     console.log(`${cat.name}: ${cat.items.join(', ')}`);
     * });
     */
    async getCategories() {
        return this.request('GET', '/api/categories');
    }

    async getGuideStandard() {
        return this.request('GET', '/api/guide/standard');
    }

    async getGuideCategory(categoryId) {
        return this.request('GET', `/api/guide/category/${categoryId}`);
    }

    async getConfusingPairs(limit = 10, frequency = '') {
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        if (frequency) params.set('frequency', frequency);
        return this.request('GET', `/api/guide/confusing?${params.toString()}`);
    }

    async getConfusingPair(pairId) {
        return this.request('GET', `/api/guide/confusing/${pairId}`);
    }

    async getGuideItem(keyword) {
        return this.request('GET', `/api/guide/item/${encodeURIComponent(keyword)}`);
    }

    /**
     * 批量识别接口 - 同时对多张图片进行AI分类
     *
     * 适用于用户一次选择多张图片的场景，
     * 减少网络往返次数，提升批量处理效率
     *
     * @public
     * @async
     * @param {Array<string>} images - Base64图片数据数组
     * @returns {Promise<Array<Object>>} 识别结果数组，顺序与输入一致
     * @throws {ApiError} 数组为空、单张图片过大、部分失败等情况
     *
     * @example
     * const results = await api.batchPredict([img1, img2, img3]);
     * results.forEach((r, i) => console.log(`图${i+1}: ${r.label_cn}`));
     */
    async batchPredict(images) {
        if (!Array.isArray(images) || images.length === 0) {
            throw new ApiError('E001', '图片列表不能为空', 400);
        }

        if (images.length > 5) {
            throw new ApiError('E005', '单次最多上传5张图片', 429);
        }

        return this.request('POST', '/api/batch-predict', {
            body: { images },
            timeout: 120_000 // 批量识别需要更长时间
        });
    }

    /**
     * 降级特征分析接口 - 当主预测模型不可用时的备用方案
     *
     * 该接口不依赖深度学习模型，而是通过传统图像特征（颜色、纹理、形状）
     * 进行粗粒度的垃圾类型推断。适用于：
     * - GPU资源不足导致主模型离线
     * - 快速预判场景（不需要高精度结果）
     * - 开发调试阶段验证管道连通性
     *
     * @public
     * @async
     * @param {string} imageBase64 - 图片Base64数据
     * @returns {Promise<Object>} 特征分析结果：
     *   @property {string} dominant_color - 主色调
     *   @property {string} texture_type - 纹理类型
     *   @property {Array<Object>>} candidates - 候选分类及置信度
     *   @property {string} method - 分析方法标识（fallback）
     * @throws {ApiError} 同predict接口的错误体系
     *
     * @example
     * try {
     *     const result = await api.predict(imageData);
     * } catch (err) {
     *     // 主模型失败时降级到特征分析
     *     if (err.code === 'E002') {
     *         const fallback = await api.analyzeFallback(imageData);
     *         renderFallbackResult(fallback);
     *     }
     * }
     */
    async analyzeFallback(imageBase64) {
        if (!imageBase64 || typeof imageBase64 !== 'string') {
            throw new ApiError('E001', '图片数据不能为空', 400);
        }

        return this.request('POST', '/api/debug/analyze', {
            body: { image: imageBase64 },
            timeout: 20_000 // 特征分析比深度学习快，但比普通请求慢
        });
    }

    // ==================== 历史记录API方法 ====================

    /**
     * 获取识别历史记录（分页）
     * @param {number} [page=1] - 页码
     * @param {number} [pageSize=20] - 每页条数
     * @returns {Promise<Object>} { data: [...], pagination: { total, page, page_size, total_pages } }
     */
    async getHistory(page = 1, pageSize = 20) {
        return this.request('GET', `/api/history?page=${page}&page_size=${pageSize}`);
    }

    /**
     * 删除单条历史记录
     * @param {string} id - 记录ID
     * @returns {Promise<Object>} { success: true, message: '已删除' }
     */
    async deleteHistoryRecord(id) {
        return this.request('DELETE', `/api/history/${encodeURIComponent(id)}`);
    }

    /**
     * 清空全部历史记录
     * @returns {Promise<Object>} { success: true, message: '已清空全部历史记录' }
     */
    async clearAllHistory() {
        return this.request('DELETE', '/api/history');
    }

    async register(username, password, nickname = '') {
        return this.request('POST', '/api/auth/register', {
            body: { username, password, nickname }
        });
    }

    async login(username, password, remember = false) {
        return this.request('POST', '/api/auth/login', {
            body: { username, password, remember }
        });
    }

    async logout() {
        return this.request('POST', '/api/auth/logout');
    }

    async getMe() {
        return this.request('GET', '/api/auth/me');
    }

    async getDisposalPoints(zone = '', category = '') {
        const params = new URLSearchParams();
        if (zone) params.set('zone', zone);
        if (category) params.set('category', category);
        return this.request('GET', `/api/map/points?${params.toString()}`);
    }

    async getDisposalPoint(pointId) {
        return this.request('GET', `/api/map/point/${pointId}`);
    }

    async checkin(pointId = '', lat = 0, lng = 0, category = '') {
        return this.request('POST', '/api/checkin', {
            body: { point_id: pointId, lat, lng, category }
        });
    }

    async getTodayCheckin() {
        return this.request('GET', '/api/checkin/today');
    }

    async getCheckinHistory(page = 1) {
        return this.request('GET', `/api/checkin/history?page=${page}`);
    }

    async getDailyQuiz() {
        return this.request('GET', '/api/quiz/daily');
    }

    async answerQuiz(questionId, selected) {
        return this.request('POST', '/api/quiz/answer', {
            body: { question_id: questionId, selected }
        });
    }

    async getActivities(status = '', page = 1) {
        const params = new URLSearchParams();
        if (status) params.set('status', status);
        params.set('page', page);
        return this.request('GET', `/api/activities?${params.toString()}`);
    }

    async getActivity(activityId) {
        return this.request('GET', `/api/activities/${activityId}`);
    }

    async signupActivity(activityId) {
        return this.request('POST', '/api/activities/signup', {
            body: { activity_id: activityId }
        });
    }

    async checkActivitySignup(activityId) {
        return this.request('GET', `/api/activities/${activityId}/signed`);
    }

    async createActivity(activityData) {
        return this.request('POST', '/api/activities', { body: activityData });
    }

    async updateActivity(activityId, activityData) {
        return this.request('PUT', `/api/activities/${activityId}`, { body: activityData });
    }

    async deleteActivity(activityId) {
        return this.request('DELETE', `/api/activities/${activityId}`);
    }

    async cancelActivitySignup(activityId) {
        return this.request('POST', `/api/activities/${activityId}/cancel`);
    }
}

// ==================== 模块导出 ====================

/** 导出API客户端类供实例化 */
export { ApiClient };

/** 导出自定义错误类，方便外部做instanceof判断 */
export { ApiError };

/** 导出错误码映射表，供外部扩展或参考 */
export { ERROR_CODE_MAP };

/** 导出API客户端单例实例，供各页面直接使用 */
const api = new ApiClient();
export { api };

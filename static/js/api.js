/*
 * API客户端
 * 所有后端接口调用都走这，统一超时、错误处理、降级逻辑
 * 基于原生fetch + AbortController
 */

const REQUEST_TIMEOUT_MS = 30_000;

// 后端定义的业务错误码 → 中文提示
const ERROR_CODE_MAP = Object.freeze({
    E001: { message: '图片格式无效，请上传JPG/PNG格式的图片', status: 400 },
    E002: { message: '模型未就绪，请稍后重试或联系管理员', status: 503 },
    E004: { message: '请求的资源不存在', status: 404 },
    E005: { message: '操作过于频繁，请稍后再试', status: 429 },
    E003: { message: 'AI推理过程出错，请稍后重试', status: 500 },
    E006: { message: '服务器繁忙，请稍后重试', status: 500 }
});

// API异常，比原生Error多了code和statusCode
class ApiError extends Error {
    constructor(code, message, statusCode = 0, rawResponse = null) {
        super(message);
        this.code = code;
        this.statusCode = statusCode;
        this.rawResponse = rawResponse;
        this.name = 'ApiError';
    }
}

class ApiClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
        this.timeout = REQUEST_TIMEOUT_MS;
    }

    // 通用请求方法，所有业务方法的底层
    async request(method, path, options = {}) {
        const url = `${this.baseURL}${path}`;
        const reqTimeout = options.timeout || this.timeout;

        const controller = new AbortController();
        const timerId = setTimeout(() => controller.abort(), reqTimeout);

        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        const init = {
            method,
            headers,
            signal: controller.signal,
            credentials: 'include'
        };

        // GET/HEAD不带body
        if (options.body && !['GET', 'HEAD'].includes(method.toUpperCase())) {
            init.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, init);
            clearTimeout(timerId);

            // 解析JSON，不管成功失败都要读
            let responseData;
            try {
                responseData = await response.json();
            } catch (parseErr) {
                // 返回了HTML之类的非JSON内容
                responseData = {
                    success: false,
                    error: { code: 'E006', message: `服务器返回非JSON数据(HTTP ${response.status})` }
                };
            }

            if (!response.ok) {
                return this._parseErrorResponse(response, responseData);
            }

            // 2xx：优先取data/result字段，兼容裸数据
            if (responseData.data !== undefined) return responseData.data;
            if (responseData.result !== undefined) return responseData.result;
            return responseData;

        } catch (err) {
            clearTimeout(timerId);

            if (err.name === 'AbortError') {
                throw new ApiError('TIMEOUT', '请求超时，请稍后重试', 0, null);
            }

            // TypeError一般是网络断了、DNS失败、CORS拦截
            if (err instanceof TypeError) {
                throw new ApiError('NETWORK', '网络连接失败，请检查后端服务是否启动', 0, null);
            }

            throw new ApiError('UNKNOWN', err.message || '未知网络错误', 0, null);
        }
    }

    // 处理4xx/5xx响应，从响应体提取业务错误码
    _parseErrorResponse(response, responseData) {
        const status = response.status;

        // 401单独处理，不输出红色error日志
        if (status === 401) {
            const serverMsg = responseData?.error?.message || '';
            const serverCode = responseData?.error?.code || 'UNAUTH';

            if (serverMsg && serverMsg !== 'Unauthorized') {
                throw new ApiError(serverCode, serverMsg, status, response);
            }

            throw new ApiError('UNAUTH', '未授权，请先登录', status, response);
        }

        // 422 FastAPI验证错误格式
        if (status === 422) {
            const detail = responseData?.detail;
            if (Array.isArray(detail) && detail.length > 0) {
                const firstError = detail[0];
                const field = Array.isArray(firstError.loc)
                    ? firstError.loc[firstError.loc.length - 1]
                    : '字段';
                const msg = firstError.msg || '参数格式错误';
                throw new ApiError(
                    'VALIDATION_ERROR',
                    `${field}: ${msg}`,
                    status,
                    response
                );
            }

            const fallbackMsg = responseData?.detail
                ? JSON.stringify(responseData.detail)
                : '请求参数有误，请检查输入后重试';
            throw new ApiError('VALIDATION_ERROR', fallbackMsg, status, response);
        }

        // 尝试匹配预定义的错误码
        const serverCode = responseData?.error?.code || '';
        const serverMsg = responseData?.error?.message || '';

        const mapped = ERROR_CODE_MAP[serverCode];

        if (mapped) {
            throw new ApiError(serverCode, mapped.message, status, response);
        }

        // 未知错误码，用服务端消息或根据状态码生成兜底提示
        const fallbackMessage = serverMsg || this._statusFallbackMsg(status);
        throw new ApiError(serverCode || `HTTP_${status}`, fallbackMessage, status, response);
    }

    // 根据HTTP状态码生成兜底错误消息
    _statusFallbackMsg(status) {
        if (status >= 400 && status < 500) {
            return `请求参数有误（HTTP ${status}），请检查输入后重试`;
        }
        if (status >= 500) {
            return `服务器内部错误（HTTP ${status}），请稍后重试`;
        }
        return `请求失败（HTTP ${status}）`;
    }

    /* ---- 识别相关 ---- */

    // AI垃圾识别，上传base64图片
    async predict(imageBase64) {
        if (!imageBase64 || typeof imageBase64 !== 'string') {
            throw new ApiError('E001', '图片数据不能为空', 400);
        }

        return this.request('POST', '/api/predict', {
            body: { image: imageBase64 },
            timeout: 45_000 // 识别比较慢，给长一点
        });
    }

    // 搜索垃圾分类
    async search(query) {
        if (!query || typeof query !== 'string') {
            throw new ApiError('E001', '搜索关键词不能为空', 400);
        }

        return this.request('GET', `/api/search?query=${encodeURIComponent(query.trim())}`);
    }

    // 获取全量分类目录
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

    // 批量识别，一次传多张图
    async batchPredict(images) {
        if (!Array.isArray(images) || images.length === 0) {
            throw new ApiError('E001', '图片列表不能为空', 400);
        }

        if (images.length > 5) {
            throw new ApiError('E005', '单次最多上传5张图片', 429);
        }

        return this.request('POST', '/api/batch_predict', {
            body: { images },
            timeout: 120_000
        });
    }

    // 降级接口：主模型挂了的时候用特征分析凑合一下
    async analyzeFallback(imageBase64) {
        if (!imageBase64 || typeof imageBase64 !== 'string') {
            throw new ApiError('E001', '图片数据不能为空', 400);
        }

        return this.request('POST', '/api/debug/analyze', {
            body: { image: imageBase64 },
            timeout: 20_000
        });
    }

    /* ---- 历史记录 ---- */

    async getHistory(page = 1, pageSize = 20) {
        return this.request('GET', `/api/history?page=${page}&page_size=${pageSize}`);
    }

    async deleteHistoryRecord(id) {
        return this.request('DELETE', `/api/history/${encodeURIComponent(id)}`);
    }

    async clearAllHistory() {
        return this.request('DELETE', '/api/history');
    }

    /* ---- 用户认证 ---- */

    async register(username, password, nickname = '') {
        return this.request('POST', '/api/auth/register', {
            body: { username, password, nickname }
        });
    }

    // 登录后服务端Set-Cookie，后续请求自动带
    async login(username, password, remember = false) {
        return this.request('POST', '/api/auth/login', {
            body: { username, password, remember }
        });
    }

    // MVP阶段验证码直接返回，上线后走短信
    async sendSmsCode(phone) {
        return this.request('POST', '/api/auth/sms-code', {
            body: { phone }
        });
    }

    // 手机号未注册会自动创建账号
    async phoneLogin(phone, code) {
        return this.request('POST', '/api/auth/phone-login', {
            body: { phone, code }
        });
    }

    async logout() {
        return this.request('POST', '/api/auth/logout');
    }

    // 获取当前登录用户信息，未登录会401
    async getMe() {
        return this.request('GET', '/api/auth/me');
    }

    /* ---- 投放点 ---- */

    async getDisposalPoints(zone = '', category = '') {
        const params = new URLSearchParams();
        if (zone) params.set('zone', zone);
        if (category) params.set('category', category);
        return this.request('GET', `/api/map/points?${params.toString()}`);
    }

    async getDisposalPoint(pointId) {
        return this.request('GET', `/api/map/point/${pointId}`);
    }

    /* ---- 打卡 ---- */

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

    /* ---- 问答 ---- */

    async getDailyQuiz() {
        return this.request('GET', '/api/quiz/daily');
    }

    async answerQuiz(questionId, selected) {
        return this.request('POST', '/api/quiz/answer', {
            body: { question_id: questionId, selected }
        });
    }

    /* ---- 活动 ---- */

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

    /* ---- 成就与积分 ---- */

    async getAchievements() {
        return this.request('GET', '/api/achievements');
    }

    async getPointsHistory(page = 1, pageSize = 20) {
        return this.request('GET', `/api/points/history?page=${page}&page_size=${pageSize}`);
    }

    /* ---- 数据统计 ---- */

    async getStatsSummary() {
        return this.request('GET', '/api/stats/summary');
    }

    async getLeaderboard(type = 'points', limit = 10) {
        return this.request('GET', `/api/stats/leaderboard?type=${type}&limit=${limit}`);
    }

    async updateUserSettings(settings) {
        return this.request('PUT', '/api/auth/settings', { body: settings });
    }

    /* ---- 管理后台 ---- */

    async adminLogin(username, password) {
        return this.request('POST', '/api/admin/login', { body: { username, password } });
    }

    async adminCheck() {
        return this.request('GET', '/api/admin/check');
    }

    async adminGetDashboard() {
        return this.request('GET', '/api/admin/stats/dashboard');
    }

    async adminGetUsers(page = 1, search = '', role = '') {
        return this.request('GET', `/api/admin/users?page=${page}&search=${encodeURIComponent(search)}&role=${role}`);
    }

    async adminGetUser(userId) {
        return this.request('GET', `/api/admin/users/${userId}`);
    }

    async adminUpdateUserStatus(userId, status) {
        return this.request('PUT', `/api/admin/users/${userId}/status`, { body: { status } });
    }

    async adminUpdateUserRole(userId, role) {
        return this.request('PUT', `/api/admin/users/${userId}/role`, { body: { role } });
    }

    async adminGetVocabulary() {
        return this.request('GET', '/api/admin/content/vocabulary');
    }

    async adminUpdateVocabulary(items) {
        return this.request('PUT', '/api/admin/content/vocabulary', { body: { items } });
    }

    async adminGetCategories() {
        return this.request('GET', '/api/admin/content/categories');
    }

    async adminUpdateCategories(data) {
        return this.request('PUT', '/api/admin/content/categories', { body: data });
    }

    async adminGetPoints() {
        return this.request('GET', '/api/admin/points');
    }

    async adminCreatePoint(data) {
        return this.request('POST', '/api/admin/points', { body: data });
    }

    async adminUpdatePoint(id, data) {
        return this.request('PUT', `/api/admin/points/${id}`, { body: data });
    }

    async adminDeletePoint(id) {
        return this.request('DELETE', `/api/admin/points/${id}`);
    }

    async adminGetModels() {
        return this.request('GET', '/api/admin/models');
    }

    async adminSwitchModel(modelId) {
        return this.request('PUT', `/api/admin/models/${modelId}/switch`, { body: { model_id: modelId } });
    }

    async adminGetBadcases() {
        return this.request('GET', '/api/admin/models/badcases');
    }

    async adminGetBadcasesByModel(modelId) {
        return this.request('GET', `/api/admin/models/${modelId}/badcases`);
    }

    async adminDeleteBadcase(badcaseId) {
        return this.request('DELETE', `/api/admin/models/badcases/${badcaseId}`);
    }

    async adminUpdateActivity(id, data) {
        return this.request('PUT', `/api/admin/activities/${id}`, { body: data });
    }

    async adminCreateActivity(data) {
        return this.request('POST', '/api/admin/activities', { body: data });
    }

    async adminDeleteActivity(id) {
        return this.request('DELETE', `/api/admin/activities/${id}`);
    }

    async adminGetActivitySignups(id) {
        return this.request('GET', `/api/admin/activities/${id}/signups`);
    }

    async adminAddVocabularyItem(item) {
        return this.request('POST', '/api/admin/content/vocabulary/item', { body: item });
    }

    async adminDeleteVocabularyItem(label) {
        return this.request('DELETE', `/api/admin/content/vocabulary/item/${encodeURIComponent(label)}`);
    }

    async adminGetConfusingPairs() {
        return this.request('GET', '/api/admin/content/confusing');
    }

    async adminAddConfusingPair(data) {
        return this.request('POST', '/api/admin/content/confusing', { body: data });
    }

    async adminDeleteConfusingPair(pairId) {
        return this.request('DELETE', `/api/admin/content/confusing/${pairId}`);
    }
}

export { ApiClient };
export { ApiError };
export { ERROR_CODE_MAP };

const api = new ApiClient();
export { api };

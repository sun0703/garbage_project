/**
 * HTML 安全工具模块
 * 提供统一的 XSS 防护函数，避免各组件重复实现 HTML 转义逻辑
 */

/**
 * HTML 特殊字符转义，防止 XSS 注入
 * 使用 DOM textContent 方式（最安全且性能最佳）
 *
 * @param {*} str - 需要转义的值（推荐传入string，支持null/undefined/number/object等类型）
 * @returns {string} 转义后的安全字符串
 * @description 处理规则：
 *   - null/undefined → 返回空字符串（console.warn提示）
 *   - 非字符串类型 → 强制转换为String()后转义
 *   - 正常字符串 → 使用DOM textContent方式安全转义
 *
 * @example
 * escapeHtml(null)          // ''
 * escapeHtml(undefined)     // ''
 * escapeHtml(123)           // '123'
 * escapeHtml({a:1})         // '[object Object]'
 * escapeHtml('<script>')    // '&lt;script&gt;'
 */
export function escapeHtml(str) {
    if (str === null || str === undefined) {
        console.warn('[escapeHtml] 收到 null/undefined 参数，返回空字符串');
        return '';
    }
    if (typeof str !== 'string') {
        str = String(str);
    }
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * 从 URL 参数中安全提取字符串值（自动转义防 XSS）
 *
 * @param {URLSearchParams} params - 查询参数对象
 * @param {string} key - 参数名
 * @param {string} [defaultVal=''] - 默认值
 * @returns {string} 转义后的安全字符串
 */
export function safeQueryParam(params, key, defaultVal = '') {
    const raw = params.get(key);
    return raw ? escapeHtml(raw) : defaultVal;
}

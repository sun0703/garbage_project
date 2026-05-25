/**
 * HTML 安全工具模块
 * 提供统一的 XSS 防护函数，避免各组件重复实现 HTML 转义逻辑
 */

/**
 * HTML 特殊字符转义，防止 XSS 注入
 * 使用 DOM textContent 方式（最安全且性能最佳）
 *
 * @param {string} str - 需要转义的字符串
 * @returns {string} 转义后的安全字符串
 */
export function escapeHtml(str) {
    if (typeof str !== 'string') return '';
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

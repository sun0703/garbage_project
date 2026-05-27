// HTML安全工具 — XSS防护，各组件共用

// 用DOM textContent方式转义，最安全也最快
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

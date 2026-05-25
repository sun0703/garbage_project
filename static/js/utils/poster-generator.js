/**
 * @fileoverview 打卡分享海报生成器 - CheckinPosterGenerator
 * @description 使用 Canvas API 生成精美的打卡分享海报
 *              支持自定义背景、用户信息、统计数据展示
 *
 * @module utils/poster-generator
 * @example
 * import { generatePoster } from './poster-generator.js';
 * const posterUrl = await generatePoster(posterData);
 */

/**
 * 海报生成配置
 * @typedef {Object} PosterConfig
 * @property {number} width - 海报宽度（默认 750）
 * @property {number} height - 海报高度（默认 1334，适配手机屏幕）
 */

/**
 * 海报数据结构
 * @typedef {Object} PosterData
 * @property {Object} user - 用户信息
 * @property {string} user.nickname - 用户昵称
 * @property {string} user.avatar - 头像 URL
 * @property {number} user.points - 积分
 * @property {number} user.level - 等级
 * @property {string} user.level_name - 等级名称
 * @property {string} user.level_icon - 等级图标
 * @property {Object} checkin - 打卡信息
 * @property {number} checkin.consecutive_days - 连续打卡天数
 * @property {number} checkin.points_earned - 本次获得积分
 * @property {Object} stats - 统计数据
 * @property {number} stats.total_checkins - 总打卡次数
 * @property {number} stats.rank - 排名
 * @property {Object} poster_config - 海报配置
 * @property {string} poster_config.slogan - 鼓励语
 * @property {string} poster_config.date_text - 日期文本
 * @property {string[]} poster_config.background_gradient - 背景渐变色
 */

// 默认配置
const DEFAULT_CONFIG = {
    width: 750,
    height: 1334,
    padding: 40,
};

// 颜色主题
const THEMES = {
    green: {
        primary: '#2D9B5E',
        secondary: '#1a7343',
        accent: '#FFD700',
        text: '#FFFFFF',
        textSecondary: 'rgba(255,255,255,0.85)',
        cardBg: 'rgba(255,255,255,0.15)',
        cardBorder: 'rgba(255,255,255,0.25)',
    },
    blue: {
        primary: '#4A90D9',
        secondary: '#2E6BB0',
        accent: '#64B5F6',
        text: '#FFFFFF',
        textSecondary: 'rgba(255,255,255,0.85)',
        cardBg: 'rgba(255,255,255,0.15)',
        cardBorder: 'rgba(255,255,255,0.25)',
    },
};

/**
 * 生成打卡分享海报
 *
 * @param {PosterData} data - 海报数据（来自 API /api/checkin/poster）
 * @param {Partial<PosterConfig>} [options] - 可选配置覆盖
 * @returns {Promise<string>} 返回 Base64 编码的 PNG 图片 URL
 */
export async function generatePoster(data, options = {}) {
    const config = { ...DEFAULT_CONFIG, ...options };
    const theme = THEMES.green;

    // 创建 Canvas
    const canvas = document.createElement('canvas');
    canvas.width = config.width;
    canvas.height = config.height;
    const ctx = canvas.getContext('2d');

    // 设备像素比优化（高清屏支持）
    const dpr = window.devicePixelRatio || 1;
    if (dpr > 1) {
        canvas.width *= dpr;
        canvas.height *= dpr;
        canvas.style.width = `${config.width}px`;
        canvas.style.height = `${config.height}px`;
        ctx.scale(dpr, dpr);
    }

    try {
        // ===== 1. 绘制背景渐变 =====
        _drawBackground(ctx, config, theme, data.poster_config);

        // ===== 2. 绘制装饰元素 =====
        _drawDecorations(ctx, config, theme);

        // ===== 3. 绘制头部区域（Logo + 标题）=====
        _drawHeader(ctx, config, theme, data.poster_config);

        // ===== 4. 绘制主卡片区域 =====
        await _drawMainCard(ctx, config, theme, data);

        // ===== 5. 绘制统计区域 =====
        _drawStatsSection(ctx, config, theme, data.stats);

        // ===== 6. 绘制底部信息 =====
        _drawFooter(ctx, config, theme, data.poster_config);

        return canvas.toDataURL('image/png', 1.0);
    } catch (error) {
        console.error('[PosterGenerator] 海报生成失败:', error);
        throw error;
    }
}

/**
 * 绘制背景渐变
 */
function _drawBackground(ctx, config, theme, posterConfig) {
    const gradient = ctx.createLinearGradient(0, 0, 0, config.height);

    // 使用 API 返回的渐变色或默认值
    const colors = posterConfig?.background_gradient || [theme.primary, theme.secondary];
    gradient.addColorStop(0, colors[0]);
    gradient.addColorStop(1, colors[1]);

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, config.width, config.height);

    // 添加噪点纹理效果（模拟质感）
    _addNoiseTexture(ctx, config.width, config.height, 0.03);
}

/**
 * 添加噪点纹理
 */
function _addNoiseTexture(ctx, width, height, opacity) {
    const imageData = ctx.getImageData(0, 0, width, height);
    const pixels = imageData.data;

    for (let i = 0; i < pixels.length; i += 4) {
        const noise = (Math.random() - 0.5) * 255 * opacity;
        pixels[i] += noise;     // R
        pixels[i + 1] += noise; // G
        pixels[i + 2] += noise; // B
    }

    ctx.putImageData(imageData, 0, 0);
}

/**
 * 绘制装饰元素（圆形、线条等）
 */
function _drawDecorations(ctx, config, theme) {
    ctx.save();

    // 右上角大圆装饰
    ctx.beginPath();
    ctx.arc(config.width + 50, -30, 200, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.06)';
    ctx.fill();

    // 左下角圆形装饰
    ctx.beginPath();
    ctx.arc(-80, config.height + 100, 250, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.04)';
    ctx.fill();

    // 中间偏右的装饰圆环
    ctx.beginPath();
    ctx.arc(config.width - 60, config.height * 0.45, 120, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // 小圆点装饰
    for (let i = 0; i < 8; i++) {
        const x = Math.random() * config.width;
        const y = Math.random() * config.height;
        const r = Math.random() * 6 + 2;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,215,0,${Math.random() * 0.15 + 0.05})`;
        ctx.fill();
    }

    ctx.restore();
}

/**
 * 绘制头部区域
 */
function _drawHeader(ctx, config, theme, posterConfig) {
    const y = 70;

    // 应用名称
    ctx.font = "bold 28px -apple-system, 'PingFang SC', sans-serif";
    ctx.fillStyle = theme.text;
    ctx.textAlign = 'center';
    ctx.fillText(posterConfig?.app_name || '校园垃圾分类AI助手', config.width / 2, y);

    // 副标题/日期
    ctx.font = "16px -apple-system, 'PingFang SC', sans-serif";
    ctx.fillStyle = theme.textSecondary;
    ctx.fillText(posterConfig?.date_text || '', config.width / 2, y + 35);
}

/**
 * 绘制主卡片（用户信息 + 打卡详情）
 */
async function _drawMainCard(ctx, config, theme, data) {
    const cardX = config.padding;
    const cardY = 140;
    const cardW = config.width - config.padding * 2;
    const cardH = 420;

    // 卡片背景（半透明毛玻璃效果）
    ctx.save();
    _roundRect(ctx, cardX, cardY, cardW, cardH, 24);
    ctx.fillStyle = theme.cardBg;
    ctx.fill();

    // 卡片边框
    ctx.strokeStyle = theme.cardBorder;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();

    let currentY = cardY + 45;

    // ---- 用户头像区域 ----
    await _drawAvatar(ctx, theme, data.user, cardX, currentY, cardW);

    currentY += 110;

    // ---- 昵称和等级 ----
    ctx.font = "bold 32px -apple-system, 'PingFang SC', sans-serif";
    ctx.fillStyle = theme.text;
    ctx.textAlign = 'center';
    ctx.fillText(data.user.nickname || '环保达人', config.width / 2, currentY);

    currentY += 40;

    // 等级标签
    const levelText = `${data.user.level_icon || ''} ${data.user.level_name || '环保新人'}`;
    const levelWidth = ctx.measureText(levelText).width + 40;
    _drawPillTag(
        ctx,
        (config.width - levelWidth) / 2,
        currentY - 15,
        levelWidth,
        32,
        levelText,
        theme.accent,
        '#333'
    );

    currentY += 55;

    // ---- 鼓励语（Slogan）----
    ctx.font = "bold 26px -apple-system, 'PingFang SC', sans-serif";
    ctx.fillStyle = theme.accent;
    ctx.fillText(data.poster_config?.slogan || '今日份环保打卡 ✓', config.width / 2, currentY);

    currentY += 50;

    // ---- 分割线 ----
    ctx.beginPath();
    ctx.moveTo(cardX + 40, currentY);
    ctx.lineTo(cardX + cardW - 40, currentY);
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 1;
    ctx.stroke();

    currentY += 35;

    // ---- 打卡数据网格 ----
    _drawDataGrid(ctx, config, theme, [
        { label: '连续打卡', value: `${data.checkin?.consecutive_days || 1}天`, icon: '🔥' },
        { label: '本次积分', value: `+${data.checkin?.points_earned || 5}`, icon: '⭐' },
        { label: '总积分', value: `${data.stats?.user_points || 0}`, icon: '💎' },
    ], cardX, currentY, cardW);
}

/**
 * 绘制头像（带边框和加载处理）
 */
async function _drawAvatar(ctx, theme, user, cardX, y, cardW) {
    const centerX = cardX + cardW / 2;
    const avatarSize = 90;
    const avatarX = centerX - avatarSize / 2;
    const avatarY = y;

    // 外圈光晕
    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, avatarY + avatarSize / 2, avatarSize / 2 + 8, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,215,0,0.25)';
    ctx.fill();
    ctx.restore();

    // 头像圆形裁剪区域
    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, avatarY + avatarSize / 2, avatarSize / 2, 0, Math.PI * 2);
    ctx.clip();

    try {
        // 尝试加载真实头像
        if (user.avatar && !user.avatar.includes('default')) {
            const img = await _loadImage(user.avatar);
            ctx.drawImage(img, avatarX, avatarY, avatarSize, avatarSize);
        } else {
            // 默认头像：绘制首字母或 emoji
            _drawDefaultAvatar(ctx, centerX, avatarY + avatarSize / 2, avatarSize, user.nickname);
        }
    } catch (e) {
        // 加载失败时使用默认头像
        _drawDefaultAvatar(ctx, centerX, avatarY + avatarSize / 2, avatarSize, user.nickname);
    }

    ctx.restore();

    // 头像边框
    ctx.beginPath();
    ctx.arc(centerX, avatarY + avatarSize / 2, avatarSize / 2, 0, Math.PI * 2);
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 3;
    ctx.stroke();
}

/**
 * 绘制默认头像（首字母/emoji）
 */
function _drawDefaultAvatar(ctx, cx, cy, size, nickname) {
    // 渐变背景
    const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
    gradient.addColorStop(0, '#667eea');
    gradient.addColorStop(1, '#764ba2');

    ctx.beginPath();
    ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // 首字母
    const initial = (nickname || '?').charAt(0).toUpperCase();
    ctx.font = `bold ${size * 0.45}px -apple-system, sans-serif`;
    ctx.fillStyle = '#FFFFFF';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(initial, cx, cy + 2);
}

/**
 * 绘制胶囊标签
 */
function _drawPillTag(ctx, x, y, w, h, text, bgColor, textColor) {
    ctx.save();
    _roundRect(ctx, x, y, w, h, h / 2);
    ctx.fillStyle = bgColor;
    ctx.fill();

    ctx.font = `bold ${h * 0.48}px -apple-system, sans-serif`;
    ctx.fillStyle = textColor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x + w / 2, y + h / 2 + 1);
    ctx.restore();
}

/**
 * 绘制数据网格（三列）
 */
function _drawDataGrid(ctx, config, theme, items, cardX, y, cardW) {
    const colWidth = (cardW - 80) / items.length;
    const startX = cardX + 40;

    items.forEach((item, index) => {
        const x = startX + colWidth * index + colWidth / 2;

        // 图标
        ctx.font = "36px sans-serif";
        ctx.textAlign = 'center';
        ctx.fillText(item.icon || '', x, y + 10);

        // 数值
        ctx.font = "bold 30px -apple-system, sans-serif";
        ctx.fillStyle = theme.text;
        ctx.fillText(item.value || '', x, y + 52);

        // 标签
        ctx.font = "14px -apple-system, sans-serif";
        ctx.fillStyle = theme.textSecondary;
        ctx.fillText(item.label || '', x, y + 78);
    });
}

/**
 * 统计区域
 */
function _drawStatsSection(ctx, config, theme, stats) {
    const sectionY = 600;
    const cardX = config.padding;
    const cardW = config.width - config.padding * 2;
    const cardH = 180;

    // 半透明卡片
    ctx.save();
    _roundRect(ctx, cardX, sectionY, cardW, cardH, 20);
    ctx.fillStyle = theme.cardBg;
    ctx.fill();
    ctx.strokeStyle = theme.cardBorder;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();

    // 标题
    ctx.font = "bold 22px -apple-system, sans-serif";
    ctx.fillStyle = theme.text;
    ctx.textAlign = 'left';
    ctx.fillText('📊 我的环保成就', cardX + 30, sectionY + 42);

    // 两列数据
    const statsItems = [
        { label: '累计打卡', value: `${stats?.total_checkins || 0} 次`, color: '#4CAF50' },
        { label: '环保排名', value: `第 ${stats?.rank || '-'} 名`, color: '#FFD700' },
        { label: '累计获得', value: `${stats?.total_points_earned || 0} 积分`, color: '#64B5F6' },
    ];

    const itemHeight = 44;
    statsItems.forEach((item, i) => {
        const itemY = sectionY + 65 + i * itemHeight;

        // 彩色指示条
        ctx.fillStyle = item.color;
        _roundRect(ctx, cardX + 30, itemY - 14, 4, 22, 2);
        ctx.fill();

        // 标签
        ctx.font = "17px -apple-system, sans-serif";
        ctx.fillStyle = theme.textSecondary;
        ctx.textAlign = 'left';
        ctx.fillText(item.label, cardX + 46, itemY + 2);

        // 数值
        ctx.font = "bold 18px -apple-system, sans-serif";
        ctx.fillStyle = theme.text;
        ctx.textAlign = 'right';
        ctx.fillText(item.value, cardX + cardW - 30, itemY + 2);
    });
}

/**
 * 底部信息
 */
function _drawFooter(ctx, config, theme, posterConfig) {
    const footerY = config.height - 90;

    // 二维码占位区域（实际项目中可替换为真实二维码）
    ctx.save();
    const qrSize = 70;
    const qrX = config.width / 2 - qrSize / 2;
    _roundRect(ctx, qrX, footerY, qrSize, qrSize, 10);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();

    // 二维码内部图案（简化版）
    ctx.fillStyle = '#333';
    const patternSize = 8;
    const padding = 12;
    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            if ((row + col) % 2 === 0 || (row === 2 && col === 2)) {
                ctx.fillRect(
                    qrX + padding + col * patternSize,
                    footerY + padding + row * patternSize,
                    patternSize - 2,
                    patternSize - 2
                );
            }
        }
    }
    ctx.restore();

    // 提示文字
    ctx.font = "13px -apple-system, sans-serif";
    ctx.fillStyle = theme.textSecondary;
    ctx.textAlign = 'center';
    ctx.fillText('长按识别二维码，一起参与垃圾分类', config.width / 2, footerY + qrSize + 25);

    // 版权信息
    ctx.font = "11px -apple-system, sans-serif";
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.fillText('© 2026 校园垃圾分类AI助手 · 让分类更简单', config.width / 2, config.height - 20);
}

/**
 * 圆角矩形辅助函数
 */
function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

/**
 * 图片加载 Promise 包装
 */
function _loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous'; // 允许跨域
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
        // 超时处理
        setTimeout(() => reject(new Error('图片加载超时')), 5000);
    });
}

/**
 * 下载海报到本地
 *
 * @param {string} posterBase64 - 海报 Base64 URL
 * @param {string} [filename='checkin-poster.png'] - 文件名
 */
export async function downloadPoster(posterBase64, filename = 'checkin-poster.png') {
    try {
        // 将 Base64 转为 Blob
        const response = await fetch(posterBase64);
        const blob = await response.blob();

        // 创建下载链接
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // 清理内存
        URL.revokeObjectURL(url);

        console.log('[PosterGenerator] 海报下载成功');
        return true;
    } catch (error) {
        console.error('[PosterGenerator] 海报下载失败:', error);
        return false;
    }
}

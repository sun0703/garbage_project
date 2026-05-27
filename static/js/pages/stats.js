import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';

const ACHIEVEMENT_DEFINITIONS = [
    {
        id: 'first_prediction',
        name: '初次识别',
        desc: '完成首次垃圾识别',
        icon: '🌱',
        unlocked_icon: '🌿'
    },
    {
        id: 'ten_predictions',
        name: '识别达人',
        desc: '累计识别10次垃圾',
        icon: '🔍',
        unlocked_icon: '🔎'
    },
    {
        id: 'fifty_predictions',
        name: '火眼金睛',
        desc: '累计识别50次垃圾',
        icon: '👁️',
        unlocked_icon: '👁️'
    },
    {
        id: 'first_checkin',
        name: '首次打卡',
        desc: '完成首次环保打卡',
        icon: '📍',
        unlocked_icon: '📍'
    },
    {
        id: 'seven_day_streak',
        name: '连续7天',
        desc: '连续打卡7天',
        icon: '🔥',
        unlocked_icon: '🔥'
    },
    {
        id: 'thirty_day_streak',
        name: '坚持一个月',
        desc: '连续打卡30天',
        icon: '🏆',
        unlocked_icon: '🏆'
    },
    {
        id: 'quiz_master',
        name: '答题高手',
        desc: '累计答对50道题',
        icon: '🧠',
        unlocked_icon: '🧠'
    },
    {
        id: 'points_100',
        name: '百分达人',
        desc: '积分达到100分',
        icon: '💎',
        unlocked_icon: '💎'
    }
];

export class StatsPage {
    container = null;
    _boundHandlers = {};
    _chartInstances = [];
    _unlockedAchievements = new Set();

    init() {
        this.container = document.getElementById('page-stats');
        this._render();
        this._loadData();
    }

    _render() {
        const content = this.container.querySelector('.page__content');
        content.innerHTML = `
            <div class="stats-header">
                <h2 class="stats-title">📊 数据统计</h2>
            </div>

            <div class="stats-summary-grid" id="statsSummaryGrid">
                <div class="stats-summary-card">
                    <span class="stats-summary-icon">🔍</span>
                    <span class="stats-summary-value" id="statPredictions">-</span>
                    <span class="stats-summary-label">累计识别</span>
                </div>
                <div class="stats-summary-card">
                    <span class="stats-summary-icon">📍</span>
                    <span class="stats-summary-value" id="statCheckins">-</span>
                    <span class="stats-summary-label">累计打卡</span>
                </div>
                <div class="stats-summary-card">
                    <span class="stats-summary-icon">🧠</span>
                    <span class="stats-summary-value" id="statQuizSummary">-</span>
                    <span class="stats-summary-label">答题(答对/总数)</span>
                </div>
                <div class="stats-summary-card">
                    <span class="stats-summary-icon">💎</span>
                    <span class="stats-summary-value" id="statTotalPoints">-</span>
                    <span class="stats-summary-label">总积分</span>
                </div>
            </div>

            <div class="stats-section card">
                <h3 class="stats-section-title">🏅 我的成就</h3>
                <div class="achievements-grid" id="achievementsGrid">
                    <p class="no-data">加载中...</p>
                </div>
            </div>

            <div class="stats-section card">
                <h3 class="stats-section-title">📈 近30天活跃趋势</h3>
                <div class="chart-wrap">
                    <canvas id="trendChart" height="220"></canvas>
                </div>
            </div>

            <div class="stats-section card">
                <h3 class="stats-section-title">🎯 积分来源分布</h3>
                <div class="chart-wrap chart-wrap--pie">
                    <canvas id="distChart" height="200"></canvas>
                </div>
            </div>

            <div class="stats-section card">
                <h3 class="stats-section-title">🗑️ 识别分类分布</h3>
                <div class="chart-wrap chart-wrap--pie">
                    <canvas id="categoryDistChart" height="200"></canvas>
                </div>
            </div>

            <div class="stats-section card">
                <h3 class="stats-section-title">🏆 积分排行榜</h3>
                <div class="leaderboard-list" id="leaderboardList">
                    <p class="no-data">加载中...</p>
                </div>
            </div>
        `;
    }

    async _loadData() {
        try {
            const [summaryData, lbData, achievementsData] = await Promise.all([
                api.getStatsSummary(),
                api.getLeaderboard('points', 10),
                api.getAchievements().catch(() => ({ achievements: [], unlocked: [] }))
            ]);

            const summary = summaryData.summary || summaryData;
            if (summary) {
                this._renderSummary(summary);
                this._renderTrendChart(summary.trend_30d);
                this._renderDistChart(summary.transaction_distribution);
                this._renderCategoryDistChart(summary.category_distribution);
            }

            const unlockedIds = achievementsData.unlocked || achievementsData.achievements
                ?.filter(a => a.unlocked || a.is_unlocked)
                .map(a => a.id || a.achievement_id) || [];
            this._unlockedAchievements = new Set(unlockedIds);
            this._renderAchievements(achievementsData);

            const leaderboard = lbData.leaderboard || lbData;
            if (leaderboard && leaderboard.length > 0) {
                this._renderLeaderboard(leaderboard);
            }
        } catch (e) {
            console.error('加载统计数据失败:', e);
            this._renderAchievementsFallback();
            const content = this.container.querySelector('.page__content');
            if (content) content.innerHTML = '<p class="no-data" style="padding:40px">加载统计数据失败，请先登录</p>';
        }
    }

    _renderSummary(s) {
        document.getElementById('statPredictions').textContent = s.total_predictions || 0;
        document.getElementById('statCheckins').textContent = s.total_checkins || 0;
        document.getElementById('statQuizSummary').textContent = `${s.quiz_correct || 0}/${s.quiz_total || 0}`;
        document.getElementById('statTotalPoints').textContent = s.current_points || 0;
    }

    _renderAchievements(data) {
        const grid = document.getElementById('achievementsGrid');
        if (!grid) return;

        const achievements = data.achievements || [];
        const unlockedMap = {};
        achievements.forEach(a => {
            const id = a.id || a.achievement_id;
            if (a.unlocked || a.is_unlocked) {
                unlockedMap[id] = true;
                this._unlockedAchievements.add(id);
            }
        });

        const unlockedCount = this._unlockedAchievements.size;
        const totalCount = ACHIEVEMENT_DEFINITIONS.length;

        let html = `<div class="achievements-progress"><span>${unlockedCount}/${totalCount} 已解锁</span></div>`;
        html += '<div class="achievements-grid-inner">';

        ACHIEVEMENT_DEFINITIONS.forEach(def => {
            const isUnlocked = this._unlockedAchievements.has(def.id);
            const achievementData = achievements.find(a => (a.id || a.achievement_id) === def.id);
            const progress = achievementData?.progress || 0;
            const target = achievementData?.target || 0;

            html += `
                <div class="achievement-card ${isUnlocked ? 'achievement-card--unlocked' : ''}">
                    <div class="achievement-icon">
                        ${isUnlocked ? def.unlocked_icon : def.icon}
                    </div>
                    <div class="achievement-info">
                        <span class="achievement-name">${escapeHtml(def.name)}</span>
                        <span class="achievement-desc">${escapeHtml(def.desc)}</span>
                        ${!isUnlocked && target > 0 ? `<span class="achievement-progress">${progress}/${target}</span>` : ''}
                    </div>
                    ${isUnlocked ? '<span class="achievement-badge">✓</span>' : '<span class="achievement-lock">🔒</span>'}
                </div>
            `;
        });

        html += '</div>';
        grid.innerHTML = html;
    }

    _renderAchievementsFallback() {
        const grid = document.getElementById('achievementsGrid');
        if (!grid) return;

        let html = '<div class="achievements-progress"><span>0/' + ACHIEVEMENT_DEFINITIONS.length + ' 已解锁</span></div>';
        html += '<div class="achievements-grid-inner">';

        ACHIEVEMENT_DEFINITIONS.forEach(def => {
            html += `
                <div class="achievement-card">
                    <div class="achievement-icon">${def.icon}</div>
                    <div class="achievement-info">
                        <span class="achievement-name">${escapeHtml(def.name)}</span>
                        <span class="achievement-desc">${escapeHtml(def.desc)}</span>
                    </div>
                    <span class="achievement-lock">🔒</span>
                </div>
            `;
        });

        html += '</div>';
        grid.innerHTML = html;
    }

    _renderTrendChart(trendData) {
        const canvas = document.getElementById('trendChart');
        if (!canvas || !trendData) return;

        const labels = trendData.map(d => d.date);
        const checkinData = trendData.map(d => d.checkin);
        const quizData = trendData.map(d => d.quiz);

        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: '打卡',
                        data: checkinData,
                        borderColor: '#2D9B5E',
                        backgroundColor: 'rgba(45, 155, 94, 0.08)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    },
                    {
                        label: '答题',
                        data: quizData,
                        borderColor: '#4ECDC4',
                        backgroundColor: 'rgba(78, 205, 196, 0.08)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 20, font: { size: 12 } }
                    }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } } },
                    x: { ticks: { font: { size: 10 }, maxTicksLimit: 10 } }
                },
                interaction: { intersect: false, mode: 'index' }
            }
        });
        this._chartInstances.push(chart);
    }

    _renderDistChart(dist) {
        const canvas = document.getElementById('distChart');
        if (!canvas || !dist) return;

        const typeLabels = { checkin: '打卡', quiz: '答题', prediction: '识别' };
        const colors = { checkin: '#2D9B5E', quiz: '#4ECDC4', prediction: '#FF9F43' };
        const labels = [];
        const data = [];
        const bgColors = [];

        for (const [key, label] of Object.entries(typeLabels)) {
            if (dist[key]) {
                labels.push(label);
                data.push(dist[key]);
                bgColors.push(colors[key] || '#ccc');
            }
        }

        if (labels.length === 0) {
            labels.push('暂无数据');
            data.push(1);
            bgColors.push('#e0e0e0');
        }

        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{ data, backgroundColor: bgColors, borderWidth: 2, borderColor: '#fff' }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 16, font: { size: 12 } }
                    }
                }
            }
        });
        this._chartInstances.push(chart);
    }

    _renderCategoryDistChart(dist) {
        const canvas = document.getElementById('categoryDistChart');
        if (!canvas) return;

        const catLabels = {
            '可回收物': '#007bff',
            '厨余垃圾': '#8B4513',
            '有害垃圾': '#dc3545',
            '其他垃圾': '#6c757d'
        };

        const labels = [];
        const data = [];
        const bgColors = [];

        if (dist) {
            for (const [cat, count] of Object.entries(dist)) {
                if (count > 0) {
                    labels.push(cat);
                    data.push(count);
                    bgColors.push(catLabels[cat] || '#ccc');
                }
            }
        }

        if (labels.length === 0) {
            labels.push('暂无数据');
            data.push(1);
            bgColors.push('#e0e0e0');
        }

        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{ data, backgroundColor: bgColors, borderWidth: 2, borderColor: '#fff' }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 16, font: { size: 12 } }
                    }
                }
            }
        });
        this._chartInstances.push(chart);
    }

    _renderLeaderboard(list) {
        const el = document.getElementById('leaderboardList');
        if (!el) return;

        const medals = ['🥇', '🥈', '🥉'];
        el.innerHTML = list.map((u, i) => `
            <div class="lb-row">
                <span class="lb-rank">${i < 3 ? medals[i] : `${i + 1}.`}</span>
                <span class="lb-name">${escapeHtml(u.nickname || u.username)}</span>
                <span class="lb-points">${u.points || 0} 分</span>
            </div>
        `).join('') || '<p class="no-data">暂无数据</p>';
    }

    destroy() {
        this._chartInstances.forEach(c => {
            try { c.destroy(); } catch (_) {}
        });
        this._chartInstances = [];
    }
}

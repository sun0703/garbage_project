export class AdminDashboard {
    container = null;
    _api = null;
    _chartInstances = [];

    constructor(options = {}) {
        this._api = options.api;
        this.container = options.container;
    }

    init() {
        this._render();
        this._loadData();
    }

    _render() {
        this.container.innerHTML = `
            <h2 style="font-size:20px;font-weight:700;color:var(--text-primary);margin-bottom:20px">
                📊 数据仪表盘
            </h2>

            <div class="admin-stats-grid" id="adminStatsGrid">
                ${this._renderStatCard('👥', '—', '今日活跃用户')}
                ${this._renderStatCard('📱', '—', '注册用户总数')}
                ${this._renderStatCard('🔍', '—', '今日识别次数')}
                ${this._renderStatCard('📍', '—', '今日打卡次数')}
            </div>

            <div class="dashboard-charts-row">
                <div class="admin-card dashboard-chart-card">
                    <h3 class="admin-card__title">📈 近30天活跃趋势</h3>
                    <div class="admin-chart-wrap">
                        <canvas id="adminTrendChart"></canvas>
                    </div>
                </div>

                <div class="admin-card dashboard-chart-card">
                    <h3 class="admin-card__title">🗑️ 识别分类分布</h3>
                    <div class="admin-chart-wrap admin-chart-wrap--pie">
                        <canvas id="adminCategoryChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="admin-card">
                <h3 class="admin-card__title">🏆 热门识别物品 TOP10</h3>
                <div class="hot-items-list" id="hotItemsList">
                    <p class="admin-loading">⏳ 加载中...</p>
                </div>
            </div>
        `;
    }

    _renderStatCard(icon, value, label) {
        return `
            <div class="admin-stat-card">
                <div class="admin-stat-card__icon">${icon}</div>
                <div class="admin-stat-card__value">${value}</div>
                <div class="admin-stat-card__label">${label}</div>
            </div>
        `;
    }

    async _loadData() {
        try {
            const data = await this._api.adminGetDashboard();
            this._updateStats(data);
            this._renderTrendChart(data);
            this._renderCategoryChart(data);
            this._renderHotItems(data.hot_items || data.popular_items || []);
        } catch (err) {
            console.error('[AdminDashboard] 数据加载失败:', err);
            const statsGrid = this.container.querySelector('#adminStatsGrid');
            if (statsGrid) {
                const isAuthError = err.code === 'UNAUTH' || err.statusCode === 401;
                statsGrid.innerHTML = `
                    <div style="grid-column:1/-1;text-align:center;padding:40px;color:#999">
                        ${isAuthError ? '🔒 登录已过期，请重新登录' : '⚠️ 数据加载失败，请检查后端服务'}
                    </div>
                `;
            }
        }
    }

    _updateStats(data) {
        const stats = this.container.querySelectorAll('.admin-stat-card__value');
        if (stats.length < 4) return;

        stats[0].textContent = this._fmt(data.dau ?? data.active_users ?? 0);
        stats[1].textContent = this._fmt(data.total_users ?? 0);
        stats[2].textContent = this._fmt(data.today_recognitions ?? data.today_predictions ?? 0);
        stats[3].textContent = this._fmt(data.today_checkins ?? 0);
    }

    _renderTrendChart(data) {
        const canvas = document.getElementById('adminTrendChart');
        if (!canvas) return;

        if (typeof window.Chart === 'undefined') {
            console.warn('[AdminDashboard] Chart.js 未加载，跳过图表渲染');
            return;
        }

        let labels = [];
        let values = [];
        const trend = data.trend || data.daily_trend || [];

        if (Array.isArray(trend) && trend.length > 0) {
            labels = trend.map(item => item.date || item.label || '');
            values = trend.map(item => item.count || item.value || 0);
        } else {
            labels = Array.from({ length: 30 }, (_, i) => `D${i + 1}`);
            values = Array.from({ length: 30 }, () => 0);
        }

        const chart = new window.Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '活跃用户数',
                    data: values,
                    borderColor: '#2D9B5E',
                    backgroundColor: 'rgba(45, 155, 94, 0.08)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    pointBackgroundColor: '#2D9B5E'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11 }, color: '#999', maxTicksLimit: 10 }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: { font: { size: 11 }, color: '#999' }
                    }
                }
            }
        });
        this._chartInstances.push(chart);
    }

    _renderCategoryChart(data) {
        const canvas = document.getElementById('adminCategoryChart');
        if (!canvas) return;

        if (typeof window.Chart === 'undefined') return;

        const catDist = data.category_distribution || data.category_dist || {};
        const catColors = {
            '可回收物': '#007bff',
            '厨余垃圾': '#8B4513',
            '有害垃圾': '#dc3545',
            '其他垃圾': '#6c757d'
        };

        const labels = [];
        const chartData = [];
        const bgColors = [];

        for (const [cat, count] of Object.entries(catDist)) {
            if (count > 0) {
                labels.push(cat);
                chartData.push(count);
                bgColors.push(catColors[cat] || '#ccc');
            }
        }

        if (labels.length === 0) {
            labels.push('暂无数据');
            chartData.push(1);
            bgColors.push('#e0e0e0');
        }

        const chart = new window.Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: chartData,
                    backgroundColor: bgColors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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

    _renderHotItems(items) {
        const container = document.getElementById('hotItemsList');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = '<p class="admin-empty">暂无数据</p>';
            return;
        }

        container.innerHTML = items.slice(0, 10).map((item, idx) => {
            const medals = ['🥇', '🥈', '🥉'];
            const rank = idx < 3 ? medals[idx] : `${idx + 1}.`;
            const count = item.count || item.predictions || item.times || 0;

            return `
                <div class="hot-item-row">
                    <span class="hot-item-rank">${rank}</span>
                    <span class="hot-item-name">${this._escapeHtml(item.name || item.label || item.item || '未知')}</span>
                    <span class="hot-item-category">${this._escapeHtml(item.category || '')}</span>
                    <span class="hot-item-count">${this._fmt(count)} 次</span>
                </div>
            `;
        }).join('');
    }

    _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    _fmt(n) {
        if (n === null || n === undefined) return '0';
        return Number(n).toLocaleString('zh-CN');
    }

    destroy() {
        this._chartInstances.forEach(chart => {
            try { chart.destroy(); } catch (_) {}
        });
        this._chartInstances = [];
    }
}

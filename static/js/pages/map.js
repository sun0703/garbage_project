import { store } from '../store.js';
import { api } from '../api.js';

export class MapPage {
    container = null;
    _map = null;
    _markers = [];
    _boundHandlers = {};
    _userLat = 0;
    _userLng = 0;

    init() {
        this.container = document.getElementById('page-map');
        this._render();
        this._loadMap();
        this._loadPoints();
        this._getUserLocation();
    }

    _render() {
        const content = this.container.querySelector('.page__content');
        content.innerHTML = `
            <div class="map-header">
                <h2 class="map-title">投放点地图</h2>
                <div class="map-filters">
                    <select id="mapZoneFilter" class="map-filter-select">
                        <option value="">全部区域</option>
                        <option value="西区">西区</option>
                        <option value="东区">东区</option>
                        <option value="中心区">中心区</option>
                    </select>
                    <select id="mapCatFilter" class="map-filter-select">
                        <option value="">全部分类</option>
                        <option value="可回收物">可回收物</option>
                        <option value="厨余垃圾">厨余垃圾</option>
                        <option value="有害垃圾">有害垃圾</option>
                        <option value="其他垃圾">其他垃圾</option>
                    </select>
                </div>
            </div>
            <div id="mapContainer" class="map-container"></div>
            <div id="pointList" class="point-list"></div>
        `;
    }

    _loadMap() {
        if (typeof L === 'undefined') {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);

            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = () => this._initMap();
            document.head.appendChild(script);
        } else {
            this._initMap();
        }
    }

    _initMap() {
        if (!window.L) return;
        const mapEl = document.getElementById('mapContainer');
        if (!mapEl) return;

        this._map = L.map(mapEl).setView([30.759, 103.935], 16);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap',
            maxZoom: 19
        }).addTo(this._map);

        setTimeout(() => this._map.invalidateSize(), 300);
    }

    async _loadPoints() {
        try {
            const zone = document.getElementById('mapZoneFilter')?.value || '';
            const category = document.getElementById('mapCatFilter')?.value || '';
            const data = await api.getDisposalPoints(zone, category);
            if (data.success) {
                this._renderPoints(data.points);
                this._renderMarkers(data.points);
            }
        } catch (e) {
            console.error('加载投放点失败:', e);
        }

        this._boundHandlers.filterChange = () => this._loadPoints();
        document.getElementById('mapZoneFilter')?.addEventListener('change', this._boundHandlers.filterChange);
        document.getElementById('mapCatFilter')?.addEventListener('change', this._boundHandlers.filterChange);
    }

    /**
     * 生成导航URL（根据设备类型动态选择地图应用）
     * iOS设备使用Apple Maps，Android/其他设备使用高德地图
     *
     * @param {number} lat - 目标纬度
     * @param {number} lng - 目标经度
     * @param {string} name - 目标地点名称
     * @returns {string} 导航链接URL
     * @private
     */
    _generateNavUrl(lat, lng, name) {
        /* 检测iOS设备（iPhone/iPad/iPod） */
        const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);

        if (isIOS) {
            /* iOS使用Apple Maps原生导航 */
            return `https://maps.apple.com/?daddr=${lat},${lng}`;
        } else {
            /* Android/其他设备使用高德地图Web导航 */
            return `https://uri.amap.com/navigation?to=${lng},${lat},${encodeURIComponent(name)}&mode=car`;
        }
    }

    _renderMarkers(points) {
        if (!this._map || !window.L) return;
        this._markers.forEach(m => this._map.removeLayer(m));
        this._markers = [];

        const catColors = { '可回收物': '#2196F3', '厨余垃圾': '#4CAF50', '有害垃圾': '#F44336', '其他垃圾': '#9E9E9E' };

        points.forEach(p => {
            const mainCat = p.categories?.[0] || '其他垃圾';
            const color = catColors[mainCat] || '#666';
            const icon = L.divIcon({
                className: 'custom-marker',
                html: `<div style="width:28px;height:28px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="white"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                </div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 28]
            });

            const marker = L.marker([p.lat, p.lng], { icon }).addTo(this._map);
            const catTags = p.categories.map(c => `<span class="point-cat-tag" style="background:${catColors[c] || '#666'}">${c}</span>`).join('');

            /* 生成该投放点的导航URL */
            const navUrl = this._generateNavUrl(p.lat, p.lng, p.name);

            marker.bindPopup(`
                <div class="map-popup">
                    <strong>${p.name}</strong>
                    <p class="popup-address">${p.address}</p>
                    <div class="popup-cats">${catTags}</div>
                    ${p.is_indoor ? '<span class="popup-indoor">室内</span>' : '<span class="popup-outdoor">室外</span>'}
                    <!-- F-3.1.4 导航跳转按钮 -->
                    <a href="${navUrl}" target="_blank" rel="noopener noreferrer" class="map-nav-btn">
                        🧭 导航去这里
                    </a>
                </div>
            `);
            this._markers.push(marker);
        });

        if (points.length > 0) {
            const bounds = L.latLngBounds(points.map(p => [p.lat, p.lng]));
            this._map.fitBounds(bounds, { padding: [40, 40] });
        }
    }

    _renderPoints(points) {
        const listEl = document.getElementById('pointList');
        if (!listEl) return;

        const catColors = { '可回收物': '#2196F3', '厨余垃圾': '#4CAF50', '有害垃圾': '#F44336', '其他垃圾': '#9E9E9E' };

        listEl.innerHTML = points.map(p => `
            <div class="point-card card" data-point-id="${p.id}" data-lat="${p.lat}" data-lng="${p.lng}">
                <div class="point-card-header">
                    <h3 class="point-card-name">${p.name}</h3>
                    <span class="point-card-zone">${p.campus_zone}</span>
                </div>
                <p class="point-card-address">${p.address}</p>
                <div class="point-card-cats">
                    ${p.categories.map(c => `<span class="point-cat-tag" style="background:${catColors[c] || '#666'}">${c}</span>`).join('')}
                </div>
                <div class="point-card-meta">
                    ${p.is_indoor ? '🏠 室内' : '🌳 室外'}
                </div>
            </div>
        `).join('');

        listEl.querySelectorAll('.point-card').forEach(card => {
            card.addEventListener('click', () => {
                const lat = parseFloat(card.dataset.lat);
                const lng = parseFloat(card.dataset.lng);
                const name = card.querySelector('.point-card-name')?.textContent || '投放点';
                if (this._map && lat && lng) {
                    this._map.setView([lat, lng], 18);
                    this._markers.forEach(m => {
                        const pos = m.getLatLng();
                        if (Math.abs(pos.lat - lat) < 0.0001 && Math.abs(pos.lng - lng) < 0.0001) {
                            m.openPopup();
                        }
                    });
                    /* F-3.1.4 卡片点击后延迟弹出导航选项（等待popup打开） */
                    setTimeout(() => this._showNavOptions(lat, lng, name), 300);
                }
            });
        });
    }

    /**
     * 显示导航选项弹窗（卡片点击时调用）
     * 提供多种导航方式选择：iOS使用Apple Maps、Android使用高德地图
     *
     * @param {number} lat - 目标纬度
     * @param {number} lng - 目标经度
     * @param {string} name - 目标地点名称
     * @private
     */
    _showNavOptions(lat, lng, name) {
        /* 移除已存在的导航弹窗（防止重复创建） */
        const existingModal = document.getElementById('mapNavModal');
        if (existingModal) {
            existingModal.remove();
        }

        /* 生成各平台导航URL */
        const iosUrl = `https://maps.apple.com/?daddr=${lat},${lng}`;
        const amapUrl = `https://uri.amap.com/navigation?to=${lng},${lat},${encodeURIComponent(name)}&mode=car`;

        /* 创建导航选项弹窗HTML */
        const modal = document.createElement('div');
        modal.id = 'mapNavModal';
        modal.className = 'map-nav-modal-overlay';
        modal.innerHTML = `
            <div class="map-nav-modal">
                <div class="map-nav-modal-header">
                    <h3 class="map-nav-modal-title">🧭 导航到 ${this._escapeHtml(name)}</h3>
                    <button class="map-nav-modal-close" id="mapNavCloseBtn" aria-label="关闭">✕</button>
                </div>
                <div class="map-nav-modal-body">
                    <a href="${iosUrl}" target="_blank" rel="noopener noreferrer" class="map-nav-option-btn">
                        <span class="map-nav-option-icon">🍎</span>
                        <span class="map-nav-option-text">
                            <strong>Apple 地图</strong>
                            <small>iOS设备推荐</small>
                        </span>
                    </a>
                    <a href="${amapUrl}" target="_blank" rel="noopener noreferrer" class="map-nav-option-btn">
                        <span class="map-nav-option-icon">🗺️</span>
                        <span class="map-nav-option-text">
                            <strong>高德地图</strong>
                            <small>Android/通用</small>
                        </span>
                    </a>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        /* 绑定关闭事件 */
        const closeBtn = document.getElementById('mapNavCloseBtn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this._closeNavModal());
        }
        /* 点击遮罩层也可关闭 */
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this._closeNavModal();
            }
        });

        /* 添加入场动画 */
        requestAnimationFrame(() => {
            modal.classList.add('visible');
        });
    }

    /**
     * 关闭导航选项弹窗
     * @private
     */
    _closeNavModal() {
        const modal = document.getElementById('mapNavModal');
        if (modal) {
            modal.classList.remove('visible');
            /* 等待动画完成后移除DOM */
            setTimeout(() => modal.remove(), 250);
        }
    }

    /**
     * HTML特殊字符转义（防止XSS注入）
     * @param {string} str - 需要转义的字符串
     * @returns {string} 转义后的安全字符串
     * @private
     */
    _escapeHtml(str) {
        if (typeof str !== 'string') return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
        return str.replace(/[&<>"']/g, (ch) => map[ch]);
    }

    _getUserLocation() {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(pos => {
            this._userLat = pos.coords.latitude;
            this._userLng = pos.coords.longitude;
        }, () => {});
    }

    destroy() {
        document.getElementById('mapZoneFilter')?.removeEventListener('change', this._boundHandlers.filterChange);
        document.getElementById('mapCatFilter')?.removeEventListener('change', this._boundHandlers.filterChange);
        if (this._map) {
            this._map.remove();
            this._map = null;
        }
        this._markers = [];
    }
}

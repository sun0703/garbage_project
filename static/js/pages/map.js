// 投放点地图 — Leaflet地图 + 筛选 + 导航

import { store } from '../store.js';
import { api } from '../api.js';
import { escapeHtml } from '../utils/escape.js';

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
                        <option value="朝阳区">朝阳区</option>
                        <option value="浦东新区">浦东新区</option>
                        <option value="中心区">中心区</option>
                        <option value="海淀区">海淀区</option>
                        <option value="徐汇区">徐汇区</option>
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
            <div class="map-data-notice">
                <span>📍 正在定位并搜索附近真实投放点...</span>
            </div>
            <div id="pointList" class="point-list"></div>
        `;
    }

    _loadMap() {
        if (typeof L === 'undefined') {
            /* 跟踪 CSS 和 JS 加载状态，二者就绪后才初始化地图 */
            let _cssReady = false;
            let _jsReady = false;

            const _tryInit = () => {
                if (_cssReady && _jsReady) {
                    this._initMap();
                }
            };

            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            link.onload = () => {
                _cssReady = true;
                _tryInit();
            };
            link.onerror = () => {
                _cssReady = true; /* CSS 加载失败也不阻塞，降级继续 */
                _tryInit();
            };
            document.head.appendChild(link);

            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            let _scriptLoaded = false;
            script.onload = () => {
                _scriptLoaded = true;
                clearTimeout(timeoutId);
                _jsReady = true;
                _tryInit();
            };
            document.head.appendChild(script);

            const timeoutId = setTimeout(() => {
                if (!_scriptLoaded) {
                    _jsReady = true;
                    console.warn('[MapPage] Leaflet JS 加载超时，地图不可用');
                    _tryInit();
                }
            }, 10000);
        } else {
            this._initMap();
        }
    }

    _initMap() {
        if (!window.L) return;
        const mapEl = document.getElementById('mapContainer');
        if (!mapEl) return;

        this._map = L.map(mapEl).setView([35.86, 104.19], 5);

        this._tileSources = [
            {
                name: '高德卫星混合',
                url: 'https://webst0{s}.is.autonavi.com/maptile/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scale=1&style=6',
                attribution: '&copy; <a href="https://www.amap.com/">高德地图</a>',
                options: { maxZoom: 18, subdomains: ['1', '2', '3', '4'] }
            },
            {
                name: '高德路网',
                url: 'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8',
                attribution: '&copy; 高德地图',
                options: { maxZoom: 18, subdomains: ['1', '2', '3', '4'] }
            },
            {
                name: 'CartoDB(国际备用)',
                url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                attribution: '&copy; OSM &copy; CARTO',
                options: { subdomains: 'abcd', maxZoom: 19 }
            }
        ];
        this._currentTileSourceIndex = 0;
        this._currentTileLayer = null;
        this._loadedTileCount = 0;
        this._addTileLayer();

        this._locateUser();

        setTimeout(() => { if (this._map) this._map.invalidateSize(); }, 300);
    }

    _addTileLayer() {
        if (this._currentTileLayer) {
            this._map.removeLayer(this._currentTileLayer);
            this._currentTileLayer.off();
        }

        const source = this._tileSources[this._currentTileSourceIndex];
        this._loadedTileCount = 0;

        this._currentTileLayer = L.tileLayer(source.url, source.options);

        this._currentTileLayer.on('tileload', () => {
            this._loadedTileCount++;
        });

        this._currentTileLayer.on('load', () => {
            console.log(`[MapPage] 瓦片源 "${source.name}" 加载完成，共 ${this._loadedTileCount} 张瓦片`);
        });

        this._currentTileLayer.addTo(this._map);
        console.log(`[MapPage] 使用瓦片源: ${source.name}`);

        setTimeout(() => {
            if (this._loadedTileCount === 0 && this._currentTileSourceIndex < this._tileSources.length - 1) {
                console.warn(`[MapPage] 瓦片源 "${source.name}" 超时无瓦片加载(${this._loadedTileCount}张)，切换到下一个...`);
                this._currentTileSourceIndex++;
                this._addTileLayer();
            } else if (this._loadedTileCount > 0) {
                console.log(`[MapPage] 瓦片源 "${source.name}" 正常工作，已加载 ${this._loadedTileCount} 张`);
            } else if (this._loadedTileCount === 0) {
                console.warn('[MapPage] 所有瓦片源均不可用，显示离线底图');
                this._showOfflineMap();
            }
        }, 4000);
    }

    _showOfflineMap() {
        const container = document.getElementById('mapContainer');
        if (!container || !this._map) return;
        
        const offlinePane = this._map.createPane('offlinePane');
        offlinePane.style.zIndex = 200;

        L.imageOverlay('', this._map.getBounds(), { pane: 'offlinePane' });

        const bgLayer = L.gridLayer({
            pane: 'offlinePane',
            createTile: (coords) => {
                const tile = document.createElement('div');
                tile.style.cssText = `
                    width:256px;height:256px;background:#e8ecf1;
                    display:flex;align-items:center;justify-content:center;
                    font-size:10px;color:#bbb;border:1px solid rgba(0,0,0,0.04);
                `;
                tile.innerHTML = `<span>${coords.z}/${coords.x}/${coords.y}</span>`;
                return tile;
            }
        });
        bgLayer.addTo(this._map);

        const noticeEl = document.querySelector('.map-data-notice');
        if (noticeEl) {
            noticeEl.innerHTML = '<span>⚠️ 地图瓦片加载失败（网络限制）— 坐标和投放点标记仍可正常使用 | 手机访问时地图将正常显示</span>';
            noticeEl.style.cssText += 'background:#fff3cd;color:#856404;font-weight:500;';
        }
    }

    /* 使用浏览器Geolocation API定位用户 */
    _locateUser() {
        if (!navigator.geolocation) {
            console.warn('[MapPage] 浏览器不支持地理定位');
            return;
        }

        const loadingToast = document.createElement('div');
        loadingToast.className = 'map-locating-toast';
        loadingToast.innerHTML = '<span>📍 正在定位...</span>';
        document.body.appendChild(loadingToast);

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                const accuracy = position.coords.accuracy || 0;
                console.log(`[MapPage] 定位成功: ${latitude}, ${longitude} (精度: ${Math.round(accuracy)}m)`);

                if (this._map) {
                    this._map.setView([latitude, longitude], 17);

                    if (this._userMarker) this._map.removeLayer(this._userMarker);
                    if (this._accuracyCircle) this._map.removeLayer(this._accuracyCircle);

                    this._accuracyCircle = L.circle([latitude, longitude], {
                        radius: accuracy,
                        color: '#2196F3',
                        fillColor: '#2196F3',
                        fillOpacity: 0.15,
                        weight: 1
                    }).addTo(this._map);

                    this._userMarker = L.marker([latitude, longitude], {
                        icon: L.divIcon({
                            className: 'user-location-marker',
                            html: '<div style="background:#2196F3;width:16px;height:16px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);cursor:move;"></div>',
                            iconSize: [16, 16],
                            iconAnchor: [8, 8]
                        }),
                        draggable: true
                    }).addTo(this._map);

                    const updatePopup = () => {
                        const pos = this._userMarker.getLatLng();
                        this._userMarker.bindPopup(`
                            <b>📍 我的位置</b><br>
                            <small>精度: ±${Math.round(accuracy)}m</small><br>
                            <small style="color:#888;">可拖拽蓝点校正位置</small><br>
                            <small>${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)}</small>
                        `).openPopup();
                        if (this._accuracyCircle) this._accuracyCircle.setLatLng(pos);
                    };

                    this._userMarker.on('dragend', updatePopup);
                    updatePopup();

                    this._fetchNearbyPoints(latitude, longitude);
                }

                loadingToast.remove();
            },
            (error) => {
                let errorMsg = '定位失败';
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMsg = '用户拒绝了定位请求'; break;
                    case error.POSITION_UNAVAILABLE:
                        errorMsg = '无法获取位置信息'; break;
                    case error.TIMEOUT:
                        errorMsg = '定位超时'; break;
                }
                console.warn(`[MapPage] ${errorMsg}`, error);
                loadingToast.innerHTML = `<span>⚠️ ${errorMsg}</span>`;
                setTimeout(() => loadingToast.remove(), 2000);
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            }
        );
    }

    async _fetchNearbyPoints(lat, lng) {
        this._nearbyMarkers = this._nearbyMarkers || [];

        let amapSuccess = false;
        try {
            const resp = await fetch(`/api/map/amap-nearby?lat=${lat}&lng=${lng}&radius=2000`);
            const data = await resp.json();
            if (data.success && data.points.length > 0) {
                amapSuccess = true;
                console.log(`[MapPage] 高德POI查询到 ${data.points.length} 个真实投放点`);
                data.points.forEach(p => {
                    const marker = L.marker([p.lat, p.lng], {
                        icon: L.divIcon({
                            className: 'amap-real-marker',
                            html: `<div style="background:#FF5722;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.3);"></div>`,
                            iconSize: [14, 14], iconAnchor: [7, 7]
                        })
                    }).addTo(this._map).bindPopup(`
                        <b>${p.type_label}</b><br>
                        <strong>${p.name}</strong><br>
                        <small style="color:#666">${p.address || '附近'}</small><br>
                        ${p.distance ? `<small style="color:#2196F3">距你 ${p.distance}m</small><br>` : ''}
                        <span style="color:#FF5722;font-size:11px">✅ 高德地图真实数据</span>
                    `);
                    this._nearbyMarkers.push(marker);
                });

                const noticeEl = document.querySelector('.map-data-notice');
                if (noticeEl) {
                    noticeEl.innerHTML = `<span>🔴 ${data.points.length}个真实投放点(高德地图) | 🔵 蓝点可拖拽校正</span>`;
                }
            } else if (data.success && data.points.length === 0) {
                console.log('[MapPage] 高德POI该区域暂无垃圾桶数据');
                amapSuccess = true;
            }
        } catch (e) {
            console.warn('[MapPage] 高德POI查询失败:', e.message);
        }

        if (!amapSuccess) {
            await this._fetchOsmPoints(lat, lng);
        }

        const localResp = await fetch(`/api/map/points`);
        const localData = await localResp.json();
        if (localData.success && localData.points.length > 0) {
            localData.points.forEach(p => {
                const marker = L.marker([p.lat, p.lng], {
                    icon: L.divIcon({
                        className: 'reference-marker',
                        html: `<div style="background:#9E9E9E;width:10px;height:10px;border-radius:50%;border:2px solid #fff;opacity:0.6;"></div>`,
                        iconSize: [10, 10], iconAnchor: [5, 5]
                    })
                }).addTo(this._map).bindPopup(`<b>📌 ${p.name}</b><br><small style="color:#888">参考位置（非精确）</small><br><small>${p.address}</small>`);
                this._nearbyMarkers.push(marker);
            });
        }
    }

    async _fetchOsmPoints(lat, lng) {
        const overpassQuery = `
            [out:json][timeout:15];
            (
              node["amenity"~"waste_basket|waste_disposal|recycling"](around:3000,${lat},${lng});
              way["amenity"~"waste_basket|waste_disposal|recycling"](around:3000,${lat},${lng});
            );
            out body center;
        `;

        try {
            const resp = await fetch('https://overpass-api.de/api/interpreter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'data=' + encodeURIComponent(overpassQuery)
            });
            const text = await resp.text();
            if (!text || text[0] !== '{') {
                console.warn('[MapPage] OSM返回非JSON（可能网络不可达）');
                return;
            }
            const data = JSON.parse(text);

            if (data.elements && data.elements.length > 0) {
                console.log(`[MapPage] OSM查询到 ${data.elements.length} 个真实投放点(fallback)`);
                data.elements.forEach(elem => {
                    const tags = elem.tags || {};
                    const pLat = elem.lat || (elem.center?.lat || 0);
                    const pLng = elem.lon || (elem.center?.lon || 0);
                    const name = tags.name || { waste_basket: '垃圾桶', waste_disposal: '垃圾站', recycling: '回收点' }[tags.amenity] || '投放点';
                    const typeLabel = { waste_basket: '🗑️ 垃圾桶', waste_disposal: '🏭 垃圾站', recycling: '♻️ 回收点' }[tags.amenity] || '📍 投放点';

                    const marker = L.marker([pLat, pLng], {
                        icon: L.divIcon({
                            className: 'osm-real-marker',
                            html: `<div style="background:#FF9800;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.3);"></div>`,
                            iconSize: [14, 14], iconAnchor: [7, 7]
                        })
                    }).addTo(this._map).bindPopup(`
                        <b>${typeLabel}</b><br>
                        <strong>${name}</strong><br>
                        <small style="color:#666">${tags['addr:street'] || tags['addr:housenumber'] ? (tags['addr:street']||'') + (tags['addr:housenumber']||'') : '位置未知'}</small><br>
                        <span style="color:#FF9800;font-size:11px">⚠️ OSM备选数据（高德不可用时的降级）</span>
                    `);
                    this._nearbyMarkers.push(marker);
                });

                const noticeEl = document.querySelector('.map-data-notice');
                if (noticeEl) {
                    noticeEl.innerHTML = `<span>🟠 ${data.elements.length}个投放点(OSM备选) | 🔵 蓝点可拖拽校正</span>`;
                }
            } else {
                console.log('[MapPage] 该区域OSM暂无垃圾桶数据');
                const noticeEl = document.querySelector('.map-data-notice');
                if (noticeEl) {
                    noticeEl.innerHTML = `<span>⚠️ 附近暂无垃圾桶数据 | 🔵 蓝点可拖拽校正</span>`;
                }
            }
        } catch (e) {
            console.warn('[MapPage] OSM前端查询失败:', e.message);
        }
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

    // 生成导航URL，iOS走Apple Maps，其他走高德
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
                    <strong>${escapeHtml(p.name)}</strong>
                    <p class="popup-address">${escapeHtml(p.address)}</p>
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
                    <h3 class="point-card-name">${escapeHtml(p.name)}</h3>
                    <span class="point-card-zone">${escapeHtml(p.zone)}</span>
                </div>
                <p class="point-card-address">${escapeHtml(p.address)}</p>
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

    // 导航方式选择弹窗
    _showNavOptions(lat, lng, name) {
        /* 移除已存在的导航弹窗（防止重复创建） */
        const existingModal = document.getElementById('mapNavModal');
        if (existingModal) {
            existingModal.remove();
        }

        /* 生成各平台导航URL */
        const iosUrl = `https://maps.apple.com/?daddr=${lat},${lng}`;
        const amapUrl = `https://uri.amap.com/navigation?to=${lng},${lat},${encodeURIComponent(name)}&mode=car`;

        const safeName = escapeHtml(name);

        /* 创建导航选项弹窗HTML */
        const modal = document.createElement('div');
        modal.id = 'mapNavModal';
        modal.className = 'map-nav-modal-overlay';
        modal.innerHTML = `
            <div class="map-nav-modal">
                <div class="map-nav-modal-header">
                    <h3 class="map-nav-modal-title">🧭 导航到 ${safeName}</h3>
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

    _getUserLocation() {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(pos => {
            this._userLat = pos.coords.latitude;
            this._userLng = pos.coords.longitude;
            this._renderNearestPoint();
        }, (err) => {
            console.warn('[MapPage] 获取位置失败:', err.message);
        });
    }

    /**
     * 推荐最近的投放点（需求 F-3.1.5）
     * 根据用户当前位置，计算距离最近的投放点并高亮显示
     * @private
     */
    _renderNearestPoint() {
        if (!this._userLat || !this._userLng) return;

        const listEl = document.getElementById('pointList');
        if (!listEl) return;

        // 计算每个投放点到用户的距离
        const cards = listEl.querySelectorAll('.point-card');
        let minDist = Infinity;
        let nearestCard = null;
        let nearestPoint = null;

        cards.forEach(card => {
            const lat = parseFloat(card.dataset.lat);
            const lng = parseFloat(card.dataset.lng);
            if (lat && lng) {
                const dist = this._calcDistance(this._userLat, this._userLng, lat, lng);
                card.dataset.distance = dist.toFixed(0);
                if (dist < minDist) {
                    minDist = dist;
                    nearestCard = card;
                    nearestPoint = { lat, lng, name: card.querySelector('.point-card-name')?.textContent || '投放点' };
                }
            }
        });

        // 在列表顶部插入最近投放点推荐卡片
        if (nearestCard && minDist < 5000) {
            const existing = document.getElementById('nearestPointBanner');
            if (existing) existing.remove();

            const banner = document.createElement('div');
            banner.id = 'nearestPointBanner';
            banner.className = 'nearest-point-banner card';
            banner.innerHTML = `
                <div class="nearest-point-header">
                    <span class="nearest-point-icon">📍</span>
                    <span class="nearest-point-label">离你最近</span>
                    <span class="nearest-point-dist">${minDist < 1000 ? Math.round(minDist) + 'm' : (minDist / 1000).toFixed(1) + 'km'}</span>
                </div>
                <div class="nearest-point-name">${escapeHtml(nearestPoint.name)}</div>
                <a href="${this._generateNavUrl(nearestPoint.lat, nearestPoint.lng, nearestPoint.name)}"
                   target="_blank" rel="noopener noreferrer" class="nearest-point-nav-btn">
                    🧭 导航前往
                </a>
            `;
            banner.addEventListener('click', (e) => {
                if (e.target.closest('.nearest-point-nav-btn')) return;
                if (this._map && nearestPoint.lat && nearestPoint.lng) {
                    this._map.setView([nearestPoint.lat, nearestPoint.lng], 18);
                    this._markers.forEach(m => {
                        const pos = m.getLatLng();
                        if (Math.abs(pos.lat - nearestPoint.lat) < 0.0001 && Math.abs(pos.lng - nearestPoint.lng) < 0.0001) {
                            m.openPopup();
                        }
                    });
                }
            });
            listEl.insertBefore(banner, listEl.firstChild);
        }
    }

    /**
     * 使用 Haversine 公式计算两点之间的距离（米）
     * @private
     */
    _calcDistance(lat1, lng1, lat2, lng2) {
        const R = 6371000; // 地球半径（米）
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    destroy() {
        document.getElementById('mapZoneFilter')?.removeEventListener('change', this._boundHandlers.filterChange);
        document.getElementById('mapCatFilter')?.removeEventListener('change', this._boundHandlers.filterChange);
        this._closeNavModal();
        if (this._map) {
            this._map.remove();
            this._map = null;
        }
        this._markers = [];
        this._nearbyMarkers = [];
    }
}

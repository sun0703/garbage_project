"""地图打卡接口"""

import json
import logging
import math
import time
import uuid
import httpx

import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from repositories.disposal_point_repo import DisposalPointRepository
from repositories.checkin_repo import CheckinRepository
from repositories.user_repo import UserRepository
from app.models import CheckinRequest

logger = logging.getLogger(__name__)

AMAP_KEY = os.getenv("AMAP_KEY", "")

_PI = 3.14159265358979324
_A = 6378245.0
_EE = 0.00669342162296594323


def _gcj02_to_wgs84(lng: float, lat: float) -> tuple:
    """GCJ-02(火星坐标系) → WGS-84(GPS坐标系)"""
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _PI
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * _PI)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * _PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


def _wgs84_to_gcj02(lng: float, lat: float) -> tuple:
    """WGS-84(GPS坐标系) → GCJ-02(火星坐标系)"""
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _PI
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * _PI)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * _PI)
    return lng + dlng, lat + dlat


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) + 20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * _PI) + 40.0 * math.sin(lat / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * _PI) + 320 * math.sin(lat * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) + 20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * _PI) + 40.0 * math.sin(lng / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * _PI) + 300.0 * math.sin(lng / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def _out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

router = APIRouter(tags=["地图打卡"])

# 复用 auth 模块的认证辅助函数
from routers.auth import _get_current_user


# 投放点地图

@router.get("/api/map/points")
async def get_disposal_points(zone: str = "", category: str = ""):
    """获取投放点列表，支持按校区和类别过滤"""
    try:
        all_points = DisposalPointRepository.list_all()
        points = []
        for p in all_points:
            p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
            if zone and p.get("zone") != zone:
                continue
            if category and category not in p.get("categories", []):
                continue
            points.append(p)
        return JSONResponse(content={"success": True, "points": points, "total": len(points)})
    except Exception as e:
        logger.error("获取投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点失败"}})


@router.get("/api/map/amap-nearby")
async def get_amap_nearby_bins(lat: float = Query(..., description="纬度"), lng: float = Query(..., description="经度"), radius: int = Query(2000, description="搜索半径(米)，最大50000")):
    """通过高德地图POI周边搜索API查询用户位置附近真实的垃圾桶/回收站/废品回收点"""
    try:
        if radius > 50000:
            radius = 50000
        if radius < 100:
            radius = 100

        gcj_lng, gcj_lat = _wgs84_to_gcj02(lng, lat)

        keywords = "垃圾桶|回收站|废品回收|垃圾分类|垃圾投放点|垃圾站"
        url = (
            f"https://restapi.amap.com/v5/place/around"
            f"?key={AMAP_KEY}"
            f"&location={gcj_lng},{gcj_lat}"
            f"&keywords={keywords}"
            f"&radius={radius}"
            f"&page_size=25"
            f"&sortrule=distance"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()

        if data.get("status") != "1":
            logger.warning("[高德POI] 查询失败: %s", data.get("info", "unknown"))
            return JSONResponse(content={"success": False, "error": {"code": "E503", "message": "高德地图服务暂不可用"}, "points": [], "total": 0})

        pois = data.get("pois", []) or []
        points = []
        for poi in pois:
            loc = poi.get("location", "")
            if not loc or "," not in loc:
                continue
            poi_lng, poi_lat = loc.split(",", 1)
            try:
                poi_lat_f = float(poi_lat)
                poi_lng_f = float(poi_lng)
            except ValueError:
                continue

            name = poi.get("name", "投放点")
            address = poi.get("address", "") or poi.get("pname", "") + poi.get("cityname", "") + poi.get("adname", "")
            poi_type = poi.get("type", "")
            distance = poi.get("distance", "")

            if not _is_waste_related(name, poi_type):
                continue

            category = _map_amap_category(name, poi_type)

            wgs_lng, wgs_lat = _gcj02_to_wgs84(poi_lng_f, poi_lat_f)

            points.append({
                "id": f"amap_{poi.get('id', '')}",
                "name": name,
                "lat": wgs_lat,
                "lng": wgs_lng,
                "address": address,
                "categories": [category],
                "zone": poi.get("adname", "周边"),
                "is_indoor": 0,
                "source": "amap",
                "distance": distance,
                "type_label": _map_amap_type_label(name, poi_type),
            })

        logger.info("[高德POI] 查询到 %d 个附近投放点 (lat=%s, lng=%s, r=%sm)", len(points), lat, lng, radius)
        return JSONResponse(content={"success": True, "points": points, "total": len(points), "source": "amap_poi"})
    except httpx.TimeoutException:
        logger.warning("[高德POI] 请求超时")
        return JSONResponse(content={"success": False, "error": {"code": "E504", "message": "高德地图服务超时"}, "points": [], "total": 0})
    except Exception as e:
        logger.error("[高德POI] 查询失败: %s", e)
        return JSONResponse(content={"success": False, "error": {"code": "E503", "message": f"查询失败: {str(e)}"}, "points": [], "total": 0})


def _map_amap_category(name: str, poi_type: str) -> str:
    text = (name + poi_type).lower()
    if any(k in text for k in ["回收", "废品", "再生"]):
        return "可回收物"
    if any(k in text for k in ["有害", "电池", "药品", "灯管"]):
        return "有害垃圾"
    if any(k in text for k in ["厨余", "餐厨", "湿垃圾"]):
        return "厨余垃圾"
    return "其他垃圾"


_EXCLUDE_KEYWORDS = ["奢侈品", "名表", "名包", "黄金", "珠宝", "首饰", "典当", "抵押", "贷款", "二手手机", "二手车", "房产"]
_WASTE_KEYWORDS = ["垃圾", "回收站", "废品", "分类投放", "垃圾桶", "投放点", "转运站", "环卫", "清洁", "保洁"]


def _is_waste_related(name: str, poi_type: str) -> bool:
    text = (name + poi_type).lower()
    if any(k in text for k in _EXCLUDE_KEYWORDS):
        return False
    return any(k in text for k in _WASTE_KEYWORDS)


def _map_amap_type_label(name: str, poi_type: str) -> str:
    text = (name + poi_type).lower()
    if "回收站" in text or "废品" in text:
        return "♻️ 回收站"
    if "分类" in text:
        return "🗑️ 垃圾分类点"
    if "垃圾站" in text or "转运" in text:
        return "🏭 垃圾站"
    return "🗑️ 垃圾桶"


@router.get("/api/map/nearby")
async def get_nearby_waste_points(lat: float = Query(..., description="纬度"), lng: float = Query(..., description="经度"), radius: int = Query(2000, description="搜索半径(米)")):
    """通过OSM Overpass API查询用户位置附近的真实垃圾桶/回收点"""
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:15];
        (
          node["amenity"~"waste_basket|waste_disposal|recycling"](around:{radius},{lat},{lng});
          way["amenity"~"waste_basket|waste_disposal|recycling"](around:{radius},{lat},{lng});
        );
        out body center;
        """
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(overpass_url, data={"data": query})
            text = resp.text
            if not text or text[0] != '{':
                logger.warning("[Overpass] 返回非JSON响应(长度:%d)，可能是网络不可达", len(text))
                return JSONResponse(content={"success": False, "error": {"code": "E503", "message": "OSM服务暂不可达，使用本地数据"}, "points": [], "total": 0})
            data = json.loads(text)

        elements = data.get("elements", [])
        points = []
        for elem in elements:
            tags = elem.get("tags", {})
            lat_val = elem.get("lat") or (elem.get("center") or {}).get("lat", 0)
            lng_val = elem.get("lon") or (elem.get("center") or {}).get("lon", 0)
            name = tags.get("name", tags.get("amenity", "投放点"))
            amenity_type = tags.get("amenity", "waste_basket")
            type_names = {"waste_basket": "垃圾桶", "waste_disposal": "垃圾站", "recycling": "回收点"}
            points.append({
                "id": f"osm_{elem['id']}",
                "name": name,
                "lat": lat_val,
                "lng": lng_val,
                "address": tags.get("addr:street", "附近街道"),
                "categories": [_map_osm_category(amenity_type)],
                "zone": "周边",
                "is_indoor": 0,
                "source": "osm",
                "type_label": type_names.get(amenity_type, "投放点")
            })

        logger.info("[Overpass] 查询到 %d 个附近投放点 (lat=%s, lng=%s, r=%sm)", len(points), lat, lng, radius)
        return JSONResponse(content={"success": True, "points": points, "total": len(points), "source": "osm_overpass"})
    except Exception as e:
        logger.error("OSM Overpass 查询失败: %s", e)
        return JSONResponse(content={"success": False, "error": {"code": "E503", "message": f"外部查询失败: {str(e)}"}, "points": [], "total": 0})


def _map_osm_category(amenity: str) -> str:
    mapping = {
        "waste_basket": "其他垃圾",
        "waste_disposal": "其他垃圾",
        "recycling": "可回收物"
    }
    return mapping.get(amenity, "其他垃圾")


@router.get("/api/map/point/{point_id}")
async def get_disposal_point(point_id: str):
    """获取单个投放点详情"""
    try:
        p = DisposalPointRepository.get_by_id(point_id)
        if not p:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "投放点不存在"}})
        p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
        return JSONResponse(content={"success": True, "point": p})
    except Exception as e:
        logger.error("获取投放点详情失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点详情失败"}})


# 环保打卡

@router.post("/api/checkin")
async def create_checkin(request: Request, req: CheckinRequest):
    """打卡，含位置校验和连续签到翻倍"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        if CheckinRepository.check_today_exists(user["id"]):
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "今日已打卡"}})

        # 位置校验：有投放点ID且提供了经纬度，检查500米内
        if req.point_id and req.lat and req.lng:
            point = DisposalPointRepository.get_by_id(req.point_id)
            if point:
                import math
                lat1, lng1 = math.radians(req.lat), math.radians(req.lng)
                lat2, lng2 = math.radians(point["lat"]), math.radians(point["lng"])
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
                distance = 6371000 * 2 * math.asin(math.sqrt(a))
                if distance > 500:
                    return JSONResponse(status_code=400, content={
                        "success": False,
                        "error": {"code": "E400", "message": f"距离投放点{int(distance)}米，需在500米内才能打卡"}
                    })

        # 连续签到翻倍：基础5分，3天+2，7天+5，30天+10
        consecutive_days = CheckinRepository.get_consecutive_days(user["id"], 30)
        bonus_map = {3: 2, 7: 5, 30: 10}
        bonus = 0
        for threshold, extra in sorted(bonus_map.items()):
            if consecutive_days >= threshold:
                bonus = extra
        points_earned = 5 + bonus

        checkin_id = CheckinRepository.create_checkin(
            user_id=user["id"],
            point_id=req.point_id,
            lat=req.lat,
            lng=req.lng,
            category=req.category,
            photo_hash=req.photo_hash,
            points_earned=points_earned,
        )
        if not checkin_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "打卡失败"}})

        UserRepository.add_checkin_count(user["id"], points_earned)

        streak_msg = ""
        if consecutive_days > 0:
            streak_msg = f"（连续{consecutive_days + 1}天，额外+{bonus}分）"

        return JSONResponse(content={
            "success": True,
            "checkin": {"id": checkin_id, "points_earned": points_earned, "consecutive_days": consecutive_days + 1},
            "message": f"打卡成功！获得 {points_earned} 积分{streak_msg}"
        })
    except Exception as e:
        logger.error("打卡失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "打卡失败"}})


@router.get("/api/checkin/today")
async def get_today_checkin(request: Request):
    """今日打卡状态"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        row = CheckinRepository.get_today_checkin(user["id"])
        return JSONResponse(content={"success": True, "checked_in": row is not None, "checkin": row})
    except Exception as e:
        logger.error("获取打卡状态失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡状态失败"}})


@router.get("/api/checkin/history")
async def get_checkin_history(request: Request, page: int = 1, page_size: int = 20):
    """打卡历史"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        records, total = CheckinRepository.get_history(user["id"], page, page_size)
        return JSONResponse(content={"success": True, "records": records, "total": total, "page": page})
    except Exception as e:
        logger.error("获取打卡历史失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡历史失败"}})


# 打卡海报

@router.get("/api/checkin/poster")
async def generate_checkin_poster(request: Request, checkin_id: str = Query(...)):
    """生成打卡分享海报数据，前端用Canvas绘制"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        # 查询打卡记录
        row = CheckinRepository.get_by_id_and_user(checkin_id, user["id"])
        if not row:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "打卡记录不存在"}})

        checkin = row

        # 连续打卡天数
        consecutive_days = CheckinRepository.get_consecutive_days(user["id"], 30)

        # 总统计
        total_checkins, total_points_earned = CheckinRepository.get_user_stats(user["id"])

        # 排名
        rank = UserRepository.get_rank_by_points(user.get("points", 0))

        # 日期
        from datetime import datetime
        date_text = datetime.now().strftime("%Y年%m月%d日")

        # 根据连续天数选择不同的鼓励语
        slogans = {
            1: "🌱 环保第一步，从今天开始！",
            3: "🔥 连续3天，保持住！",
            7: "⭐ 坚持一周，你是环保达人！",
            14: "💪 半个月，习惯已成自然！",
            21: "🏆 21天养成一个环保好习惯！",
            30: "🎖️ 整月坚持，环保大使就是你！",
            100: "💯 百天打卡传奇！致敬你的坚持！",
        }
        closest_day = min(slogans.keys(), key=lambda d: abs(d - consecutive_days))
        slogan = slogans[closest_day]

        # 等级
        level_thresholds = [0, 50, 200, 500, 1000]
        level_names = ["环保新人", "分类达人", "绿色先锋", "环保卫士", "环保大使"]
        level_icons = ["🌱", "🌿", "🌳", "🏆", "👑"]
        user_level = 0
        for i, threshold in enumerate(level_thresholds):
            if user["points"] >= threshold:
                user_level = i

        poster_data = {
            "user": {
                "nickname": user.get("nickname") or "环保达人",
                "avatar": user.get("avatar") or "/static/images/default-avatar.png",
                "points": user.get("points", 0),
                "level": user_level,
                "level_name": level_names[user_level],
                "level_icon": level_icons[user_level],
            },
            "checkin": {
                "id": checkin["id"],
                "created_at": checkin["created_at"],
                "category": checkin.get("category", ""),
                "consecutive_days": consecutive_days,
                "points_earned": checkin.get("points_earned", 5),
            },
            "stats": {
                "total_checkins": total_checkins,
                "total_points_earned": total_points_earned,
                "rank": min(rank, 999),
                "user_points": user.get("points", 0),
            },
            "poster_config": {
                "slogan": slogan,
                "date_text": date_text,
                "app_name": "垃圾分类AI助手",
                "background_gradient": ["#2D9B5E", "#1a7343"],
                "accent_color": "#FFD700",
            },
        }

        return JSONResponse(content={
            "success": True,
            "poster_data": poster_data,
        })

    except Exception as e:
        logger.error("生成海报数据失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "海报生成失败"}})

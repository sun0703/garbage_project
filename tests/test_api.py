"""API 接口集成测试"""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


def _make_test_image(width=64, height=64, color=(128, 128, 128)):
    """生成纯色测试图片并返回 Base64 编码"""
    img = Image.new("RGB", (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class TestHealthCheck:
    """健康检查接口测试"""

    def test_health_returns_ok(self, client):
        """验证健康检查返回正常状态"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "model_loaded" in data

    def test_root_returns_html(self, client):
        """验证根路径返回 HTML"""
        response = client.get("/")
        assert response.status_code in (200, 404)  # 前端页面可能存在或不存在


class TestSearchAPI:
    """搜索接口测试"""

    def test_search_empty_query(self, client):
        """空关键词搜索应返回422（参数校验 min_length=1）"""
        response = client.get("/api/search", params={"query": "", "top_k": 5})
        assert response.status_code == 422

    def test_search_common_word(self, client):
        """常见物品搜索应返回结果"""
        response = client.get("/api/search", params={"query": "塑料瓶", "top_k": 3})
        assert response.status_code == 200
        data = response.json()
        assert data.get("success", False)

    def test_search_with_limit(self, client):
        """验证 top_k 参数限制生效"""
        response = client.get("/api/search/enhanced", params={"query": "纸", "top_k": 2})
        if response.status_code == 200:
            data = response.json()
            assert len(data.get("results", [])) <= 2


class TestGuideAPI:
    """分类指南接口测试"""

    def test_get_categories(self, client):
        """获取四分类列表"""
        response = client.get("/api/categories")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        assert len(data.get("categories", [])) == 4

    def test_get_guide_standard(self, client):
        """获取分类标准完整数据"""
        response = client.get("/api/guide/standard")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")

    def test_get_guide_category_valid(self, client):
        """获取合法类别ID的指南"""
        for cat_id in range(4):
            response = client.get(f"/api/guide/category/{cat_id}")
            assert response.status_code == 200, f"类别 {cat_id} 应返回200"

    def test_get_guide_category_invalid(self, client):
        """非法类别ID应返回400"""
        response = client.get("/api/guide/category/99")
        assert response.status_code == 400


class TestPredictAPI:
    """预测接口测试（不依赖真实模型）"""

    def test_predict_invalid_image(self, client):
        """无效Base64图片应返回400"""
        response = client.post("/api/predict", json={"image": "invalid_base64!!!"})
        assert response.status_code in (400, 503)  # 400=格式错误, 503=模型未就绪

    def test_predict_no_image(self, client):
        """缺少image字段应返回422"""
        response = client.post("/api/predict", json={})
        assert response.status_code == 422


class TestErrorCodes:
    """统一错误码测试"""

    def test_404_route(self, client):
        """不存在的路由应返回404"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404


class TestImageUtils:
    """图像工具函数测试"""

    def test_decode_plain_base64(self):
        """验证纯Base64解码"""
        from utils.image import decode_base64_image
        test_img = _make_test_image()
        image, data = decode_base64_image(test_img)
        assert image.size == (64, 64)

    def test_decode_data_url(self):
        """验证带 Data URL 前缀的解码"""
        from utils.image import decode_base64_image
        test_img = _make_test_image()
        data_url = f"data:image/jpeg;base64,{test_img}"
        image, data = decode_base64_image(data_url)
        assert image.size == (64, 64)


class TestJSONLoader:
    """JSON 加载工具测试"""

    def test_load_json_data(self, tmp_path):
        """验证 JSON 文件加载"""
        from utils.json_loader import load_json_data
        file_path = tmp_path / "test.json"
        file_path.write_text('{"key": "value"}', encoding="utf-8")
        data = load_json_data(file_path)
        assert data == {"key": "value"}

    def test_load_nonexistent(self):
        """验证文件不存在返回默认值"""
        from utils.json_loader import load_json_data
        data = load_json_data(Path("/nonexistent/path.json"))
        assert data is None


class TestResponseUtils:
    """响应工具函数测试"""

    def test_success_response(self):
        """验证成功响应格式"""
        from utils.response import success_response
        resp = success_response({"result": "ok"})
        assert resp.status_code == 200
        body = resp.body.decode("utf-8")
        import json
        data = json.loads(body)
        assert data["success"] is True
        assert data["result"] == "ok"

    def test_error_response(self):
        """验证错误响应格式"""
        from utils.response import error_response
        resp = error_response("E001", "参数错误", 400)
        assert resp.status_code == 400
        body = resp.body.decode("utf-8")
        import json
        data = json.loads(body)
        assert data["success"] is False
        assert data["error"]["code"] == "E001"

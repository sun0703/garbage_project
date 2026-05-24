"""
测试垃圾分类系统API接口
"""
import requests
import json

BASE_URL = "http://localhost:8002"

def test_health_check():
    """测试健康检查接口"""
    print("=" * 50)
    print("1. 测试健康检查接口 (/api/health)")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"✅ 状态码: {response.status_code}")
        data = response.json()
        print(f"响应内容:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_root():
    """测试根路径（前端页面）"""
    print("\n" + "=" * 50)
    print("2. 测试根路径 (/) - 前端页面")
    print("=" * 50)
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✅ 状态码: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        if response.status_code == 200:
            print(f"页面大小: {len(response.text)} 字符")
            if "校园垃圾" in response.text or "垃圾分类" in response.text:
                print("✅ 页面包含预期内容")
            else:
                print("⚠️ 页面可能不完整")
        return True
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_categories():
    """测试获取分类接口"""
    print("\n" + "=" * 50)
    print("3. 测试获取分类接口 (/api/categories)")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/categories", timeout=5)
        print(f"✅ 状态码: {response.status_code}")
        data = response.json()
        if data.get("success"):
            categories = data.get("categories", [])
            print(f"✅ 获取到 {len(categories)} 个分类:")
            for cat in categories:
                print(f"   - {cat['name']} (ID: {cat['id']}, 示例数: {len(cat['examples'])})")
        else:
            print(f"⚠️ 返回数据异常: {data}")
        return True
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_search():
    """测试搜索接口"""
    print("\n" + "=" * 50)
    print("4. 测试模糊搜索接口 (/api/search?query=塑料瓶)")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/search?query=塑料瓶", timeout=5)
        print(f"✅ 状态码: {response.status_code}")
        data = response.json()
        if data.get("success"):
            results = data.get("results", [])
            print(f"✅ 搜索到 {len(results)} 个结果:")
            for r in results[:3]:  # 只显示前3个
                print(f"   - {r.get('label')} (相似度: {r.get('similarity_score')})")
        else:
            print(f"⚠️ 返回数据异常: {data}")
        return True
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "🚀 开始测试垃圾分类系统".center(50, "="))
    print(f"📡 服务地址: {BASE_URL}\n")

    results = []
    results.append(("健康检查", test_health_check()))
    results.append(("前端页面", test_root()))
    results.append(("分类接口", test_categories()))
    results.append(("搜索接口", test_search()))

    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 项测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！项目运行正常！")
    else:
        print(f"\n⚠️ 有 {total - passed} 项测试未通过，请检查服务状态")

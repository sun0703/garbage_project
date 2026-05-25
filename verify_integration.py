"""验证 main.py 集成是否成功"""
import sys
sys.path.insert(0, '.')

from main import app, _MULTIMODAL_AVAILABLE

print("=" * 60)
print("  main.py 集成验证")
print("=" * 60)

print(f"\n[1] 多模态模块可用: {_MULTIMODAL_AVAILABLE}")

# 列出所有API端点
routes = [r.path for r in app.routes if hasattr(r, 'path')]
predict_routes = [r for r in routes if 'predict' in r]

print(f"\n[2] 预测相关端点 ({len(predict_routes)}个):")
for r in sorted(predict_routes):
    tag = "NEW" if "multimodal" in r else ""
    print(f"   {r} {tag}")

health_routes = [r for r in routes if 'health' in r]
print(f"\n[3] 健康检查端点:")
for r in sorted(health_routes):
    print(f"   {r}")

print("\n" + "=" * 60)
print("  验证完成!")
print("=" * 60)

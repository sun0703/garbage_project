"""
全局服务实例状态模块

所有路由模块通过此模块获取服务单例，避免直接 import main 中的全局变量。
main.py 在启动时设置这些变量的值，实现依赖注入。
"""
vision_engine = None
search_engine = None
history_store = None
feedback_store = None
inference_cache = None
multimodal_classifier = None
disposal_steps_data: dict = {}
rate_limiter = None

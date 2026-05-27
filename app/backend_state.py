"""全局服务实例，路由模块从这里拿单例"""
vision_engine = None
search_engine = None
history_store = None
feedback_store = None
inference_cache = None
multimodal_classifier = None
multimodal_available = False
disposal_steps_data: dict = {}
rate_limiter = None
architecture_mode = None

"""
请求/响应 Pydantic 模型定义
从 main.py 提取集中管理，供路由模块和主程序引用
"""

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """图像预测请求体"""
    image: str  # Base64编码的图片数据


class BatchPredictRequest(BaseModel):
    """批量图像预测请求体"""
    images: list[str]  # Base64编码的图片数组，最多5张


class FeedbackRequest(BaseModel):
    """用户反馈请求体"""
    image_base64: str                          # 原始图片Base64
    predicted_category_id: int                 # 模型预测的类别 0-3
    correct_category_id: int                   # 用户认为的正确类别 0-3
    comment: str = ""                          # 用户备注（可选，最长500字）

    class Config:
        json_schema_extra = {
            "example": {
                "image_base64": "data:image/jpeg;base64,...",
                "predicted_category_id": 1,
                "correct_category_id": 0,
                "comment": "应该是厨余垃圾"
            }
        }


class RegisterRequest(BaseModel):
    """用户注册请求体"""
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=32)
    nickname: str = Field("", max_length=20)


class LoginRequest(BaseModel):
    """用户登录请求体"""
    username: str
    password: str
    remember: bool = False


class CheckinRequest(BaseModel):
    """打卡请求体"""
    point_id: str = ""
    lat: float = 0
    lng: float = 0
    category: str = ""


class QuizAnswerRequest(BaseModel):
    """答题请求体"""
    question_id: str
    selected: int = Field(..., ge=0, le=3)


class ActivitySignupRequest(BaseModel):
    """活动报名请求体"""
    activity_id: str


class ActivityCreateRequest(BaseModel):
    """活动创建请求体"""
    title: str = Field(..., min_length=2, max_length=100)
    description: str = Field("", max_length=2000)
    cover_image: str = ""
    location: str = Field(..., min_length=1, max_length=200)
    start_time: float
    end_time: float
    max_participants: int = 0
    status: str = "draft"

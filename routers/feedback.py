"""用户反馈接口"""

import hashlib
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import FeedbackRequest
from app import backend_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest) -> JSONResponse:
    """提交反馈"""
    if request.predicted_category_id not in (0, 1, 2, 3):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "predicted_category_id 必须为 0-3"},
            },
        )
    if request.correct_category_id not in (0, 1, 2, 3):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "correct_category_id 必须为 0-3"},
            },
        )

    if not backend_state.feedback_store:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E006", "message": "反馈服务未就绪"}},
        )

    # 只存图片哈希，不存原始base64，省内存
    image_hash = hashlib.sha256(request.image_base64.encode("utf-8")).hexdigest()[:16]
    feedback_id = backend_state.feedback_store.add({
        "image_hash": image_hash,
        "predicted_category_id": request.predicted_category_id,
        "correct_category_id": request.correct_category_id,
        "comment": request.comment[:500],  # 评论太长截断
    })

    logger.info("📝 收到用户反馈: %s, 预测=%d, 正确=%d", feedback_id,
                request.predicted_category_id, request.correct_category_id)

    return JSONResponse(content={
        "success": True,
        "message": "反馈已提交，感谢您的帮助",
        "feedback_id": feedback_id,
    })

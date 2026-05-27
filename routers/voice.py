"""语音纠错接口"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.asr_correction import predict_voice

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/voice/correct")
async def voice_correct(request: dict) -> JSONResponse:
    """语音识别纠错，顺带返回搜索建议"""
    raw_text = request.get("text", "").strip()
    confidence = request.get("confidence", 0)

    if not raw_text:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "识别文本不能为空"},
            },
        )

    # 纠错+搜索建议都交给服务层
    result = predict_voice(raw_text, confidence)

    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(content=result)

"""
语音识别纠错路由模块

接收前端 Web Speech API 的识别结果，返回经过纠错和标准化的文本。
核心纠错逻辑委托给 services.asr_correction.predict_voice 函数。
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.asr_correction import predict_voice

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/voice/correct")
async def voice_correct(request: dict) -> JSONResponse:
    """
    语音识别结果纠错 API

    接收前端 Web Speech API 的识别结果，
    返回经过纠错和标准化的文本。

    请求体：
    {
        "text": "ASR原始识别文本",
        "confidence": 0.95  // 可选，识别置信度
    }

    响应：
    {
        "success": true,
        "original": "原始文本",
        "corrected": "纠错后文本",
        "changed": false,
        "search_results": [...]  // 可选，如果纠错成功则返回搜索建议
    }
    """
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

    # 调用服务层纠错函数，包含完整的纠错+搜索建议逻辑
    result = predict_voice(raw_text, confidence)

    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(content=result)

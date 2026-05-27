"""统一API响应格式"""

import time
from fastapi.responses import JSONResponse


def success_response(
    data: dict = None,
    message: str = None,
    status_code: int = 200,
) -> JSONResponse:
    """成功响应"""
    body = {"success": True, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if data:
        body.update(data)
    if message:
        body["message"] = message
    return JSONResponse(content=body, status_code=status_code)


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
) -> JSONResponse:
    """错误响应"""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )

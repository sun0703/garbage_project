"""
统一 API 响应工具模块
提供标准化的成功/错误响应工厂函数，消除路由中的重复模式
"""

import time
from fastapi.responses import JSONResponse


def success_response(
    data: dict = None,
    message: str = None,
    status_code: int = 200,
) -> JSONResponse:
    """
    构建成功响应

    :param data: 业务数据字典，自动设置 success=True
    :param message: 可选的成功提示消息
    :param status_code: HTTP 状态码，默认 200
    :return: JSONResponse 对象
    """
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
    """
    构建标准错误响应

    :param code: 错误码（如 E001、E002）
    :param message: 用户可读的错误描述
    :param status_code: HTTP 状态码，默认 400
    :return: JSONResponse 对象
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )

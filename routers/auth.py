"""用户认证相关路由"""

import hashlib
import logging
import os
import random
import time
import uuid

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from repositories.user_repo import UserRepository
from repositories.session_repo import SessionRepository
from repositories.sms_code_repo import SmsCodeRepository
from app.models import RegisterRequest, LoginRequest, PhoneLoginRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["用户认证"])


class UserSettingsRequest(BaseModel):
    nickname: str = ""
    avatar: str = ""

# 会话配置
SESSION_COOKIE_NAME = "session_id"
SESSION_EXPIRE_SECONDS = 86400 * 7

# OAuth配置，生产环境记得从环境变量读
OAUTH_CONFIG = {
    "wechat": {
        "enabled": False,
        "app_id": os.getenv("WECHAT_APP_ID", ""),
        "app_secret": os.getenv("WECHAT_APP_SECRET", ""),
        "redirect_uri": os.getenv("WECHAT_REDIRECT_URI", ""),
        "scope": "snsapi_login",
        "auth_url": "https://open.weixin.qq.com/connect/qrconnect",
        "token_url": "https://api.weixin.qq.com/sns/oauth2/access_token",
        "user_url": "https://api.weixin.qq.com/sns/userinfo",
    },
    "github": {
        "enabled": False,
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("GITHUB_REDIRECT_URI", ""),
        "scope": "user:email",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_url": "https://api.github.com/user",
    },
}


def _hash_password(password: str) -> str:
    # SHA-256哈希，先这么用着
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_current_user(request: Request):
    # 从Cookie拿当前用户
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    user_id = SessionRepository.get_session_user_id(session_id)
    if not user_id:
        return None
    return UserRepository.get_user_for_session(user_id)


def _create_session(user_id: str) -> str:
    """创建会话"""
    return SessionRepository.create_session(user_id, SESSION_EXPIRE_SECONDS)


# OAuth辅助函数

def _generate_oauth_state(provider: str) -> str:
    # CSRF防护的state参数
    raw = f"{provider}:{time.time()}:{os.urandom(8).hex()}"
    import hashlib as _hashlib
    return _hashlib.sha256(raw.encode()).hexdigest()[:32]


def _extract_oauth_user_info(provider: str, data: dict):
    # 从不同OAuth提供商提取统一格式用户信息
    if provider == "wechat":
        openid = data.get("openid") or data.get("unionid")
        if not openid:
            return None
        return {
            "oauth_id": openid,
            "nickname": data.get("nickname"),
            "avatar": data.get("headimgurl"),
            "email": None,
        }

    elif provider == "github":
        github_id = str(data.get("id"))
        if not github_id:
            return None
        return {
            "oauth_id": github_id,
            "nickname": data.get("name") or data.get("login"),
            "avatar": data.get("avatar_url"),
            "email": data.get("email"),
        }

    return None


def _generate_oauth_username(provider: str, user_info: dict) -> str:
    # 生成OAuth用户唯一用户名
    prefix_map = {"wechat": "wx_", "github": "gh_"}
    base_name = user_info.get("nickname") or "user"
    import re
    clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', base_name)[:15]
    suffix = user_info.get("oauth_id", "")[:6]
    return f"{prefix_map.get(provider, 'oa_')}{clean_name}_{suffix}"


# 用户系统路由

@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    """用户注册"""
    try:
        if UserRepository.check_username_exists(req.username):
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E409", "message": "用户名已存在"}})

        user_id = UserRepository.create_user(
            username=req.username,
            password_hash=_hash_password(req.password),
            nickname=req.nickname or req.username,
        )

        if not user_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "注册失败，请稍后重试"}})

        session_id = _create_session(user_id)
        resp = JSONResponse(content={
            "success": True,
            "user": {"id": user_id, "username": req.username, "nickname": req.nickname or req.username, "points": 0}
        })
        resp.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")
        return resp
    except Exception as e:
        logger.error("注册失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "注册失败，请稍后重试"}})


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    """用户登录"""
    try:
        user = UserRepository.get_user_by_username(req.username)
        if not user or user["password_hash"] != _hash_password(req.password):
            return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "用户名或密码错误"}})

        UserRepository.update_last_login(user["id"])

        session_id = _create_session(user["id"])
        resp = JSONResponse(content={
            "success": True,
            "user": {"id": user["id"], "username": user["username"], "nickname": user["nickname"], "points": user["points"]}
        })
        cookie_max_age = 86400 * 30 if req.remember else SESSION_EXPIRE_SECONDS
        resp.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=cookie_max_age, httponly=True, samesite="lax")
        return resp
    except Exception as e:
        logger.error("登录失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "登录失败"}})


# 手机号验证码登录

class SmsCodeRequest(BaseModel):
    """发送验证码请求体"""
    phone: str


@router.post("/sms-code")
async def send_sms_code(req: SmsCodeRequest):
    """发送验证码（MVP阶段直接返回，上线前要改）"""
    phone = req.phone
    # 校验手机号格式
    import re
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E001", "message": "手机号格式不正确"}})

    # 生成6位随机验证码
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    # 持久化到数据库，5分钟有效
    SmsCodeRepository.save_code(phone, code, expire_seconds=300)

    # TODO: 上线后不能直接返回验证码
    return JSONResponse(content={
        "success": True,
        "code": code,
        "message": "验证码已发送（开发模式直接返回）"
    })


@router.post("/phone-login")
async def phone_login(req: PhoneLoginRequest):
    """手机号+验证码登录，未注册自动创建"""
    phone = req.phone
    code = req.code

    # 校验验证码（从数据库读取，已过期自动清除）
    stored = SmsCodeRepository.get_code(phone)
    if not stored:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先获取验证码"}})

    stored_code, expire_time = stored
    if stored_code != code:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "验证码错误"}})

    # 验证码用完就删
    SmsCodeRepository.delete_code(phone)

    # 查找手机号对应的用户
    user = UserRepository.get_user_by_phone(phone)

    if user:
        # 已注册，直接登录
        if user.get("status") == "banned":
            return JSONResponse(status_code=403, content={"success": False, "error": {"code": "E403", "message": "账号已被禁用"}})

        UserRepository.update_last_login(user["id"])
        user_id = user["id"]
        is_new_user = False
    else:
        # 未注册，自动创建
        username = f"phone_{phone[-4:]}_{uuid.uuid4().hex[:4]}"
        nickname = f"用户{phone[-4:]}"
        # 手机注册没密码，生成个随机的
        random_password = uuid.uuid4().hex
        user_id = UserRepository.create_user(
            username=username,
            password_hash=_hash_password(random_password),
            nickname=nickname,
            phone=phone,
        )
        if not user_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "自动注册失败，请稍后重试"}})
        is_new_user = True

    # 创建会话
    session_id = _create_session(user_id)

    # 获取完整用户信息
    user_info = UserRepository.get_user_by_id(user_id)

    resp = JSONResponse(content={
        "success": True,
        "user": user_info,
        "is_new_user": is_new_user,
        "message": "欢迎加入！" if is_new_user else "欢迎回来！",
    })
    resp.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")

    logger.info("手机号登录成功: phone=%s, user=%s, new=%s", phone, user_id, is_new_user)
    return resp


@router.post("/logout")
async def logout(request: Request, response: Response):
    """用户登出"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        try:
            SessionRepository.delete_session(session_id)
        except Exception:
            pass
    resp = JSONResponse(content={"success": True, "message": "已退出登录"})
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


# OAuth第三方登录

@router.get("/oauth/providers")
async def list_oauth_providers():
    # 返回可用的OAuth登录方式
    providers = []
    display_config = {
        "wechat": {"display_name": "微信登录", "icon": "wechat", "color": "#07C160", "hint": "微信扫码登录"},
        "github": {"display_name": "GitHub 登录", "icon": "github", "color": "#333", "hint": "开发者首选"},
    }

    for key, config in OAUTH_CONFIG.items():
        info = display_config.get(key, {})
        providers.append({
            "name": key,
            **info,
            "enabled": config.get("enabled", False),
            "has_credentials": bool(config.get("client_id")),
        })

    return JSONResponse(content={
        "success": True,
        "providers": providers,
    })


@router.get("/oauth/{provider}")
async def oauth_authorize(provider: str):
    """获取OAuth授权URL"""
    if provider not in OAUTH_CONFIG:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "E001", "message": f"不支持的登录方式: {provider}"}}
        )

    config = OAUTH_CONFIG[provider]

    if not config.get("enabled"):
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E003", "message": f"{provider} 登录暂未开放，请使用账号密码登录"},
                "hint": f"请联系管理员配置 {provider} OAuth 参数",
            }
        )

    try:
        import urllib.parse

        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": config.get("scope", ""),
            "state": _generate_oauth_state(provider),
        }

        # 微信多一个appid参数
        if provider == "wechat":
            params["appid"] = config["client_id"]

        auth_url = f"{config['auth_url']}?{urllib.parse.urlencode(params)}"

        return JSONResponse(content={
            "success": True,
            "auth_url": auth_url,
            "provider": provider,
            "hint": f"正在跳转 {provider} 登录页面...",
        })

    except Exception as e:
        logger.error("OAuth 授权 URL 生成失败 [%s]: %s", provider, e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E500", "message": "OAuth 服务异常"}}
        )


@router.post("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: dict):
    """OAuth回调，用code换token再拿用户信息"""
    code = request.get("code")

    if not code:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "E001", "message": "缺少授权码"}}
        )

    if provider not in OAUTH_CONFIG:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "E001", "message": f"不支持的登录方式: {provider}"}}
        )

    config = OAUTH_CONFIG[provider]

    try:
        import httpx

        # 用code换access_token
        token_params = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"],
        }

        async with httpx.AsyncClient() as client:
            # 换token
            token_resp = await client.post(config["token_url"], data=token_params, timeout=10.0)
            token_data = token_resp.json()

            if "access_token" not in token_data and "access_token" not in (token_data.get("data") or {}):
                logger.error("OAuth token 获取失败 [%s]: %s", provider, token_data)
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "error": {"code": "E401", "message": "第三方登录失败"}}
                )

            access_token = (
                token_data.get("access_token") or
                token_data.get("data", {}).get("access_token", "")
            )

            # 拿用户信息
            headers = {"Authorization": f"Bearer {access_token}"}
            user_resp = await client.get(
                config["user_url"],
                headers=headers,
                timeout=10.0
            )
            user_data = user_resp.json()

        # 提取用户信息
        oauth_user_info = _extract_oauth_user_info(provider, user_data)

        if not oauth_user_info:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": {"code": "E002", "message": "无法获取用户信息"}}
            )

        # 查找或创建本地用户
        existing_user = UserRepository.get_user_by_oauth(provider, oauth_user_info["oauth_id"])

        if existing_user:
            UserRepository.update_last_login_and_avatar(existing_user["id"], oauth_user_info.get("avatar") or "")
            user_id = existing_user["id"]
            is_new_user = False
        else:
            # 新用户，自动注册
            username = _generate_oauth_username(provider, oauth_user_info)
            user_id = UserRepository.create_user(
                username="",
                password_hash="",
                nickname=oauth_user_info.get("nickname") or username,
                avatar=oauth_user_info.get("avatar") or "",
                oauth_provider=provider,
                oauth_id=oauth_user_info["oauth_id"],
                role="visitor",
            )
            is_new_user = True

        # 创建会话
        session_id = _create_session(user_id)

        # 返回用户信息
        user = UserRepository.get_user_by_id(user_id)

        resp = JSONResponse(content={
            "success": True,
            "user": user,
            "is_new_user": is_new_user,
            "provider": provider,
            "message": f"{'欢迎加入' if is_new_user else '欢迎回来'}！{oauth_user_info.get('nickname', '')}",
        })
        resp.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")

        logger.info("✅ OAuth 登录成功: provider=%s, user=%s, new=%s", provider, user_id, is_new_user)
        return resp

    except Exception as e:
        logger.error("OAuth 回调处理失败 [%s]: %s", provider, e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E500", "message": "第三方登录处理失败"}}
        )


@router.get("/me")
async def get_current_user(request: Request):
    """获取当前用户"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "未登录"}})
    return JSONResponse(content={"success": True, "user": user})


@router.put("/settings")
async def update_user_settings(request: Request, req: UserSettingsRequest):
    """更新用户设置"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from app.database import get_db

        db = get_db()
        now = time.time()
        updates = []
        params = []

        if req.nickname:
            updates.append("nickname = ?")
            params.append(req.nickname)
        if req.avatar:
            updates.append("avatar = ?")
            params.append(req.avatar)

        if updates:
            updates.append("updated_at = ?")
            params.append(now)
            params.append(user["id"])
            db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            db.commit()

        updated_user = UserRepository.get_user_by_id(user["id"])
        return JSONResponse(content={"success": True, "user": updated_user})
    except Exception as e:
        logger.error("更新用户设置失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新设置失败"}})

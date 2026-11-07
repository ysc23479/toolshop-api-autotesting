import base64
import json
import time


def decode_jwt_payload(token: str) -> dict:
    """解析 JWT 中间段 payload"""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(b64))
    except Exception:
        return {}


def token_expires_in(token: str) -> float:
    """返回 token 剩余有效秒数；解析失败返回 -1。"""
    exp = decode_jwt_payload(token).get("exp")
    if not exp:
        return -1
    return exp - time.time()
import time
import uuid

from api.user_api import UserApi
from utils.request_util import RequestUtil

# 一次性账号固定密码
THROWAWAY_PASSWORD = "Kp9#Rt2!wQvX"

# 一次性账号地址
THROWAWAY_ADDRESS = {
    "street": "Test Street",
    "house_number": "10",
    "city": "New Joaquinberg",
    "state": "Arkansas",
    "country": "DM",
    "postal_code": "100000",
}

def login_and_get_token(req, email, password, role_label):
    """登录并返回 access_token"""
    assert email and password, f"{role_label}账号未配置，请检查 .env"

    resp = UserApi(req).login(email, password)

    if resp.status_code != 200:
        body = resp.text
        if resp.status_code == 401:
            raise AssertionError(
                f"{role_label}登录失败 401: {email}\n"
                f"可能原因：密码被 forgot-password 改过"
                f"或账号从未成功注册。\n"
                f"响应: {body}"
            )
        elif resp.status_code == 423:
            raise AssertionError(
                f"{role_label}账号已被锁定 423: {email}\n"
                f"原因：3 次连续登录失败。\n"
                f"修复：注册新账号并更新 .env，或联系 admin 解锁。\n"
                f"响应: {body}"
            )
        else:
            raise AssertionError(
                f"{role_label}登录失败 {resp.status_code}: {email}。响应: {body}"
            )

    body = resp.json()
    assert "access_token" in body, f"{role_label}登录未返回 token: {body}"
    return body["access_token"]

def build_req(env_config):
    """从 env_config 构建未登录的 RequestUtil。"""
    return RequestUtil(
        base_url=env_config["base_url"],
        timeout=env_config.get("timeout", 10),
    )


def build_auth_req(env_config, token):
    """基于 token 构建带 Authorization 头的 RequestUtil。"""
    r = build_req(env_config)
    r.session.headers.update({"Authorization": f"Bearer {token}"})
    return r

def register_and_login_throwaway(req, env_config):
    """现场注册一个一次性账号并登录。
    返回 dict：
      - email / password：账号凭证
      - token：登录后的 access_token
      - req：已带 Authorization 头的 RequestUtil
    """
    suffix = f"{int(time.time())}{uuid.uuid4().hex[:6]}"
    email = f"throwaway_{suffix}@example.org"

    payload = {
        "first_name": "Throwaway",
        "last_name": "Test",
        "address": {**THROWAWAY_ADDRESS},   # 浅拷贝，避免共享可变对象
        "phone": "0987654321",
        "dob": "1990-01-01",
        "password": THROWAWAY_PASSWORD,
        "email": email,
    }
    resp = UserApi(req).register(payload)
    assert resp.status_code == 201, f"一次性账号注册失败: {resp.text}"

    login_resp = UserApi(req).login(email, THROWAWAY_PASSWORD)
    assert login_resp.status_code == 200, f"一次性账号登录失败: {login_resp.text}"
    token = login_resp.json()["access_token"]

    return {
        "email": email,
        "password": THROWAWAY_PASSWORD,
        "token": token,
        "req": build_auth_req(env_config, token),
    }
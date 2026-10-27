# testcases/conftest.py
import os
import pytest
from dotenv import load_dotenv

from api.user_api import UserApi
from api.product_api import ProductApi
from api.cart_api import CartApi
from utils.request_util import RequestUtil
from utils.log_util import get_logger
from utils.yaml_util import load_yaml, write_extract, clear_extract

load_dotenv()
logger = get_logger(__name__)


# ---------- 环境配置 ----------
@pytest.fixture(scope="session")
def env_config():
    config = load_yaml("config/env.yaml")
    return config["env"][config["active_env"]]


@pytest.fixture(scope="session")
def req(env_config):
    """未登录请求工具，整个 session 共用一个 session"""
    return RequestUtil(
        base_url=env_config["base_url"],
        timeout=env_config.get("timeout", 10),
    )


# ---------- 登录辅助 ----------
def _login_and_get_token(req, email, password, role_label):
    """登录并返回 token；失败时给出精确诊断。"""
    assert email and password, f"{role_label}账号未配置，请检查 .env"

    resp = UserApi(req).login(email, password)

    if resp.status_code != 200:
        body = resp.text
        if resp.status_code == 401:
            raise AssertionError(
                f"{role_label}登录失败 401: {email}\n"
                f"可能原因：密码被 forgot-password 改过（重置为 welcome02）"
                f"或账号从未成功注册。\n"
                f"快速诊断：用 Swagger UI 打 POST /users/login，"
                f"密码先试当前 .env 的，再试 welcome02。\n"
                f"响应: {body}"
            )
        elif resp.status_code == 423:
            raise AssertionError(
                f"{role_label}账号已被锁定 423: {email}\n"
                f"原因：3 次连续登录失败（用户故事 AC4）。\n"
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


# ---------- 双 token fixture ----------
@pytest.fixture(scope="session")
def token(req):
    """普通用户 token（读取 .env 的 USER_EMAIL/USER_PASSWORD）"""
    token = _login_and_get_token(
        req, os.getenv("USER_EMAIL"), os.getenv("USER_PASSWORD"), "普通用户"
    )
    write_extract({"token": token})
    return token


@pytest.fixture(scope="session")
def admin_token(req):
    """管理员 token（读取 .env 的 ADMIN_EMAIL/ADMIN_PASSWORD）"""
    token = _login_and_get_token(
        req, os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD"), "管理员"
    )
    write_extract({"admin_token": token})
    return token


# ---------- 双请求工具 ----------
def _build_auth_req(env_config, token):
    r = RequestUtil(
        base_url=env_config["base_url"],
        timeout=env_config.get("timeout", 10),
    )
    r.session.headers.update({"Authorization": f"Bearer {token}"})
    return r


@pytest.fixture(scope="session")
def auth_req(env_config, token):
    """普通用户鉴权请求工具，session 级复用"""
    return _build_auth_req(env_config, token)


@pytest.fixture(scope="session")
def admin_req(env_config, admin_token):
    """管理员鉴权请求工具，session 级复用"""
    return _build_auth_req(env_config, admin_token)


@pytest.fixture(scope="function")
def ephemeral_auth_req(env_config):
    """一次性登录的请求工具（function 级）。

    用途：测试 logout / refresh 等会消耗或使当前 token 失效的接口。
    每次用例独立登录、用完即弃，不会污染 session 级的 auth_req / token。
    """
    r = RequestUtil(
        base_url=env_config["base_url"],
        timeout=env_config.get("timeout", 10),
    )
    resp = UserApi(r).login(os.getenv("USER_EMAIL"), os.getenv("USER_PASSWORD"))
    assert resp.status_code == 200, f"临时登录失败: {resp.text}"
    r.session.headers.update({
        "Authorization": f"Bearer {resp.json()['access_token']}"
    })
    return r


# ---------- 公共真实数据源 ----------
@pytest.fixture(scope="session")
def real_product_id(req):
    """从产品列表里拿一个真实存在的 ID，整场 session 复用（公开接口，不带 token）"""
    resp = ProductApi(req).get_products()
    return resp.json()["data"][0]["id"]


# ---------- 用例级日志 ----------
@pytest.fixture(autouse=True)
def case_log_context(request):
    logger.info(f"===== 开始: {request.node.name} =====")
    yield
    logger.info(f"===== 结束: {request.node.name} =====")


# ---------- 结果钩子 ----------
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    if rep.failed:
        logger.error(f"用例失败: {item.nodeid}")
    elif rep.passed:
        logger.info(f"用例通过: {item.nodeid}")
    elif rep.skipped:
        logger.warning(f"用例跳过: {item.nodeid}")


def pytest_sessionstart(session):
    """每次跑测试前清空 extract.yaml，避免脏数据"""
    clear_extract()

# ---------- 一次性账号 fixture ----------
@pytest.fixture
def throwaway_user(env_config, req):
    """现场注册一个一次性账号并登录，返回可用凭证。

    用途：所有会"污染账号状态"的测试（错误登录、改密码、启用 TOTP、账号锁定）
    必须用它，不能用 session 级的 USER 账号。

    返回 dict：
      - email / password：账号凭证
      - token：登录后的 access_token
      - req：已带 Authorization 头的 RequestUtil

    生命周期：function 级。每个用例独立注册一个，用完即弃。
    """
    import time
    import uuid
    from api.user_api import UserApi

    suffix = f"{int(time.time())}{uuid.uuid4().hex[:6]}"
    email = f"throwaway_{suffix}@example.org"
    password = "Kp9#Rt2!wQvX"  # 已验证通过 haveibeenpwned，不在泄露库

    register_payload = {
        "first_name": "Throwaway",
        "last_name": "Test",
        "address": {
            "street": "Test Street",
            "house_number": "10",
            "city": "New Joaquinberg",
            "state": "Arkansas",
            "country": "DM",
            "postal_code": "100000",
        },
        "phone": "0987654321",
        "dob": "1990-01-01",
        "password": password,
        "email": email,
    }
    resp = UserApi(req).register(register_payload)
    assert resp.status_code == 201, f"一次性账号注册失败: {resp.text}"

    login_resp = UserApi(req).login(email, password)
    assert login_resp.status_code == 200, f"一次性账号登录失败: {login_resp.text}"
    token = login_resp.json()["access_token"]

    auth_req = RequestUtil(
        base_url=env_config["base_url"],
        timeout=env_config.get("timeout", 10),
    )
    auth_req.session.headers.update({"Authorization": f"Bearer {token}"})

    return {
        "email": email,
        "password": password,
        "token": token,
        "req": auth_req,
    }

@pytest.fixture(scope="session")
def real_brand_id(req):
    """GET /brands 返回裸数组 [{"id": "...", "name": "...", "slug": "..."}, ...]"""
    from api.brand_api import BrandApi
    resp = BrandApi(req).list()
    assert resp.status_code == 200, f"查询品牌失败: {resp.text}"
    data = resp.json()
    assert isinstance(data, list) and data, "GET /brands 应返回非空数组"
    return data[0]["id"]


@pytest.fixture(scope="session")
def real_category_id(req):
    """GET /categories 假设同样返回裸数组（brand 已确认是裸数组）。

    如果跑出来 categories 是 {data: [...]}，改这里即可。
    """
    from api.category_api import CategoryApi
    resp = CategoryApi(req).list()
    assert resp.status_code == 200, f"查询分类失败: {resp.text}"
    data = resp.json()
    assert isinstance(data, list) and data, "GET /categories 应返回非空数组"
    return data[0]["id"]
@pytest.fixture(scope="session")

def real_product_image_id(req):
    """从已有产品拿一个真实 product_image.id（POST /products 的 product_image_id 必填）。

    复用 GET /products（公开接口）返回的第一条产品的 product_image.id，
    避免额外调 /images。
    """
    from api.product_api import ProductApi
    resp = ProductApi(req).get_products()
    assert resp.status_code == 200, f"查询产品失败: {resp.text}"
    data = resp.json()["data"]
    assert data, "没有产品，无法拿到 product_image.id"
    image = data[0].get("product_image") or {}
    image_id = image.get("id")
    assert image_id, f"产品没有 product_image.id，完整产品: {data[0]}"
    return image_id


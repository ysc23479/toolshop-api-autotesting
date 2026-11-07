# testcases/conftest.py
import os
import pytest
from dotenv import load_dotenv

from api.product_api import ProductApi
from api.cart_api import CartApi
from api.brand_api import BrandApi
from api.category_api import CategoryApi
from api.invoice_api import InvoiceApi
from api.user_api import UserApi
from utils.auth_util import (
    build_req,
    build_auth_req,
    login_and_get_token,
    register_and_login_throwaway,
)
from utils.log_util import get_logger
from utils.yaml_util import load_yaml

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
    return build_req(env_config)

@pytest.fixture(scope="session")
def token_container(req):
    """可刷新的 token 容器；auth_req 通过它取最新 token。"""
    email = os.getenv("CUSTOMER2_EMAIL")
    pwd = os.getenv("CUSTOMER2_PWD")
    token = login_and_get_token(req, email, pwd, "普通用户")
    return {"token": token, "email": email, "pwd": pwd}


@pytest.fixture(scope="session")
def token(token_container):
    """对外保留原 interface：返回当前 token 字符串。"""
    return token_container["token"]


@pytest.fixture(scope="session")
def auth_req(env_config, token_container, req):
    """带自动续期能力的鉴权请求工具。"""
    r = build_auth_req(env_config, token_container["token"])

    def refresh():
        tmp = build_auth_req(env_config, token_container["token"])
        try:
            resp = UserApi(tmp).refresh()
            if resp.status_code == 200:
                new = resp.json()["access_token"]
                token_container["token"] = new
                return new
        except Exception:
            pass
        try:
            resp = UserApi(req).login(token_container["email"], token_container["pwd"])
            if resp.status_code == 200:
                new = resp.json()["access_token"]
                token_container["token"] = new
                return new
        except Exception:
            pass
        return None

    r.refresh_callback = refresh
    return r

@pytest.fixture(scope="session")
def admin_token_container(req):
    """可刷新的管理员 token 容器；admin_req 通过它取最新 token。"""
    email = os.getenv("ADMIN_EMAIL")
    pwd = os.getenv("ADMIN_PWD")
    token = login_and_get_token(req, email, pwd, "管理员")
    return {"token": token, "email": email, "pwd": pwd}


@pytest.fixture(scope="session")
def admin_token(admin_token_container):
    """对外保留原 interface：返回当前管理员 token 字符串。"""
    return admin_token_container["token"]


@pytest.fixture(scope="session")
def admin_req(env_config, admin_token_container, req):
    """带自动续期能力的管理员鉴权请求工具。"""
    r = build_auth_req(env_config, admin_token_container["token"])

    def refresh():
        tmp = build_auth_req(env_config, admin_token_container["token"])
        try:
            resp = UserApi(tmp).refresh()
            if resp.status_code == 200:
                new = resp.json()["access_token"]
                admin_token_container["token"] = new
                return new
        except Exception:
            pass
        try:
            resp = UserApi(req).login(
                admin_token_container["email"], admin_token_container["pwd"]
            )
            if resp.status_code == 200:
                new = resp.json()["access_token"]
                admin_token_container["token"] = new
                return new
        except Exception:
            pass
        return None

    r.refresh_callback = refresh
    return r


# token隔离
@pytest.fixture(scope="function")
def ephemeral_auth_req(env_config):
    """一次性登录的请求工具
    用途：测试 logout / refresh 等会消耗或使当前 token 失效的接口。
    每一条用例执行前，重新登录一次，拿到全新 token，不会污染 session 级的 auth_req / token。
    """
    r = build_req(env_config)
    ephemeral_token = login_and_get_token(
        r, os.getenv("CUSTOMER_EMAIL"), os.getenv("CUSTOMER_PWD"), "临时登录用户"
    )
    return build_auth_req(env_config, ephemeral_token)

# 账号隔离
@pytest.fixture(scope="function")
def throwaway_user(env_config, req):
    """现场注册一个一次性账号并登录，返回可用凭证。
    用途：所有会污染账号状态的测试（密码错误累加次数、账号锁定、修改密码、开启 TOTP、删除账号）。
    返回 dict：email / password / token / req（已带 Authorization 头）
    生命周期：function 级。每个用例独立注册一个，用完即弃。
    """
    return register_and_login_throwaway(req, env_config)

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

# ---------- 公共真实数据源 ----------
@pytest.fixture(scope="session")
def real_product_id(req):
    """从产品列表里拿一个真实存在的 ID"""
    resp = ProductApi(req).get_products()
    return resp.json()["data"][0]["id"]

@pytest.fixture(scope="session")
def real_brand_id(req):
    """从品牌列表里拿一个真实存在的 ID"""
    resp = BrandApi(req).list()
    data = resp.json()
    return data[0]["id"]

@pytest.fixture(scope="session")
def real_category_id(req):
    """从分类列表里拿一个真实存在的 ID"""
    resp = CategoryApi(req).list()
    data = resp.json()
    return data[0]["id"]

@pytest.fixture(scope="session")
def real_product_image_id(req):
    """从已有产品拿一个真实 product_image.id"""
    resp = ProductApi(req).get_products()
    data = resp.json()["data"]
    image = data[0].get("product_image") or {}
    image_id = image.get("id")
    return image_id

@pytest.fixture(scope="session")
def seed_data(req):
    """一次 /products 请求，取出所有被引用的真实 ID。"""
    resp = ProductApi(req).get_products(page=1)
    data = resp.json()["data"]
    for p in data:
        brand = (p.get("brand") or {}).get("id")
        category = (p.get("category") or {}).get("id")
        image = (p.get("product_image") or {}).get("id")
        if brand and category and image:
            return {
                "product_id": p["id"],
                "brand_id": brand,
                "category_id": category,
                "image_id": image,
            }

# 清理写测试产生的脏数据
@pytest.fixture(scope="session")
def cleanup_products(admin_req):
    created = []
    yield created
    for pid in created:
        try:
            ProductApi(admin_req).delete(pid)
        except Exception:
            pass

@pytest.fixture(scope="session")
def real_cart_id(req, seed_data):
    """创建一个真实购物车并加购一件商品，返回 cart_id"""
    cart_resp = CartApi(req).create_cart()
    cart_id = cart_resp.json()["id"]
    CartApi(req).add_to_cart(cart_id, seed_data["product_id"], 1)
    return cart_id

@pytest.fixture(scope="function")
def real_invoice(admin_req, real_cart_id):
    """每用例创建一张发票，返回完整 invoice dict"""
    payload = {
        "billing_street": "Test Street 1",
        "billing_city": "New Joaquinberg",
        "billing_state": "Arkansas",
        "billing_country": "DM",
        "billing_postal_code": "100000",
        "payment_method": "cash-on-delivery",
        "payment_details": {},
        "cart_id": real_cart_id,
    }
    resp = InvoiceApi(admin_req).create(payload)
    assert resp.status_code == 201, f"创建发票失败: {resp.text}"
    return resp.json()

@pytest.fixture(scope="session")
def real_invoice_id(admin_req, real_cart_id):
    """session 级：一张真实存在的发票 ID，供 get/search/pdf 用例使用"""
    payload = {
        "billing_street": "Test Street 1",
        "billing_city": "New Joaquinberg",
        "billing_state": "Arkansas",
        "billing_country": "DM",
        "billing_postal_code": "100000",
        "payment_method": "cash-on-delivery",
        "payment_details": {},
        "cart_id": real_cart_id,
    }
    resp = InvoiceApi(admin_req).create(payload)
    assert resp.status_code == 201, f"创建发票失败: {resp.text}"
    return resp.json()["id"]

@pytest.fixture(scope="session")
def real_invoice_number(admin_req, real_invoice_id):
    """session 级：真实发票编号，供 PDF 用例使用"""
    resp = InvoiceApi(admin_req).get(real_invoice_id)
    return resp.json()["invoice_number"]

@pytest.fixture(scope="session")
def real_invoice_detail(admin_req, real_invoice_id):
    """session 级：真实发票的完整信息（invoice_number、billing_street 等）"""
    return InvoiceApi(admin_req).get(real_invoice_id).json()

@pytest.fixture(scope="session")
def pdf_ready_invoice_number(admin_req):
    """session 级：从已有发票里挑一张 PDF 已 COMPLETED 的，供下载用例使用"""
    api = InvoiceApi(admin_req)
    first = api.list(page=1).json()
    last_page = first.get("last_page", 1)

    for page in range(last_page, 0, -1):
        data = api.list(page=page).json().get("data", [])
        for inv in data:
            num = inv["invoice_number"]
            r = api.get_pdf_status(num)
            if r.status_code == 200 and r.json().get("status") == "COMPLETED":
                logger.info(f"找到 PDF 就绪的发票: {num}")
                return num

    raise AssertionError("没有找到任何 PDF 已 COMPLETED 的发票")

@pytest.fixture(scope="session")
def brand_in_use_id(req):
    """从产品列表里找一个被产品引用的 brand_id"""
    resp = ProductApi(req).get_products(page=1)
    for p in resp.json()["data"]:
        brand = (p.get("brand") or {}).get("id")
        if brand:
            return brand
    raise AssertionError("没有找到被产品引用的 brand")
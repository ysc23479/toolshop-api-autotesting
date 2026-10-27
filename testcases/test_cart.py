import allure
import pytest

from api.cart_api import CartApi
from api.product_api import ProductApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_cart_data():
    return load_yaml("data/cart_data.yaml")

def load_delete_cart_cases():
    """delete_cart 也支持 xfail（BUG-002）"""
    cases = load_cart_data()["delete_cart"]
    result = []
    for c in cases:
        if c.get("xfail"):
            result.append(pytest.param(
                c,
                marks=pytest.mark.xfail(
                    reason=c.get("reason", ""),
                    strict=True,
                ),
                id=c["case_name"],
            ))
        else:
            result.append(pytest.param(c, id=c["case_name"]))
    return result

def load_cart_add_cases():
    """把 YAML 里的 xfail: true 转成 pytest.mark.xfail(strict=True)。

    strict=True 的含义：BUG 修复后测试通过时，pytest 会报 XPASS(strict) 为失败，
    提醒开发者回来删掉 xfail 标记，避免"假绿"。
    """
    cases = load_cart_data()["add"]
    result = []
    for c in cases:
        if c.get("xfail"):
            result.append(pytest.param(
                c,
                marks=pytest.mark.xfail(
                    reason=c.get("reason", ""),
                    strict=True,
                ),
                id=c["case_name"],
            ))
        else:
            result.append(pytest.param(c, id=c["case_name"]))
    return result


def _create_cart_with_product(cart_api: CartApi, req, product_id: str, quantity: int):
    """辅助：新建 cart，并在其中加购 quantity 件商品。

    行为约定：
      - quantity > 0 才加购
      - quantity == 0 视为"加了空 cart"（用于"商品不在购物车"场景）
    返回：cart_id
    """
    cart_id = cart_api.create_cart().json()["id"]
    if quantity > 0:
        resp = cart_api.add_to_cart(cart_id, product_id, quantity=quantity)
        assert resp.status_code == 200, f"前置加购失败: {resp.text}"
    return cart_id


def _resolve_product_id(case, req):
    """如果 case 里显式写了 product_id（例如 'nonexistent'），用 case 的值；
    否则从产品列表拿一个真实 id。"""
    return case.get("product_id") or ProductApi(req).get_products().json()["data"][0]["id"]


@allure.epic("Toolshop 接口自动化")
@allure.feature("购物车模块")
class TestCart:

    # ---------- 创建购物车 ----------
    @allure.story("创建购物车")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_cart_data()["create"],
        ids=lambda c: c["case_name"],
    )
    def test_create_cart(self, auth_req, case):
        resp = CartApi(auth_req).create_cart()
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")

    # ---------- 加入购物车 ----------
    @allure.story("加入购物车")
    @allure.title("{case_name}")
    @allure.issue("BUG-001: 非法 quantity 应返回 422，实际返回 404 Resource not found")
    @pytest.mark.parametrize(
        "case",
        load_cart_add_cases(),
        ids=lambda c: c["case_name"],
    )
    def test_add_to_cart(self, auth_req, real_product_id, case):
        cart_api = CartApi(auth_req)

        # 每条用例自建购物车，避免跨用例污染（cart 是有状态的）
        cart_id = cart_api.create_cart().json()["id"]

        # product_id 没填就从列表拿真实的；填了就用 case 的（例如 'nonexistent'）
        product_id = case.get("product_id") or real_product_id

        resp = cart_api.add_to_cart(cart_id, product_id, case["quantity"])
        assert_status(resp, case["expect_status"])

        if case.get("expect_result_field"):
            assert_key_exists(resp, "result")

    # ---------- 查询购物车 ----------
    @allure.story("查询购物车")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_cart_data()["get"],
        ids=lambda c: c["case_name"],
    )
    def test_get_cart(self, auth_req, real_product_id, case):
        cart_api = CartApi(auth_req)

        cart_id = case.get("cart_id")
        if not cart_id:
            cart_id = _create_cart_with_product(
                cart_api, auth_req, real_product_id, quantity=1
            )

        resp = cart_api.get_cart(cart_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_cart_items"):
            assert_key_exists(resp, "cart_items")

    # ---------- 更新购物车中商品数量 ----------
    @allure.story("更新购物车商品数量")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_cart_data()["update_quantity"],
        ids=lambda c: c["case_name"],
    )
    def test_update_quantity(self, auth_req, real_product_id, case):
        cart_api = CartApi(auth_req)

        cart_id = case.get("cart_id")
        if not cart_id:
            cart_id = _create_cart_with_product(
                cart_api, auth_req, real_product_id,
                quantity=case.get("add_quantity", 0),
            )

        resp = cart_api.update_quantity(cart_id, real_product_id, case["new_quantity"])
        assert_status(resp, case["expect_status"])

        if case["expect_status"] == 200:
            assert_key_exists(resp, "result")

    # ---------- 删除购物车中的商品 ----------
    @allure.story("删除购物车商品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_cart_data()["delete_product"],
        ids=lambda c: c["case_name"],
    )
    def test_delete_product(self, auth_req, real_product_id, case):
        cart_api = CartApi(auth_req)

        cart_id = case.get("cart_id")
        if not cart_id:
            cart_id = _create_cart_with_product(
                cart_api, auth_req, real_product_id,
                quantity=case.get("add_quantity", 0),
            )

        resp = cart_api.delete_product(cart_id, real_product_id)
        assert_status(resp, case["expect_status"])

    # ---------- 删除购物车 ----------
    @allure.story("删除购物车")
    @allure.title("{case_name}")
    @allure.issue("BUG-002", "DELETE /carts/{cartId} 未鉴权，可被匿名删除")
    @pytest.mark.parametrize(
        "case",
        load_delete_cart_cases(),
        ids=lambda c: c["case_name"],
    )
    def test_delete_cart(self, auth_req, req, case):
        # 需要 cart_id 的场景：先建一个 cart
        cart_id = case.get("cart_id")
        if not cart_id:
            cart_id = CartApi(auth_req).create_cart().json()["id"]

        # 未登录场景用 req，其它用 auth_req
        client = req if case.get("unauth") else auth_req

        resp = CartApi(client).delete_cart(cart_id)
        assert_status(resp, case["expect_status"])

        if case["expect_status"] == 401 and case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])
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

def _build_params(cases, *, with_xfail=False):
    """把 YAML 里的 xfail: true 转成 pytest.mark.xfail(strict=True)。"""
    result = []
    for c in cases:
        if with_xfail and c.get("xfail"):
            result.append(pytest.param(
                c,
                marks=pytest.mark.xfail(reason=c.get("reason", ""), strict=True),
                id=c["case_name"],
            ))
        else:
            result.append(pytest.param(c, id=c["case_name"]))
    return result

def load_create_cases():   return _build_params(load_cart_data()["create"])
def load_add_cases():      return _build_params(load_cart_data()["add"], with_xfail=True)
def load_get_cases():      return _build_params(load_cart_data()["get"])
def load_update_cases():   return _build_params(load_cart_data()["update_quantity"], with_xfail=True)
def load_delete_product_cases(): return _build_params(load_cart_data()["delete_product"])
def load_delete_cart_cases():    return _build_params(load_cart_data()["delete_cart"], with_xfail=True)


def _create_cart_with_product(cart_api: CartApi, req, product_id: str, quantity: int):
    """新建 cart，并在其中加购 quantity 件商品。
    行为约定：
      - quantity > 0 才加购
      - quantity == 0 视为"加了空 cart"
    返回：cart_id
    """
    cart_id = cart_api.create_cart().json()["id"]
    if quantity > 0:
        resp = cart_api.add_to_cart(cart_id, product_id, quantity=quantity)
        assert resp.status_code == 200, f"前置加购失败: {resp.text}"
    return cart_id

def _get_cart_items(cart_api: CartApi, cart_id):
    resp = cart_api.get_cart(cart_id)
    assert_status(resp, 200)
    return resp.json().get("cart_items") or []

def _find_item(items, product_id):
    return next((i for i in items if i["product_id"] == product_id), None)

@allure.epic("Toolshop 接口自动化")
@allure.feature("购物车模块")
class TestCart:

    # ---------- 创建购物车 ----------
    @allure.story("创建购物车")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_create_cases(),
        ids=lambda c: c["case_name"],
    )
    def test_create_cart(self, auth_req, case):
        resp = CartApi(auth_req).create_cart()
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")

    # ---------- 加入购物车 ----------
    @allure.story("加入购物车")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_add_cases(),
        ids=lambda c: c["case_name"],
    )
    def test_add_to_cart(self, auth_req, real_product_id, case):
        cart_api = CartApi(auth_req)

        # 每条用例自建购物车，避免跨用例污染
        cart_id = case.get("cart_id") or cart_api.create_cart().json()["id"]

        # product_id 没填就从列表拿真实的；填了就用 case 的
        product_id = case.get("product_id") or real_product_id

        resp = cart_api.add_to_cart(cart_id, product_id, case["quantity"])
        assert_status(resp, case["expect_status"])

        if case.get("expect_result_field"):
            assert_key_exists(resp, "result")
            items = _get_cart_items(cart_api, cart_id)
            item = _find_item(items, product_id)
            assert item is not None, f"加购后 cart_items 里找不到 {product_id}"
            assert item["quantity"] == case["quantity"], f"数量应为 {case['quantity']}，实际 {item['quantity']}"

    # ---------- 查询购物车 ----------
    @allure.story("查询购物车")
    @allure.title("{case[case_name]}")
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
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_update_cases(),
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
            items = _get_cart_items(cart_api, cart_id)
            item = _find_item(items, real_product_id)
            assert item is not None, f"更新后 cart_items 里找不到 {real_product_id}"
            assert item["quantity"] == case["new_quantity"]

    # ---------- 删除购物车中的商品 ----------
    @allure.story("删除购物车商品")
    @allure.title("{case[case_name]}")
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
        if case["expect_status"] == 204:
            items = _get_cart_items(cart_api, cart_id)
            assert _find_item(items, real_product_id) is None

    # ---------- 删除购物车 ----------
    @allure.story("删除购物车")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_delete_cart_cases(),
        ids=lambda c: c["case_name"],
    )
    def test_delete_cart(self, auth_req, case):
        cart_id = case.get("cart_id") or CartApi(auth_req).create_cart().json()["id"]
        resp = CartApi(auth_req).delete_cart(cart_id)
        assert_status(resp, case["expect_status"])
        assert_status(CartApi(auth_req).get_cart(cart_id), 404)

    @allure.story("购物车全生命周期")
    def test_cart_full_lifecycle(self, auth_req, real_product_id):
        """create → 加 A×2 → 加 A×1 → 加 B×1 → 查 → 改 A 为 5 → 删 B → 查 → 删 cart → 查"""
        cart_api = CartApi(auth_req)

        # 1. 建 cart
        cart_id = cart_api.create_cart().json()["id"]

        # 2. 商品 A 加购 2，再加购 1 → 应为 3（累加规则）
        product_a = real_product_id
        assert_status(cart_api.add_to_cart(cart_id, product_a, 2), 200)
        assert_status(cart_api.add_to_cart(cart_id, product_a, 1), 200)

        items = _get_cart_items(cart_api, cart_id)
        assert len(items) == 1, f"同商品加购应只有 1 条记录，实际 {len(items)}"
        assert items[0]["quantity"] == 3, f"累加应为 3，实际 {items[0]['quantity']}"

        # 3. 商品 B 加购 1
        product_b = ProductApi(auth_req).get_products().json()["data"][1]["id"]
        assert_status(cart_api.add_to_cart(cart_id, product_b, 1), 200)

        items = _get_cart_items(cart_api, cart_id)
        assert len(items) == 2

        # 4. 更新 A 数量为 5
        assert_status(cart_api.update_quantity(cart_id, product_a, 5), 200)
        items = _get_cart_items(cart_api, cart_id)
        assert _find_item(items, product_a)["quantity"] == 5

        # 5. 删除 B
        assert_status(cart_api.delete_product(cart_id, product_b), 204)
        items = _get_cart_items(cart_api, cart_id)
        assert len(items) == 1 and items[0]["product_id"] == product_a

        # 6. 删除 cart
        assert_status(cart_api.delete_cart(cart_id), 204)
        assert_status(cart_api.get_cart(cart_id), 404)
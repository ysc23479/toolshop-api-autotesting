"""E2E 业务流：游客完整购买链路。

覆盖链路：
  匿名 → 获取产品 → 建购物车 → 加购 → guest 下单

设计取舍：
  - 游客没有 token，下单后无法 GET 查详情/列表（这是合理的业务限制）
  - 因此 E2E 到"创建订单成功"为止
  - 这条链路是 BUG-004（guest 缺字段 404）的反向验证：
    正常 payload 时端点可用
"""
import allure
import pytest
from api.cart_api import CartApi
from api.invoice_api import InvoiceApi
from api.product_api import ProductApi
from utils.assert_util import assert_status, assert_key_exists


# 游客 billing + guest 三字段
E2E_GUEST_PAYLOAD = {
    "billing_street": "Guest Street 1",
    "billing_city": "New Joaquinberg",
    "billing_state": "Arkansas",
    "billing_country": "DM",
    "billing_postal_code": "100000",
    "guest_email": "e2e_guest@example.org",
    "guest_first_name": "Guest",
    "guest_last_name": "E2E",
}


@allure.epic("Toolshop 接口自动化")
@allure.feature("E2E-游客购买流程")
@pytest.mark.e2e
class TestGuestPurchaseFlow:

    @allure.story("游客完整购买链路")
    @allure.title("匿名 → 建 cart → 加购 → guest 下单")
    def test_guest_full_purchase_flow(self, req):
        """游客链路验证：不需要登录也能完整下单。"""

        # ---------- 1. 匿名获取产品 ----------
        with allure.step("Step 1: 匿名获取真实产品"):
            products_resp = ProductApi(req).get_products()
            assert_status(products_resp, 200)
            product_id = products_resp.json()["data"][0]["id"]

        # ---------- 2. 匿名创建购物车 ----------
        with allure.step("Step 2: 匿名创建购物车（201）"):
            cart_resp = CartApi(req).create_cart()
            assert_status(cart_resp, 201)
            cart_id = cart_resp.json()["id"]
            allure.attach(cart_id, name="cart_id", attachment_type=allure.attachment_type.TEXT)

        # ---------- 3. 匿名加购 ----------
        with allure.step(f"Step 3: 匿名加购 {product_id} × 1"):
            add_resp = CartApi(req).add_to_cart(cart_id, product_id, quantity=1)
            assert_status(add_resp, 200)

        # ---------- 4. 游客下单 ----------
        with allure.step("Step 4: 游客下单（cash-on-delivery + guest 三字段）"):
            invoice_resp = InvoiceApi(req).create_guest({
                "cart_id": cart_id,
                "payment_method": "cash-on-delivery",
                "payment_details": {},
                **E2E_GUEST_PAYLOAD,
            })
            assert_status(invoice_resp, 201)
            assert_key_exists(invoice_resp, "invoice_number")

            body = invoice_resp.json()
            assert body["invoice_number"].startswith("INV-"), (
                f"订单号格式异常: {body['invoice_number']}"
            )
            allure.attach(
                f"invoice_number={body['invoice_number']}\n"
                f"invoice_id={body.get('id')}",
                name="游客订单",
                attachment_type=allure.attachment_type.TEXT,
            )
"""E2E 业务流：登录用户完整购买链路。

改造说明（v2）：
  - 使用 throwaway_user 而非 auth_req
  - 原因：E2E 应该完全独立，不依赖 session 级 USER 账号的状态
  - 每次跑现场注册一个账号，跑完即弃，永不污染 .env 的 USER
"""
import allure
import pytest
from api.cart_api import CartApi
from api.invoice_api import InvoiceApi
from api.product_api import ProductApi
from utils.assert_util import assert_status, assert_key_exists


E2E_BILLING = {
    "billing_street": "Juvenal Estate",
    "billing_city": "New Joaquinberg",
    "billing_state": "Arkansas",
    "billing_country": "DM",
    "billing_postal_code": "100000",
}


@allure.epic("Toolshop 接口自动化")
@allure.feature("E2E-购买全流程")
@pytest.mark.e2e
class TestPurchaseFlow:

    @allure.story("登录用户完整购买链路")
    @allure.title("登录 → 建 cart → 加购 ×2 → 下单 → 查订单 → 查列表")
    def test_full_purchase_flow(self, throwaway_user):
        """E2E 用一次性账号，完全独立于 .env 的 USER 状态。"""
        # throwaway_user["req"] 是已登录的 RequestUtil
        auth_req = throwaway_user["req"]

        with allure.step("Step 1: 获取真实产品（公开接口）"):
            products_resp = ProductApi(auth_req).get_products()
            assert_status(products_resp, 200)
            product_id = products_resp.json()["data"][0]["id"]

        with allure.step("Step 2: 创建购物车（201）"):
            cart_resp = CartApi(auth_req).create_cart()
            assert_status(cart_resp, 201)
            cart_id = cart_resp.json()["id"]
            allure.attach(cart_id, name="cart_id",
                          attachment_type=allure.attachment_type.TEXT)

        with allure.step(f"Step 3: 加购 {product_id} × 2"):
            add_resp = CartApi(auth_req).add_to_cart(cart_id, product_id, quantity=2)
            assert_status(add_resp, 200)

        with allure.step("Step 4: 查购物车确认商品与数量"):
            get_resp = CartApi(auth_req).get_cart(cart_id)
            assert_status(get_resp, 200)
            assert_key_exists(get_resp, "cart_items")
            items = get_resp.json()["cart_items"]
            assert len(items) == 1, f"购物车应含 1 种商品，实际 {len(items)} 种"
            assert items[0]["quantity"] == 2, f"数量应为 2，实际 {items[0]['quantity']}"

        with allure.step("Step 5: 用该购物车创建订单（cash-on-delivery）"):
            invoice_resp = InvoiceApi(auth_req).create({
                "cart_id": cart_id,
                "payment_method": "cash-on-delivery",
                "payment_details": {},
                **E2E_BILLING,
            })
            assert_status(invoice_resp, 201)
            assert_key_exists(invoice_resp, "invoice_number")
            invoice_body = invoice_resp.json()
            invoice_id = invoice_body["id"]
            allure.attach(
                f"invoice_id={invoice_id}\n"
                f"invoice_number={invoice_body['invoice_number']}",
                name="订单信息",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure.step("Step 6: 查订单详情，确认字段一致"):
            detail_resp = InvoiceApi(auth_req).get(invoice_id)
            assert_status(detail_resp, 200)
            detail = detail_resp.json()
            assert detail["id"] == invoice_id
            assert_key_exists(detail_resp, "invoicelines")

        with allure.step("Step 7: 查订单列表，确认新订单在列表中"):
            list_resp = InvoiceApi(auth_req).list()
            assert_status(list_resp, 200)
            assert_key_exists(list_resp, "data")
            ids = [item["id"] for item in list_resp.json()["data"]]
            assert invoice_id in ids, f"新订单 {invoice_id} 不在列表中"
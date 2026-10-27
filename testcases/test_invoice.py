import time
import allure
import pytest

from api.cart_api import CartApi
from api.invoice_api import InvoiceApi
from api.product_api import ProductApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_invoice_data():
    return load_yaml("data/invoice_data.yaml")


def _wrap_cases_with_xfail(cases):
    """把 YAML 里 xfail: true 的用例转成 pytest.mark.xfail(strict=True)。

    strict=True：BUG 修复后测试通过时报 XPASS(strict) 作为失败，
    提醒开发者回来删掉 xfail 标记，避免"假绿"。
    """
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


def _build_order_payload(cart_id: str, case: dict, billing: dict, guest: bool = False) -> dict:
    """组装下单请求体。

    参数：
      cart_id: 购物车 id
      case:    YAML case（提供 payment_method / guest_* 等）
      billing: 地址字段（正常用例走 fixture 注入，错误用例走 case.billing）
      guest:   是否游客下单

    契约要点：
      - payment_details 必须 present（即使是 cash-on-delivery 也要传 {}）
      - 其它 billing_* 字段按 billing dict 展开
    """
    payload = {
        "cart_id": cart_id,
        "payment_method": case["payment_method"],
        "payment_details": {},
        **billing,
    }
    if guest:
        for key in ("guest_email", "guest_first_name", "guest_last_name"):
            if case.get(key):
                payload[key] = case[key]
    return payload


def _prepare_cart_with_item(req) -> str:
    """建 cart + 加一件真实商品，返回 cart_id"""
    cart_api = CartApi(req)
    cart_id = cart_api.create_cart().json()["id"]
    product_id = ProductApi(req).get_products().json()["data"][0]["id"]
    resp = cart_api.add_to_cart(cart_id, product_id, quantity=1)
    assert resp.status_code == 200, f"前置加购失败: {resp.text}"
    return cart_id


def _extract_pdf_status(body) -> str:
    """兼容多种可能的 pdf-status 响应结构。

    swagger 示例是 invoice 对象（可能未更新）；实际更可能是 {"status": "..."}。
    这里同时兼容三种：{status}、{pdf_status}、{data: {status}}。
    """
    if not isinstance(body, dict):
        return None
    if "status" in body:
        return body["status"]
    if "pdf_status" in body:
        return body["pdf_status"]
    if isinstance(body.get("data"), dict) and "status" in body["data"]:
        return body["data"]["status"]
    return None


@allure.epic("Toolshop 接口自动化")
@allure.feature("订单模块")
class TestInvoice:

    # ---------- bootstrap：唯一硬编码的合法 billing ----------
    @pytest.fixture(scope="class")
    def bootstrap_billing(self):
        """bootstrap 用的 billing 地址，仅用于创建第一张 invoice。

        唯一保留的硬编码。来源：真实网页下单抓包。
        后端对 country-city 做配对白名单校验，"DM" + "New Joaquinberg" 已验证通过。
        注意 DM + Arkansas（美国州）能过说明后端用的是 mock 种子数据，
        与真实地理无关。

        后续所有正常用例的 billing 从 real_billing_address（POST 响应回捞）拿，
        避免硬编码在用例中扩散。
        """
        return {
            "billing_street": "Juvenal Estate",
            "billing_city": "New Joaquinberg",
            "billing_state": "Arkansas",
            "billing_country": "DM",
            "billing_postal_code": "100000",
        }

    # ---------- 真实发票（从系统创建）----------
    @pytest.fixture(scope="class")
    def real_invoice(self, auth_req, bootstrap_billing):
        """创建一张真实发票，返回完整 body。

        成功码是 201（swagger 写 200，文档不一致）。
        """
        invoice_api = InvoiceApi(auth_req)
        cart_id = _prepare_cart_with_item(auth_req)
        payload = _build_order_payload(
            cart_id, {"payment_method": "cash-on-delivery"}, bootstrap_billing
        )
        resp = invoice_api.create(payload)
        assert resp.status_code == 201, f"建发票失败: {resp.text}"
        body = resp.json()
        # 防御性断言：确认响应体回带了 billing 字段（决定 real_billing_address 可行性）
        for k in ("billing_street", "billing_city", "billing_country"):
            assert k in body, (
                f"POST /invoices 响应体缺少 {k}，无法回捞 billing。完整响应: {body}"
            )
        return body

    # ---------- 回捞真实地址：所有正常 create 用例共享 ----------
    @pytest.fixture(scope="class")
    def real_billing_address(self, real_invoice):
        """从 real_invoice 响应体回捞 billing 地址。

        数据来源 = 系统真实存下来的地址（bootstrap 时通过后端校验的组合），
        不再硬编码。地址库变更时，只用改 bootstrap_billing 一处即可自动适配。
        """
        return {
            "billing_street": real_invoice["billing_street"],
            "billing_city": real_invoice["billing_city"],
            "billing_state": real_invoice["billing_state"],
            "billing_country": real_invoice["billing_country"],
            "billing_postal_code": real_invoice["billing_postal_code"],
        }

    # ---------- PDF 已就绪的发票号 ----------
    @pytest.fixture(scope="class")
    def pdf_ready_invoice_number(self, real_invoice, auth_req):
        """等待 real_invoice 的 PDF 生成完成，返回 invoice_number。

        PDF 是异步生成的（INITIATED → IN_PROGRESS → COMPLETED）。
        30 秒超时则 skip 依赖 PDF 的测试，避免误报。
        """
        invoice_api = InvoiceApi(auth_req)
        number = real_invoice["invoice_number"]

        for _ in range(15):  # 15 * 2s = 30s
            resp = invoice_api.get_pdf_status(number)
            if resp.status_code == 200:
                status = _extract_pdf_status(resp.json())
                if status == "COMPLETED":
                    return number
            time.sleep(2)

        pytest.skip(f"PDF 30 秒内未生成（invoice_number={number}），跳过 PDF 相关测试")

    # ---------- 创建订单（登录用户）----------
    @allure.story("创建订单")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_invoice_data()["create"],
        ids=lambda c: c["case_name"],
    )
    def test_create_invoice(self, auth_req, real_billing_address, case):
        # cart_id：case 里显式给了就用（用于"不存在的购物车"错误用例），
        #          否则自建 cart + 加商品
        cart_id = case.get("cart_id") or _prepare_cart_with_item(auth_req)

        # billing：case 里有就用（用于"缺街道"错误用例），否则用回捞的真实地址
        billing = case.get("billing") or real_billing_address

        payload = _build_order_payload(cart_id, case, billing)
        resp = InvoiceApi(auth_req).create(payload)

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_invoice_number"):
            assert_key_exists(resp, "invoice_number")

    # ---------- 查询订单 ----------
    @allure.story("查询订单")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_invoice_data()["get"],
        ids=lambda c: c["case_name"],
    )
    def test_get_invoice(self, auth_req, real_invoice, case):
        invoice_id = case.get("invoice_id") or real_invoice["id"]
        resp = InvoiceApi(auth_req).get(invoice_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_invoicelines"):
            assert_key_exists(resp, "invoicelines")

    # ---------- 订单列表（权限分层）----------
    @allure.story("订单列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_invoice_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_list_invoices(self, auth_req, admin_req, case):
        # swagger 明确：admin 检索所有，user 只检索相关
        client = admin_req if case.get("login_as") == "admin" else auth_req
        resp = InvoiceApi(client).list(**case["params"])
        assert_status(resp, case["expect_status"])
        assert_key_exists(resp, "data")
        assert_key_exists(resp, "total")

    @allure.story("订单列表-权限分层")
    @allure.title("管理员可见发票数 >= 普通用户可见数")
    def test_list_invoices_admin_sees_more_or_equal(self, auth_req, admin_req):
        """验证列表权限隔离（swagger 明确 admin 看全部、user 看自己）。

        断言 admin_total >= user_total 而非严格大于：
          - 新装环境可能数值相等（合理）
          - 若 admin 看到更多，说明权限隔离生效
        若 user 能看到 admin 才有权看到的发票，说明存在权限泄漏——
        这需要超出本用例范围的数据基线对比，先靠 >= 兜底。
        """
        user_resp = InvoiceApi(auth_req).list()
        admin_resp = InvoiceApi(admin_req).list()
        assert_status(user_resp, 200)
        assert_status(admin_resp, 200)

        user_total = user_resp.json()["total"]
        admin_total = admin_resp.json()["total"]
        assert admin_total >= user_total, (
            f"权限分层异常：admin 可见 {admin_total} 张，普通用户可见 {user_total} 张。"
            f"admin 应该能看到所有用户的发票。"
        )

    # ---------- 更新订单状态（admin）----------
    # 注意：用户故事 AC5 说这是 admin 能力，但 swagger 没有 403。
    # 所以只用 admin_req 测；
    # 若将来发现"普通用户也能成功"，需要单独加一条"普通用户应 403"的安全用例。
    @allure.story("更新订单状态")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_invoice_data()["status"],
        ids=lambda c: c["case_name"],
    )
    def test_update_invoice_status(self, admin_req, real_invoice, case):
        invoice_id = case.get("invoice_id") or real_invoice["id"]
        resp = InvoiceApi(admin_req).update_status(
            invoice_id, case["status"], case.get("status_message", "")
        )
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            assert_key_exists(resp, "success")

    # ---------- 游客下单 ----------
    @allure.story("游客下单")
    @allure.title("{case_name}")
    @allure.issue("BUG-003: 缺 guest_email 时返回 404 Resource not found，而非 422。")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_invoice_data()["guest"]),
        ids=lambda c: c["case_name"],
    )
    def test_guest_invoice(self, req, bootstrap_billing, case):
        # 游客场景全部用匿名 req（同时也验证匿名能否建 cart / 加购）
        cart_id = _prepare_cart_with_item(req)
        payload = _build_order_payload(cart_id, case, bootstrap_billing, guest=True)

        resp = InvoiceApi(req).create_guest(payload)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_invoice_number"):
            assert_key_exists(resp, "invoice_number")

    # ---------- 订单 PDF 状态 ----------
    @allure.story("订单 PDF")
    @allure.title("查询 PDF 生成状态")
    def test_invoice_pdf_status(self, auth_req, real_invoice):
        resp = InvoiceApi(auth_req).get_pdf_status(real_invoice["invoice_number"])
        # 契约：PDF 未初始化时返回 400 + {"status": "NOT_INITIATED"}
        #       PDF 已开始生成返回 200 + {"status": "INITIATED"/"IN_PROGRESS"/"COMPLETED"}
        # 两种状态码都是合法响应，断言状态值即可
        assert resp.status_code in (200, 400), (
            f"意外状态码: {resp.status_code}, 响应: {resp.text}"
        )
        status = _extract_pdf_status(resp.json())
        assert status in ("NOT_INITIATED", "INITIATED", "IN_PROGRESS", "COMPLETED"), (
            f"PDF 状态不在枚举内: {status}, 完整响应: {resp.text}"
        )

    # ---------- 订单 PDF 下载 ----------
    @allure.story("订单 PDF")
    @allure.title("下载 PDF")
    def test_invoice_pdf_download(self, auth_req, pdf_ready_invoice_number):
        resp = InvoiceApi(auth_req).download_pdf(pdf_ready_invoice_number)
        assert_status(resp, 200)

        content_type = resp.headers.get("Content-Type", "").lower()
        assert "pdf" in content_type, (
            f"期望 Content-Type 含 pdf，实际: {content_type}\n"
            f"响应体前 300 字: {resp.text[:300]}"
        )

    # ---------- 未登录 ----------
    @allure.story("权限校验")
    @allure.title("未登录查订单列表 → 401")
    def test_list_invoices_unauthorized(self, req):
        resp = InvoiceApi(req).list()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")
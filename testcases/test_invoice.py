import allure
import pytest
import time
from api.invoice_api import InvoiceApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_json_key,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_invoice_data():
    return load_yaml("data/invoice_data.yaml")


def _wrap_cases_with_xfail(cases):
    result = []
    for c in cases:
        if c.get("xfail"):
            result.append(pytest.param(
                c,
                marks=pytest.mark.xfail(reason=c.get("reason", ""), strict=True),
                id=c["case_name"],
            ))
        else:
            result.append(pytest.param(c, id=c["case_name"]))
    return result


def _load_cases(section):
    return _wrap_cases_with_xfail(load_invoice_data()[section])


DEFAULT_BILLING = {
    "billing_street": "Test Street 1",
    "billing_city": "New Joaquinberg",
    "billing_state": "Arkansas",
    "billing_country": "DM",
    "billing_postal_code": "100000",
}

GUEST_FIELDS = ("guest_email", "guest_first_name", "guest_last_name")


def _build_invoice_payload(case: dict, cart_id: str) -> dict:
    payload = {
        **DEFAULT_BILLING,
        "payment_method": case.get("payment_method", "cash-on-delivery"),
        "payment_details": case.get("payment_details", {}),
        "cart_id": cart_id,
    }
    if case.get("billing"):
        payload.update(case["billing"])
    for f in case.get("omit", []):
        payload.pop(f, None)
    for k in GUEST_FIELDS:
        if k in case:
            payload[k] = case[k]
    return payload


def _pick_client(case, req, auth_req, admin_req):
    return {"admin": admin_req, "user": auth_req, "none": req}[
        case.get("login_as", "admin")
    ]


def _resolve_invoice_id(case, real_invoice_id):
    v = case.get("invoice_id")
    if not v or v == "FROM_INVOICE":
        return real_invoice_id
    return v


def _resolve_invoice_number(case, real_invoice_number):
    v = case.get("invoice_number")
    if not v or v == "FROM_INVOICE":
        return real_invoice_number
    return v

def _resolve_q(case, real_invoice_detail):
    """把 YAML 里 q 的占位符解析成真实值"""
    q = (case.get("params") or {}).get("q", "")
    if not q.startswith("FROM_"):
        return q

    number = real_invoice_detail["invoice_number"]
    street = real_invoice_detail["billing_street"]
    parts = street.split()

    mapping = {
        "FROM_INVOICE_NUMBER": number,
        "FROM_INVOICE_NUMBER_SUFFIX": number[-6:],
        "FROM_INVOICE_BILLING_STREET": street,
        "FROM_INVOICE_BILLING_STREET_PARTIAL": parts[1] if len(parts) > 1 else street,
    }
    assert q in mapping, f"未知的 q 占位符: {q}"
    return mapping[q]

@allure.epic("Toolshop 接口自动化")
@allure.feature("发票模块")
class TestInvoice:

    # ---------- 列表 ----------
    @allure.story("发票列表")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("list"))
    def test_list_invoices(self, req, auth_req, admin_req, case):
        client = _pick_client(case, req, auth_req, admin_req)
        params = case.get("params") or {}
        resp = InvoiceApi(client).list(page=params.get("page"))
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            assert_key_exists(resp, case.get("expect_key", "data"))
            if "expect_current_page" in case:
                assert_json_key(resp, "current_page", case["expect_current_page"])
        elif case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])

    # ---------- 搜索 ----------
    @allure.story("发票搜索")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("search"))
    def test_search_invoices(self, req, auth_req, admin_req,
                            real_invoice_detail, case):
        client = _pick_client(case, req, auth_req, admin_req)
        params = case.get("params") or {}
        q = _resolve_q(case, real_invoice_detail)
        resp = InvoiceApi(client).search(q=q, page=params.get("page"))

        assert_status(resp, case["expect_status"])

        if case["expect_status"] == 200:
            body = resp.json()
            assert_key_exists(resp, case.get("expect_key", "data"))

            if case.get("expect_data_not_empty"):
                assert body.get("data"), (
                    f"期望 data 非空，实际: {resp.text}\n（q={q!r}）"
                )
            if case.get("expect_empty_data"):
                assert body.get("data") == [], (
                    f"期望 data 为空，实际: {resp.text}\n（q={q!r}）"
                )
        elif case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])

    # ---------- 详情 ----------
    @allure.story("发票详情")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("get"))
    def test_get_invoice(self, req, auth_req, admin_req, real_invoice_id, case):
        client = _pick_client(case, req, auth_req, admin_req)
        invoice_id = _resolve_invoice_id(case, real_invoice_id)
        resp = InvoiceApi(client).get(invoice_id)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_has_invoicelines"):
            assert_key_exists(resp, "invoicelines")
        elif case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])

    # ---------- 创建 ----------
    @allure.story("创建发票")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("create"))
    def test_create_invoice(self, req, auth_req, admin_req, real_cart_id, case):
        client = _pick_client(case, req, auth_req, admin_req)
        payload = _build_invoice_payload(case, cart_id=real_cart_id)
        resp = InvoiceApi(client).create(payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 201 and case.get("expect_has_invoice_number"):
            assert_key_exists(resp, "invoice_number")
        elif case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])

    # ---------- 游客下单 ----------
    @allure.story("游客下单")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("guest"))
    def test_create_guest_invoice(self, req, real_cart_id, case):
        payload = _build_invoice_payload(case, cart_id=real_cart_id)
        resp = InvoiceApi(req).create_guest(payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_has_invoice_number"):
            assert_key_exists(resp, "invoice_number")

    # ---------- PUT 更新 ----------
    @allure.story("更新发票")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("update_put"))
    def test_update_invoice_put(self, req, admin_req, real_cart_id, real_invoice, case):
        client = _pick_client(case, req, req, admin_req)
        target_id = _resolve_invoice_id(case, real_invoice["id"])
        payload = _build_invoice_payload(case, cart_id=real_cart_id)
        resp = InvoiceApi(client).update(target_id, payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_success"):
            assert_json_key(resp, "success", True)

    # ---------- PATCH 更新 ----------
    @allure.story("更新发票")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("update_patch"))
    def test_update_invoice_patch(self, req, admin_req, real_invoice, case):
        client = _pick_client(case, req, req, admin_req)
        target_id = _resolve_invoice_id(case, real_invoice["id"])
        resp = InvoiceApi(client).patch(target_id, case.get("partial_payload") or {})
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_success"):
            assert_json_key(resp, "success", True)

    # ---------- 更新状态 ----------
    @allure.story("更新发票状态")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("status"))
    def test_update_status(self, req, admin_req, real_invoice, case):
        client = _pick_client(case, req, req, admin_req)
        target_id = _resolve_invoice_id(case, real_invoice["id"])
        resp = InvoiceApi(client).update_status(
            target_id, case["status"], case.get("status_message"),
        )
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_success"):
            assert_json_key(resp, "success", True)

    # ---------- PDF 状态 ----------
    @allure.story("PDF 状态")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("pdf_status"))
    def test_pdf_status(self, req, admin_req, real_invoice_number, case):
        client = _pick_client(case, req, req, admin_req)
        invoice_number = _resolve_invoice_number(case, real_invoice_number)
        resp = InvoiceApi(client).get_pdf_status(invoice_number)
        assert_status(resp, case["expect_status"])

    # ---------- PDF 下载 ----------
    @allure.story("PDF 下载")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", _load_cases("pdf_download"))
    def test_pdf_download(self, req, auth_req, admin_req, pdf_ready_invoice_number, case):
        client = _pick_client(case, req, auth_req, admin_req)
        invoice_number = _resolve_invoice_number(case, pdf_ready_invoice_number)
        resp = InvoiceApi(client).download_pdf(invoice_number)
        assert_status(resp, case["expect_status"])
import allure
import pytest

from api.payment_api import PaymentApi
from utils.assert_util import assert_status, assert_key_exists
from utils.yaml_util import load_yaml


def load_payment_data():
    return load_yaml("data/payment_data.yaml")

def _build_params(cases, *, with_xfail=True):
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




@allure.epic("Toolshop 接口自动化")
@allure.feature("支付模块")
class TestPayment:

    @allure.story("支付校验")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _build_params(load_payment_data()["check"]),
        ids=lambda c: c["case_name"],
    )
    def test_payment_check(self, req, case):
        resp = PaymentApi(req).check(case["payload"])

        ct = resp.headers.get("content-type", "")
        assert ct.startswith("application/json"), \
            f"非 JSON 响应（疑似路由/代理异常）：{resp.text[:160]}"

        assert_status(resp, case["expect_status"])

        if case["expect_status"] == 200:
            assert_key_exists(resp, "message")
            if case.get("expect_message"):
                assert resp.json()["message"] == case["expect_message"], \
                    f"文案不符：期望 {case['expect_message']!r}，实际 {resp.json()['message']!r}"
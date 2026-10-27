import allure
import pytest

from api.payment_api import PaymentApi
from utils.assert_util import assert_status, assert_key_exists
from utils.yaml_util import load_yaml


def load_payment_data():
    return load_yaml("data/payment_data.yaml")


@allure.epic("Toolshop 接口自动化")
@allure.feature("支付模块")
class TestPayment:

    @allure.story("支付校验")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_payment_data()["check"],
        ids=lambda c: c["case_name"],
    )
    def test_payment_check(self, req, case):
        # /payment/check 是公开接口（swagger 只承诺 200，不列 401），用未登录 req
        # 不用 auth_req 是为了避免未来 USER 账号被锁时这条跟着挂——
        # 它不依赖登录态，就不该依赖 token
        resp = PaymentApi(req).check(case["payload"])
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            assert_key_exists(resp, "message")

    @allure.story("契约确认")
    @allure.title("/payment/check 是公开 mock 接口（不校验字段 + 不需要登录）")
    def test_payment_check_public_mock(self, req):
        """契约快照：/payment/check 不校验字段、不需要登录。

        依据：swagger 只承诺 200，未列 401 / 422；实测空 body / 非法 method / 未登录均返回 200。

        本用例的目标不是"验证接口对"，而是"锁定当前契约"：
          - 如果后端将来加了字段校验（返回 422）或鉴权（返回 401），这条会 FAIL
          - 提醒我们更新契约文档和上面 4 条 check 用例的 expect_status
        """
        resp = PaymentApi(req).check({
            "payment_method": "nonexistent-method",
            "payment_details": {"garbage": "data"},
        })
        assert_status(resp, 200)
        assert_key_exists(resp, "message")
        # 顺带确认未登录也返回 200（因为用的是 req 不是 auth_req）
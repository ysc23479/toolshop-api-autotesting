import allure
import pytest

from api.report_api import ReportApi
from utils.assert_util import assert_status, assert_msg_contains
from utils.yaml_util import load_yaml


def load_report_data():
    return load_yaml("data/report_data.yaml")


# ---------- 内部工具 ----------
def _param_with_marks(cases):
    """yaml case → pytest.param；xfail: true 时注入 mark.xfail(strict=True)。"""
    result = []
    for c in cases:
        marks = []
        if c.get("xfail"):
            marks.append(pytest.mark.xfail(reason=c.get("reason", ""), strict=True))
        result.append(pytest.param(c, marks=marks, id=c["case_name"]))
    return result


def _assert_status(resp, case):
    """支持精确 expect_status 与白名单 expect_status_in 两种写法。"""
    if "expect_status_in" in case:
        allowed = case["expect_status_in"]
        assert resp.status_code in allowed, (
            f"状态码不在白名单 {allowed}，实际: {resp.status_code}，响应: {resp.text}"
        )
    else:
        assert_status(resp, case["expect_status"])


def _assert_is_list(resp, expected: bool = True):
    if not expected:
        return
    body = resp.json()
    assert isinstance(body, list), (
        f"应返回数组，实际类型: {type(body)}, 内容: {body}"
    )


@allure.epic("Toolshop 接口自动化")
@allure.feature("报表模块")
class TestReport:

    # ============ 1. 年份销售 ============
    @allure.story("年份销售")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["total_sales_of_years"]),
    )
    def test_total_sales_of_years(self, admin_req, case):
        resp = ReportApi(admin_req).total_sales_of_years(**case.get("params", {}))
        _assert_status(resp, case)
        _assert_is_list(resp, case.get("expect_is_list"))

    # ============ 2. 国家销售 ============
    @allure.story("国家销售")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["total_sales_per_country"]),
    )
    def test_total_sales_per_country(self, admin_req, case):
        resp = ReportApi(admin_req).total_sales_per_country()
        _assert_status(resp, case)
        _assert_is_list(resp, case.get("expect_is_list"))

    # ============ 3. Top10 产品 ============
    @allure.story("Top10 产品")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["top10_purchased_products"]),
    )
    def test_top10_products(self, admin_req, case):
        resp = ReportApi(admin_req).top10_purchased_products()
        _assert_status(resp, case)
        _assert_is_list(resp, case.get("expect_is_list"))

    # ============ 4. Top10 分类 ============
    @allure.story("Top10 分类")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["top10_best_selling_categories"]),
    )
    def test_top10_categories(self, admin_req, case):
        resp = ReportApi(admin_req).top10_best_selling_categories()
        _assert_status(resp, case)
        _assert_is_list(resp, case.get("expect_is_list"))

    # ============ 5. 未登录权限 ============
    @allure.story("权限校验-未登录")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["unauth"]),
    )
    def test_unauthorized(self, req, case):
        api = ReportApi(req)
        method = case["method"]
        resp = getattr(api, method)()
        _assert_status(resp, case)
        if case.get("expect_error"):
            assert_msg_contains(resp, case["expect_error"])

    # ============ 6. 普通用户权限 ============
    @allure.story("权限校验-普通用户")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["forbidden"]),
    )
    def test_forbidden(self, auth_req, case):
        api = ReportApi(auth_req)
        method = case["method"]
        resp = getattr(api, method)()
        _assert_status(resp, case)

    # ============ 7. 场景法 ============
    @allure.story("完整业务流程")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_report_data()["scenario"]),
    )
    def test_full_scenario(self, admin_req, case):
        api = ReportApi(admin_req)

        # 1. 年份销售（传 years=2）
        resp = api.total_sales_of_years(years=2)
        _assert_status(resp, case)
        _assert_is_list(resp, True)

        # 2. 国家销售
        resp = api.total_sales_per_country()
        _assert_status(resp, case)
        _assert_is_list(resp, True)

        # 3. Top10 产品
        resp = api.top10_purchased_products()
        _assert_status(resp, case)
        _assert_is_list(resp, True)

        # 4. Top10 分类
        resp = api.top10_best_selling_categories()
        _assert_status(resp, case)
        _assert_is_list(resp, True)
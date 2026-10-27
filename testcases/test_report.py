import allure
import pytest

from api.report_api import ReportApi
from utils.assert_util import assert_status, assert_msg_contains
from utils.yaml_util import load_yaml


def load_report_data():
    return load_yaml("data/report_data.yaml")


@allure.epic("Toolshop 接口自动化")
@allure.feature("报表模块")
class TestReport:

    @allure.story("年份销售")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_report_data()["total_sales_of_years"],
        ids=lambda c: c["case_name"],
    )
    def test_total_sales_of_years(self, admin_req, case):
        resp = ReportApi(admin_req).total_sales_of_years(**case["params"])
        assert_status(resp, case["expect_status"])
        # 契约：返回数组 [{"year": 2022, "total": 2}]
        body = resp.json()
        assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    @allure.story("国家销售")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_report_data()["total_sales_per_country"],
        ids=lambda c: c["case_name"],
    )
    def test_total_sales_per_country(self, admin_req, case):
        resp = ReportApi(admin_req).total_sales_per_country()
        assert_status(resp, case["expect_status"])

    @allure.story("Top10 产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_report_data()["top10_purchased_products"],
        ids=lambda c: c["case_name"],
    )
    def test_top10_products(self, admin_req, case):
        resp = ReportApi(admin_req).top10_purchased_products()
        assert_status(resp, case["expect_status"])

    @allure.story("Top10 分类")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_report_data()["top10_best_selling_categories"],
        ids=lambda c: c["case_name"],
    )
    def test_top10_categories(self, admin_req, case):
        resp = ReportApi(admin_req).top10_best_selling_categories()
        assert_status(resp, case["expect_status"])

    # ---------- 权限 ----------
    @allure.story("权限校验")
    @allure.title("普通用户访问报表 → 403")
    def test_report_forbidden_for_user(self, auth_req):
        resp = ReportApi(auth_req).total_sales_of_years()
        assert_status(resp, 403)

    @allure.story("权限校验")
    @allure.title("未登录访问报表 → 401")
    def test_report_unauthorized(self, req):
        resp = ReportApi(req).total_sales_of_years()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")
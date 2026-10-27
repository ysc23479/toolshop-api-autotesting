import time
import allure
import pytest

from api.category_api import CategoryApi
from utils.assert_util import assert_status, assert_key_exists
from utils.yaml_util import load_yaml


def load_category_data():
    return load_yaml("data/category_data.yaml")


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


def _unique_suffix():
    return str(int(time.time() * 1000))[-8:]


def _build_category_payload(case: dict) -> dict:
    suffix = _unique_suffix()
    payload = {
        "name": f"AutoCategory {suffix}",
        "slug": f"auto-category-{suffix}",
    }
    if case.get("override"):
        payload.update(case["override"])
    for f in case.get("omit", []):
        payload.pop(f, None)
    return payload


@allure.epic("Toolshop 接口自动化")
@allure.feature("分类模块")
class TestCategory:

    @allure.story("分类列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_category_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_list_categories(self, req, case):
        resp = CategoryApi(req).list()
        assert_status(resp, case["expect_status"])
        # 契约：GET /categories 返回裸数组
        body = resp.json()
        assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    @allure.story("创建分类")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_category_data()["create"],
        ids=lambda c: c["case_name"],
    )
    def test_create_category(self, admin_req, case):
        payload = _build_category_payload(case)
        resp = CategoryApi(admin_req).create(payload)   # ← 不展开
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    @allure.story("创建子分类")
    @allure.title("带 parent_id 创建子分类")
    def test_create_child_category(self, admin_req, real_category_id):
        payload = _build_category_payload({})
        payload["parent_id"] = real_category_id
        resp = CategoryApi(admin_req).create(payload)   # ← 不展开
        assert_status(resp, 201)
        assert_key_exists(resp, "id")

    @allure.story("权限校验")
    @allure.title("{case_name}")
    @allure.issue("BUG-005: 普通用户可创建 product（越权）,实际返回 201 并成功创建。")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["unauth"]),
        ids=lambda c: c["case_name"],
    )
    def test_create_category_forbidden(self, auth_req, case):
        payload = _build_category_payload({})
        resp = CategoryApi(auth_req).create(payload)    # ← 不展开
        assert_status(resp, case["expect_status"])
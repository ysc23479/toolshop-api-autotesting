import time
import allure
import pytest

from api.brand_api import BrandApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
)
from utils.yaml_util import load_yaml


def load_brand_data():
    return load_yaml("data/brand_data.yaml")


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


def _build_brand_payload(case: dict) -> dict:
    """构造 brand 创建 payload。

    slug 自动加时间戳后缀保证唯一；omit 字段用于"缺必填"错误用例。
    """
    suffix = _unique_suffix()
    payload = {
        "name": f"AutoBrand {suffix}",
        "slug": f"auto-brand-{suffix}",
    }
    if case.get("override"):
        payload.update(case["override"])
    for f in case.get("omit", []):
        payload.pop(f, None)
    return payload


@allure.epic("Toolshop 接口自动化")
@allure.feature("品牌模块")
class TestBrand:

    # ---------- 列表 ----------
    @allure.story("品牌列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_brand_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_list_brands(self, req, case):
        resp = BrandApi(req).list()
        assert_status(resp, case["expect_status"])
        # 契约：GET /brands 返回裸数组（不是 {data: [...]}）
        body = resp.json()
        assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    # ---------- 详情 ----------
    @allure.story("品牌详情")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_brand_data()["detail"],
        ids=lambda c: c["case_name"],
    )
    def test_get_brand(self, req, real_brand_id, case):
        brand_id = case.get("brand_id") or real_brand_id
        resp = BrandApi(req).get(brand_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_name"):
            assert_key_exists(resp, "name")

    # ---------- 创建（admin）----------
    @allure.story("创建品牌")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_brand_data()["create"],
        ids=lambda c: c["case_name"],
    )
    def test_create_brand(self, admin_req, case):
        payload = _build_brand_payload(case)
        resp = BrandApi(admin_req).create(payload)   # ← 不展开
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    # ---------- 重复 slug ----------
    @allure.story("创建品牌-重复 slug")
    @allure.title("重复 slug 应返回 409")
    def test_create_brand_duplicate_slug(self, admin_req):
        payload = _build_brand_payload({})
        api = BrandApi(admin_req)

        first = api.create(payload)
        assert_status(first, 201)

        second = api.create(payload)
        assert_status(second, 409)

    # ---------- 权限（user 越权，标 xfail）----------
    @allure.story("权限校验")
    @allure.title("{case_name}")
    @allure.issue("BUG-005: 普通用户可创建 product（越权）,实际返回 201 并成功创建。")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["unauth"]),
        ids=lambda c: c["case_name"],
    )
    def test_create_brand_forbidden(self, auth_req, case):
        payload = _build_brand_payload({})
        resp = BrandApi(auth_req).create(payload)
        assert_status(resp, case["expect_status"])
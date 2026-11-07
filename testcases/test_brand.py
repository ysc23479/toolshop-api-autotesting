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


def _pick_client(case, req, auth_req, admin_req):
    return {"admin": admin_req, "user": auth_req, "none": req}[
        case.get("login_as", "admin")
    ]


def _assert_landed(api_client, brand_id, expected: dict, case):
    """创建/更新后 GET 回验字段落库"""
    if not case.get("expect_success_landed"):
        return
    got = BrandApi(api_client).get(brand_id).json()
    for k in ("name", "slug"):
        if k in expected:
            assert got[k] == expected[k], f"{k} 未落库: {got}"


@allure.epic("Toolshop 接口自动化")
@allure.feature("品牌模块")
class TestBrand:

    # ---------- 列表 ----------
    @allure.story("品牌列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["list"]),
        ids=lambda c: c["case_name"],
    )
    def test_list_brands(self, req, case):
        resp = BrandApi(req).list()
        assert_status(resp, case["expect_status"])
        body = resp.json()
        assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    # ---------- 详情 ----------
    @allure.story("品牌详情")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["detail"]),
        ids=lambda c: c["case_name"],
    )
    def test_get_brand(self, req, real_brand_id, case):
        brand_id = case.get("brand_id") or real_brand_id
        resp = BrandApi(req).get(brand_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_name"):
            assert_key_exists(resp, "name")
        if case.get("expect_has_slug"):
            assert_key_exists(resp, "slug")

    # ---------- 创建 ----------
    @allure.story("创建品牌")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["create"]),
        ids=lambda c: c["case_name"],
    )
    def test_create_brand(self, req, auth_req, admin_req, case):
        client = _pick_client(case, req, auth_req, admin_req)
        payload = _build_brand_payload(case)
        resp = BrandApi(client).create(payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 201:
            body = resp.json()
            if case.get("expect_has_id"):
                assert_key_exists(resp, "id")
            if case.get("expect_has_slug"):
                assert_key_exists(resp, "slug")
            _assert_landed(client, body["id"], payload, case)   # ← 传 body["id"]
    
    # ---------- 创建品牌-重复 slug ----------
    @allure.story("创建品牌-重复 slug")
    @allure.title("重复 slug")
    def test_create_brand_duplicate_slug(self, admin_req):
        payload = _build_brand_payload({})
        api = BrandApi(admin_req)

        first = api.create(payload)
        assert_status(first, 201)

        second = api.create(payload)
        assert_status(second, 409)
    
    # ---------- 更新 ----------
    @allure.story("更新品牌")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["update"]),
        ids=lambda c: c["case_name"],
    )
    def test_update_brand(self, req, auth_req, admin_req, real_brand_id, case):
        client = _pick_client(case, req, auth_req, admin_req)
        target = case.get("brand_id") or real_brand_id
        payload = _build_brand_payload(case)
        resp = BrandApi(client).update(target, payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            if case.get("expect_success"):
                assert resp.json().get("success") is True
            _assert_landed(client, target, payload, case)
    
    # ---------- 更新品牌-slug 冲突 ----------
    @allure.story("更新品牌-slug 冲突")
    @allure.title("PUT 更新品牌-slug 与其他品牌冲突")
    def test_update_brand_duplicate_slug(self, admin_req):
        """构造真实冲突：创建品牌 A / B，用 A 的 slug 更新 B"""
        api = BrandApi(admin_req)

        a = api.create(_build_brand_payload({}))
        b = api.create(_build_brand_payload({}))
        assert a.status_code == 201, f"创建品牌 A 失败: {a.text}"
        assert b.status_code == 201, f"创建品牌 B 失败: {b.text}"

        target = b.json()["id"]
        payload = {
            "name": "Conflict Target",
            "slug": a.json()["slug"],       # 用 A 的 slug 更新 B
        }
        resp = api.update(target, payload)
        assert_status(resp, 409)
        
    # ---------- 删除 ----------
    @allure.story("删除品牌")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_brand_data()["delete"]),
        ids=lambda c: c["case_name"],
    )
    def test_delete_brand(self, req, auth_req, admin_req, real_brand_id, seed_data, case):
        client = _pick_client(case, req, auth_req, admin_req)

        if case.get("brand_id") == "FROM_BRAND_IN_USE":
            brand_id = seed_data["brand_id"]
        elif case.get("brand_id"):
            brand_id = case["brand_id"]
        else:
            # 正常删除 / 无token / 普通用户：现场建一个没人引用的
            created = BrandApi(admin_req).create(_build_brand_payload({}))
            assert created.status_code == 201, f"预创建品牌失败: {created.text}"
            brand_id = created.json()["id"]

        resp = BrandApi(client).delete(brand_id)
        assert_status(resp, case["expect_status"])


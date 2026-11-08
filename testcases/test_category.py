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


def _pick_client(case, req, auth_req, admin_req):
    return {"admin": admin_req, "user": auth_req, "none": req}[
        case.get("login_as", "admin")
    ]


def _assert_landed(api_client, category_id, expected: dict, case):
    """创建后 GET 回验字段落库"""
    if not case.get("expect_success_landed"):
        return
    got = CategoryApi(api_client).get(category_id).json()
    for k in ("name", "slug"):
        if k in expected:
            assert got[k] == expected[k], f"{k} 未落库: {got}"


@allure.epic("Toolshop 接口自动化")
@allure.feature("分类模块")
class TestCategory:

    # ---------- 列表 ----------
    @allure.story("分类列表")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["list"]),
        ids=lambda c: c["case_name"],
    )
    def test_list_categories(self, req, auth_req, admin_req, case):
        client = _pick_client(case, req, auth_req, admin_req)
        resp = CategoryApi(client).list()
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            body = resp.json()
            assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    # ---------- 树 ----------
    @allure.story("分类树")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["tree"]),
        ids=lambda c: c["case_name"],
    )
    def test_category_tree(self, req, auth_req, admin_req, case):
        client = _pick_client(case, req, auth_req, admin_req)
        by_slug = case.get("by_category_slug")
        if by_slug == "FROM_EXISTING_SLUG":
            # 复用 list 接口取真实 slug
            listing = CategoryApi(req).list().json()
            by_slug = listing[0]["slug"]
        resp = CategoryApi(client).tree(by_category_slug=by_slug)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            body = resp.json()
            assert isinstance(body, list), f"应返回数组，实际: {type(body)}"

    # ---------- 详情 ----------
    @allure.story("分类详情")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["detail"]),
        ids=lambda c: c["case_name"],
    )
    def test_get_category(self, req, auth_req, admin_req, real_category_id, case):
        client = _pick_client(case, req, auth_req, admin_req)
        category_id = case.get("category_id") or real_category_id
        resp = CategoryApi(client).get(category_id)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            if case.get("expect_has_name"):
                assert_key_exists(resp, "name")
            if case.get("expect_has_slug"):
                assert_key_exists(resp, "slug")

    # ---------- 创建 ----------
    @allure.story("创建分类")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["create"]),
        ids=lambda c: c["case_name"],
    )
    def test_create_category(self, req, auth_req, admin_req, real_category_id, case):
        client = _pick_client(case, req, auth_req, admin_req)
        payload = _build_category_payload(case)
        if payload.get("parent_id") == "FROM_CATEGORY_ID":
            payload["parent_id"] = real_category_id

        resp = CategoryApi(client).create(payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 201:
            body = resp.json()
            if case.get("expect_has_id"):
                assert_key_exists(resp, "id")
            if case.get("expect_has_slug"):
                assert_key_exists(resp, "slug")
            _assert_landed(client, body["id"], payload, case)

    # ---------- 创建-重复 slug ----------
    @allure.story("创建分类-重复 slug")
    @allure.title("重复 slug")
    def test_create_category_duplicate_slug(self, admin_req):
        payload = _build_category_payload({})
        api = CategoryApi(admin_req)

        first = api.create(payload)
        assert_status(first, 201)

        second = api.create(payload)
        assert_status(second, 409)

    # ---------- 删除 ----------
    @allure.story("删除分类")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_category_data()["delete"]),
        ids=lambda c: c["case_name"],
    )
    def test_delete_category(self, req, auth_req, admin_req,
                             real_category_id, seed_data, case):
        client = _pick_client(case, req, auth_req, admin_req)

        if case.get("category_id") == "FROM_CATEGORY_IN_USE":
            # 被产品引用的分类，用 seed_data 里已反查到的 category_id
            category_id = seed_data["category_id"]
        elif case.get("category_id"):
            category_id = case["category_id"]
        else:
            # 正常删除：现场建一个干净分类（避免误删被引用分类）
            created = CategoryApi(admin_req).create(_build_category_payload({}))
            assert created.status_code == 201, f"预创建分类失败: {created.text}"
            category_id = created.json()["id"]

        resp = CategoryApi(client).delete(category_id)
        assert_status(resp, case["expect_status"])
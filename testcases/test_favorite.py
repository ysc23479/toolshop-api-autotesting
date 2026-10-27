import allure
import pytest

from api.favorite_api import FavoriteApi
from api.product_api import ProductApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_favorite_data():
    return load_yaml("data/favorite_data.yaml")


def _list_favorites(api: FavoriteApi):
    """兼容 {data: [...]} 和裸数组两种返回结构。

    未确认 GET /favorites 实际返回格式，这里做兼容。
    若两轮后确认只有一种结构，可收紧。
    """
    resp = api.list()
    if resp.status_code != 200:
        return []
    body = resp.json()
    if isinstance(body, list):
        return body
    return body.get("data", [])


def _ensure_favorite_exists(api: FavoriteApi, product_id: str) -> dict:
    """确保 product_id 在当前用户的收藏中，返回 favorite 条目（含 id）。

    若不存在则创建；若已存在则从列表中取回。
    """
    # 先查列表
    for f in _list_favorites(api):
        if f.get("product_id") == product_id:
            return f
    # 不存在则创建
    resp = api.add(product_id)
    assert resp.status_code == 200, f"前置创建收藏失败: {resp.text}"
    return resp.json()


def _ensure_favorite_not_exists(api: FavoriteApi, product_id: str):
    """确保 product_id 不在当前用户的收藏中（用于测试"正常添加"）。"""
    for f in _list_favorites(api):
        if f.get("product_id") == product_id:
            api.delete(f["id"])
            return


@allure.epic("Toolshop 接口自动化")
@allure.feature("收藏模块")
class TestFavorite:

    # ---------- 添加收藏 ----------
    @allure.story("添加收藏")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["add"],
        ids=lambda c: c["case_name"],
    )
    def test_add_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        # "正常"用例先清理，避免被之前的测试污染成"已收藏"状态
        if case.get("use_real_product"):
            _ensure_favorite_not_exists(api, real_product_id)

        product_id = case.get("product_id") or real_product_id
        resp = api.add(product_id)

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")

    # ---------- 重复收藏 ----------
    @allure.story("重复收藏")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["duplicate"],
        ids=lambda c: c["case_name"],
    )
    def test_add_favorite_duplicate(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        # 先确保已收藏，再 add 一次 → 期望 409
        _ensure_favorite_exists(api, real_product_id)

        resp = api.add(real_product_id)
        assert_status(resp, case["expect_status"])

    # ---------- 查询收藏 ----------
    @allure.story("查询收藏")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["get"],
        ids=lambda c: c["case_name"],
    )
    def test_get_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        favorite_id = case.get("favorite_id")
        if not favorite_id:
            favorite_id = _ensure_favorite_exists(api, real_product_id)["id"]

        resp = api.get(favorite_id)
        assert_status(resp, case["expect_status"])

    # ---------- 删除收藏 ----------
    @allure.story("删除收藏")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["delete"],
        ids=lambda c: c["case_name"],
    )
    def test_delete_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        favorite_id = case.get("favorite_id")
        if not favorite_id:
            favorite_id = _ensure_favorite_exists(api, real_product_id)["id"]

        resp = api.delete(favorite_id)
        assert_status(resp, case["expect_status"])

    # ---------- 权限 ----------
    @allure.story("权限校验")
    @allure.title("未登录操作收藏 → 401")
    def test_favorites_unauthorized(self, req, real_product_id):
        api = FavoriteApi(req)

        resp = api.list()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")

        resp = api.add(real_product_id)
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")
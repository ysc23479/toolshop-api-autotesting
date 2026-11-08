import allure
import pytest

from api.favorite_api import FavoriteApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_favorite_data():
    return load_yaml("data/favorite_data.yaml")


# ---------- 内部工具 ----------
def _list_favorites(api: FavoriteApi):
    """GET /favorites 兼容裸数组与 {data:[...]} 两种返回结构。"""
    resp = api.list()
    if resp.status_code != 200:
        return []
    body = resp.json()
    if isinstance(body, list):
        return body
    return body.get("data", [])


def _ensure_favorite_exists(api: FavoriteApi, product_id: str) -> dict:
    """确保 product_id 在当前用户收藏中，返回 favorite 条目（含 id）。"""
    for f in _list_favorites(api):
        if f.get("product_id") == product_id:
            return f
    resp = api.add(product_id)
    assert resp.status_code == 200, f"前置创建收藏失败: {resp.text}"
    return resp.json()


def _ensure_favorite_not_exists(api: FavoriteApi, product_id: str):
    """确保 product_id 不在当前用户收藏中。"""
    for f in _list_favorites(api):
        if f.get("product_id") == product_id:
            api.delete(f["id"])
            return


def _add_by_case(api: FavoriteApi, case: dict, real_product_id: str):
    """按用例字段构造添加收藏请求：
       - 有 payload     → 直接作为请求体（空对象 / null / 类型错误）
       - 有 product_id  → 传指定 ID（无效 / 空串 / 超长 / 注入）
       - 都没有         → 传真实存在的商品 ID
    """
    if "payload" in case:
        return api.req.send("POST", api.PATH, json=case["payload"])
    return api.add(case.get("product_id", real_product_id))


@allure.epic("Toolshop 接口自动化")
@allure.feature("收藏模块")
class TestFavorite:

    # ============ 1. 添加收藏 ============
    @allure.story("添加收藏")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["add"],
        ids=lambda c: c["case_name"],
    )
    def test_add_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        # 正常用例先清理，避免被之前测试污染成"已收藏"状态
        if case.get("use_real_product"):
            _ensure_favorite_not_exists(api, real_product_id)

        resp = _add_by_case(api, case, real_product_id)

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")

    # ============ 2. 重复收藏 ============
    @allure.story("重复收藏")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["duplicate"],
        ids=lambda c: c["case_name"],
    )
    def test_add_favorite_duplicate(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        # 前置：确保已收藏 → 再次 add 应 409
        _ensure_favorite_exists(api, real_product_id)

        resp = api.add(real_product_id)
        assert_status(resp, case["expect_status"])

    # ============ 3. 查询单个收藏 ============
    @allure.story("查询收藏")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["get"],
        ids=lambda c: c["case_name"],
    )
    def test_get_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        if case.get("use_real_favorite"):
            favorite_id = _ensure_favorite_exists(api, real_product_id)["id"]
        else:
            favorite_id = case["favorite_id"]

        resp = api.get(favorite_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")

    # ============ 4. 列出收藏 ============
    @allure.story("列出收藏")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_list_favorites(self, auth_req, case):
        api = FavoriteApi(auth_req)
        resp = api.list()
        assert_status(resp, case["expect_status"])

        if case.get("expect_is_list"):
            body = resp.json()
            if isinstance(body, dict):
                body = body.get("data", [])
            assert isinstance(body, list), f"期望返回列表，实际类型: {type(body)}"

    # ============ 5. 删除收藏 ============
    @allure.story("删除收藏")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["delete"],
        ids=lambda c: c["case_name"],
    )
    def test_delete_favorite(self, auth_req, real_product_id, case):
        api = FavoriteApi(auth_req)

        if case.get("use_real_favorite"):
            favorite_id = _ensure_favorite_exists(api, real_product_id)["id"]
        else:
            favorite_id = case["favorite_id"]

        resp = api.delete(favorite_id)
        assert_status(resp, case["expect_status"])

    # ============ 6. 权限校验 ============
    @allure.story("权限校验")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_favorite_data()["unauth"],
        ids=lambda c: c["case_name"],
    )
    def test_favorites_unauthorized(self, req, real_product_id, case):
        """req 为未登录请求工具，任何操作都应被拦截为 401。"""
        api = FavoriteApi(req)
        method = case["method"]

        if method == "list":
            resp = api.list()
        elif method == "add":
            resp = api.add(real_product_id)
        elif method == "get":
            resp = api.get("any-id")
        elif method == "delete":
            resp = api.delete("any-id")
        else:
            pytest.skip(f"未知方法: {method}")

        assert_status(resp, case["expect_status"])
        assert_msg_contains(resp, case["expect_error"])
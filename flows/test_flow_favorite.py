"""E2E：收藏流转（登录用户）。"""
import allure
import pytest

from api.favorite_api import FavoriteApi
from api.product_api import ProductApi
from utils.assert_util import assert_status


def _list_favorites(api: FavoriteApi):
    body = api.list().json()
    return body if isinstance(body, list) else body.get("data", [])


@allure.epic("Toolshop 接口自动化")
@allure.feature("业务流程-E2E")
@pytest.mark.e2e
class TestFavoriteFlow:

    @allure.story("收藏流转")
    @allure.title("收藏流程-添加→列表→详情→取消→再查404")
    def test_favorite_full_flow(self, throwaway_user):
        api = FavoriteApi(throwaway_user["req"])
        product_api = ProductApi(throwaway_user["req"])

        with allure.step("Step 1: 选一个真实商品"):
            products = product_api.get_products().json()["data"]
            assert products, "产品列表为空"
            product_id = products[0]["id"]
            allure.attach(product_id, name="product_id",
                          attachment_type=allure.attachment_type.TEXT)

        with allure.step("Step 0: 前置清理（确保初始未收藏）"):
            for f in _list_favorites(api):
                if f.get("product_id") == product_id:
                    api.delete(f["id"])

        favorite_id = None
        try:
            with allure.step("Step 2: 添加收藏"):
                add_resp = api.add(product_id)
                assert_status(add_resp, 201)  
                favorite_id = add_resp.json()["id"]

            with allure.step("Step 3: 列表能查到"):
                ids = [f["id"] for f in _list_favorites(api)]
                assert favorite_id in ids, f"收藏列表未找到 {favorite_id}"

            with allure.step("Step 4: 详情可查"):
                detail = api.get(favorite_id)
                assert_status(detail, 200)
                assert detail.json()["id"] == favorite_id

            with allure.step("Step 5: 取消收藏"):
                del_resp = api.delete(favorite_id)
                assert_status(del_resp, 204)
                favorite_id = None

            with allure.step("Step 6: 删除后再查 → 404"):
                after = api.get(add_resp.json()["id"])
                assert_status(after, 404)
        finally:
            if favorite_id:
                try:
                    api.delete(favorite_id)
                except Exception:
                    pass
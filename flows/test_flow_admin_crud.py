import time

import allure
import pytest

from api.brand_api import BrandApi
from api.product_api import ProductApi
from utils.assert_util import assert_status


def _suffix():
    return str(int(time.time() * 1000))[-8:]


@allure.epic("Toolshop 接口自动化")
@allure.feature("业务流程-E2E")
@pytest.mark.e2e
class TestAdminCrudFlow:

    @allure.story("管理员关联 CRUD")
    @allure.title("品牌+产品：建brand→建product→删brand(409)→删product→删brand(204)→查brand(404)")
    def test_brand_product_crud_flow(
        self, admin_req, real_category_id, real_product_image_id,
    ):
        suffix = _suffix()
        brand_api = BrandApi(admin_req)
        product_api = ProductApi(admin_req)

        brand_id = None
        product_id = None

        try:
            with allure.step("Step 1: 建 brand"):
                create_brand = brand_api.create({
                    "name": f"E2E Brand {suffix}",
                    "slug": f"e2e-brand-{suffix}",
                })
                assert_status(create_brand, 201)
                brand_id = create_brand.json()["id"]

            with allure.step("Step 2: 建 product 引用这个 brand"):
                create_product = product_api.create({
                    "name": f"E2E Product {suffix}",
                    "description": "E2E test product",
                    "price": 19.99,
                    "category_id": real_category_id,
                    "brand_id": brand_id,
                    "product_image_id": real_product_image_id,
                    "is_location_offer": 0,
                    "is_rental": 0,
                    "co2_rating": "A",
                })
                assert_status(create_product, 201)
                product_id = create_product.json()["id"]

            with allure.step("Step 3: 删 brand → 409（被 product 引用）"):
                del_brand_1 = brand_api.delete(brand_id)
                assert_status(del_brand_1, 409)

            with allure.step("Step 4: 删 product → 204"):
                del_product = product_api.delete(product_id)
                assert_status(del_product, 204)
                product_id = None

            with allure.step("Step 5: 删 brand → 204"):
                to_delete_brand = brand_id
                del_brand_2 = brand_api.delete(to_delete_brand)
                assert_status(del_brand_2, 204)
                brand_id = None

            with allure.step("Step 6: 查已删除 brand → 404"):
                assert_status(brand_api.get(to_delete_brand), 404)
        finally:
            if product_id:
                try: product_api.delete(product_id)
                except Exception: pass
            if brand_id:
                try: brand_api.delete(brand_id)
                except Exception: pass
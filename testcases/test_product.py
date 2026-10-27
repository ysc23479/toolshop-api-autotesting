import time
import allure
import pytest

from api.product_api import ProductApi
from utils.assert_util import assert_status, assert_key_exists
from utils.yaml_util import load_yaml


def load_product_data():
    return load_yaml("data/product_data.yaml")


def _unique_product_suffix():
    return str(int(time.time() * 1000))[-8:]

def _wrap_cases_with_xfail(cases):
    """把 YAML 里 xfail: true 的用例转成 pytest.mark.xfail(strict=True)"""
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

def _build_product_payload(real_brand_id, real_category_id, real_product_image_id,case: dict) -> dict:
    """构造 product 创建/更新 payload。

    必填：name / description / price / category_id / brand_id
    co2_rating 枚举：A/B/C/D/E（假设，看实际校验）
    is_location_offer / is_rental：0/1 整数
    """
    suffix = _unique_product_suffix()
    payload = {
        "name": f"AutoProduct {suffix}",
        "description": "Automation test product",
        "price": 19.99,
        "category_id": real_category_id,
        "brand_id": real_brand_id,
        "product_image_id": real_product_image_id,   
        "is_location_offer": 0,
        "is_rental": 0,
        "co2_rating": "A",
    }
    if case.get("override"):
        payload.update(case["override"])
    for f in case.get("omit", []):
        payload.pop(f, None)
    return payload


@allure.epic("Toolshop 接口自动化")
@allure.feature("产品模块")
class TestProduct:

    # ---------- 列表 ----------
    @allure.story("产品列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_get_products(self, req, case):
        resp = ProductApi(req).get_products(**case["params"])
        assert_status(resp, case["expect_status"])
        assert_key_exists(resp, "data")

    # ---------- 详情 ----------
    @allure.story("产品详情")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["detail"],
        ids=lambda c: c["case_name"],
    )
    def test_get_product_detail(self, req, real_product_id, case):
        product_id = real_product_id if case["product_id"] == "FROM_LIST" else case["product_id"]
        resp = ProductApi(req).get_product(product_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_name"):
            assert_key_exists(resp, "name")


@allure.epic("Toolshop 接口自动化")
@allure.feature("产品模块-管理")
class TestProductAdmin:

    # ---------- 创建 ----------
    @allure.story("创建产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["create"],
        ids=lambda c: c["case_name"],
    )
    def test_create_product(self, admin_req, real_brand_id, real_category_id,
                            real_product_image_id, case):
        payload = _build_product_payload(real_brand_id, real_category_id,
                                         real_product_image_id, case)
        resp = ProductApi(admin_req).create(payload)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    # ---------- 更新 ----------
    @allure.story("更新产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["update"],
        ids=lambda c: c["case_name"],
    )
    def test_update_product(self, admin_req, real_brand_id, real_category_id,
                            real_product_image_id, case):
        # 前置 create：必须断言成功，否则 KeyError 掩盖真实问题
        create_payload = _build_product_payload(real_brand_id, real_category_id,
                                                real_product_image_id, {})
        create_resp = ProductApi(admin_req).create(create_payload)
        assert_status(create_resp, 201)     # ← 显式断言，方便排查
        product_id = create_resp.json()["id"]

        target_id = case.get("product_id") or product_id
        update_payload = dict(create_payload)
        update_payload["name"] = f"Updated {_unique_product_suffix()}"
        resp = ProductApi(admin_req).update(target_id, update_payload)
        assert_status(resp, case["expect_status"])

    # ---------- 删除 ----------
    @allure.story("删除产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["delete"],
        ids=lambda c: c["case_name"],
    )
    def test_delete_product(self, admin_req, real_brand_id, real_category_id,
                            real_product_image_id, case):
        product_id = case.get("product_id")
        if not product_id:
            create_payload = _build_product_payload(real_brand_id, real_category_id,
                                                    real_product_image_id, {})
            create_resp = ProductApi(admin_req).create(create_payload)
            assert_status(create_resp, 201)     # ← 显式断言
            product_id = create_resp.json()["id"]

        resp = ProductApi(admin_req).delete(product_id)
        assert_status(resp, case["expect_status"])

    # ---------- 权限 ----------
    @allure.story("权限校验")
    @allure.title("{case_name}")
    @allure.issue("BUG-005: 普通用户可创建 product（越权）,实际返回 201 并成功创建。")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_product_data()["unauth"]),
        ids=lambda c: c["case_name"],
    )
    def test_create_product_forbidden(self, auth_req, real_brand_id, real_category_id,
                                       real_product_image_id, case):
        payload = _build_product_payload(real_brand_id, real_category_id,
                                         real_product_image_id, {})
        resp = ProductApi(auth_req).create(payload)
        assert_status(resp, case["expect_status"])
from os import path
import time
import allure
import pytest

from api.product_api import ProductApi
from utils.assert_util import assert_status, assert_key_exists, assert_response_time,assert_json_key, assert_sorted
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

def _load_cases(section):
    """加载 YAML 段，并把 xfail: true 的用例转成 pytest.mark.xfail(strict=True)"""
    return _wrap_cases_with_xfail(load_product_data()[section])

def _build_product_payload(real_brand_id, real_category_id, real_product_image_id, case: dict) -> dict:
    """构造 product 创建/更新 payload。"""
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

def _resolve_list_params(case, seed_data):
    """把 list 用例 params 里的占位符替换成 seed_data 真实值。

    - FROM_BRAND    -> seed_data["brand_id"]    （该品牌下有产品）
    - FROM_CATEGORY -> seed_data["category_id"] （该分类下有产品）
    其它值原样保留。
    """
    params = dict(case.get("params") or {})
    if params.get("by_brand") == "FROM_BRAND":
        params["by_brand"] = seed_data["brand_id"]
    if params.get("by_category") == "FROM_CATEGORY":
        params["by_category"] = seed_data["category_id"]
    return params


def _apply_list_expectations(resp, case, params):
    """执行 YAML 声明的结果校验。"""
    body = resp.json()
    data = body["data"]

    if "expect_current_page" in case:
        assert_json_key(resp, "current_page", case["expect_current_page"])

    if case.get("expect_empty_data"):
        assert data == [], f"期望空 data，实际 {len(data)} 条"

    if case.get("expect_data_not_empty"):
        assert data, "期望非空 data，实际为空"

    if case.get("expect_all_brand_ids"):
        expected_brand = params["by_brand"]
        for p in data:
            assert p["brand"]["id"] == expected_brand, (
                f"product {p['id']} brand={p['brand']['id']} != {expected_brand}"
            )

    if case.get("expect_all_category_ids"):
        expected_cat = params["by_category"]
        for p in data:
            assert p["category"]["id"] == expected_cat, (
                f"product {p['id']} category={p['category']['id']} != {expected_cat}"
            )

    if case.get("expect_prices_in"):
        lo, hi = case["expect_prices_in"]
        for p in data:
            assert lo <= p["price"] <= hi, (
                f"product {p['id']} price={p['price']} 超出 [{lo},{hi}]"
            )
    if case.get("expect_sorted_by"):
        field, direction = case["expect_sorted_by"]
        assert_sorted(resp, field, direction)

def _pick(obj, path):
    """支持 'brand.id' 这种路径取值"""
    for key in path.split("."):
        obj = obj[key]
    return obj

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
    def test_get_products(self, req, seed_data, case):
        params = _resolve_list_params(case, seed_data)
        resp = ProductApi(req).get_products(**params)
        assert_status(resp, case["expect_status"])
        assert_key_exists(resp, "data")
        _apply_list_expectations(resp, case, params)

    # ---------- 详情 ----------
    @allure.story("产品详情")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_product_data()["detail"],
        ids=lambda c: c["case_name"],
    )
    def test_get_product_detail(self, req, real_product_id, case):
        product_id = real_product_id if case["product_id"] == "FROM_PRODUCT" else case["product_id"]
        resp = ProductApi(req).get_product(product_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_name"):
            assert_key_exists(resp, "name")

    # ---------- 相关产品 ----------
    @allure.story("相关产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("related"))
    def test_get_related(self, req, real_product_id, case):
        pid = real_product_id if case["product_id"] == "FROM_PRODUCT" else case["product_id"]
        resp = ProductApi(req).get_related(pid)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200 and case.get("expect_data_not_empty"):
            assert resp.json(), "相关产品为空"

    # ---------- 搜索 ----------
    @allure.story("产品搜索")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("search"))
    def test_search(self, req, case):
        resp = ProductApi(req).search(**case.get("params", {}))
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            _apply_list_expectations(resp, case, case.get("params", {}))

@allure.epic("Toolshop 接口自动化")
@allure.feature("产品模块-管理")
class TestProductAdmin:

    def _run_update(self, admin_req, real_brand_id, real_category_id,
                    real_product_image_id, case, method: str):
        """method = 'put' | 'patch'"""
        create_resp = ProductApi(admin_req).create(
            _build_product_payload(real_brand_id, real_category_id, real_product_image_id, {}))
        assert_status(create_resp, 201)
        created = create_resp.json()
        target_id = case.get("product_id") or created["id"]

        if method == "patch":
            payload = dict(case.get("partial_payload") or {})
            if payload.get("name") == "<auto>":
                payload["name"] = f"PATCH updated {_unique_product_suffix()}"
            resp = ProductApi(admin_req).patch(target_id, payload)
        else:  # put
            payload = _build_product_payload(real_brand_id, real_category_id,
                                            real_product_image_id, case)
            payload["name"] = f"PUT updated {_unique_product_suffix()}"
            for f in case.get("omit", []):
                payload.pop(f, None)
            resp = ProductApi(admin_req).update(target_id, payload)

        assert_status(resp, case["expect_status"])
        if case["expect_status"] != 200:
            return

        # PUT/PATCH 响应是 {"success": true}，不是产品对象，必须回查
        after = ProductApi(admin_req).get_product(target_id).json()
        for k in case.get("expect_changed", []):
            assert _pick(after, k) != _pick(created, k), (
                f"{k} 未变化：{_pick(after, k)}"
            )
        for k in case.get("expect_unchanged", []):
            assert _pick(after, k) == _pick(created, k), (
                f"{k} 被意外修改：{_pick(created, k)} -> {_pick(after, k)}"
            )
    @allure.story("创建产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("create"))
    def test_create_product(self, admin_req, real_brand_id, real_category_id,
                            real_product_image_id, case):
        payload = _build_product_payload(real_brand_id, real_category_id,
                                         real_product_image_id, case)
        resp = ProductApi(admin_req).create(payload)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    @allure.story("更新产品")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("update_put"))
    def test_update_put(self, admin_req, real_brand_id, real_category_id,
                        real_product_image_id, case):
        self._run_update(admin_req, real_brand_id, real_category_id,
                        real_product_image_id, case, "put")


    @pytest.mark.parametrize("case", _load_cases("update_patch"))
    def test_update_patch(self, admin_req, real_brand_id, real_category_id,
                        real_product_image_id, case):
        self._run_update(admin_req, real_brand_id, real_category_id,
                        real_product_image_id, case, "patch")

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
            assert_status(create_resp, 201)
            product_id = create_resp.json()["id"]

        resp = ProductApi(admin_req).delete(product_id)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 204:
            assert_status(ProductApi(admin_req).get_product(product_id), 404)
            assert_status(ProductApi(admin_req).delete(product_id), 404)

    @allure.story("删除产品-鉴权")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("delete_unauth"))
    def test_delete_product_unauth(self, req, admin_req, real_brand_id,
                                   real_category_id, real_product_image_id, case):
        create_resp = ProductApi(admin_req).create(
            _build_product_payload(real_brand_id, real_category_id,
                                   real_product_image_id, {}))
        assert_status(create_resp, 201)
        pid = create_resp.json()["id"]

        resp = ProductApi(req).delete(pid)      # 无 token
        assert_status(resp, case["expect_status"])

    @allure.story("删除产品-鉴权")
    @allure.title("{case_name}")
    @pytest.mark.parametrize("case", _load_cases("delete_forbidden"))
    def test_delete_product_forbidden(self, auth_req, admin_req, real_brand_id,
                                      real_category_id, real_product_image_id, case):
        create_resp = ProductApi(admin_req).create(
            _build_product_payload(real_brand_id, real_category_id,
                                   real_product_image_id, {}))
        assert_status(create_resp, 201)
        pid = create_resp.json()["id"]

        resp = ProductApi(auth_req).delete(pid)  # 普通用户 token
        assert_status(resp, case["expect_status"])
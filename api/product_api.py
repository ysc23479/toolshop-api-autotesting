# api/product_api.py
from utils.request_util import RequestUtil


class ProductApi:
    """产品资源封装。

    契约要点：
      - GET 公开；POST/PUT/PATCH/DELETE 需 admin
      - POST 成功 200（注意：与 brand/category 的 201 不同）
      - product 依赖真实的 category_id + brand_id
    """

    PATH = "/products"

    def __init__(self, req: RequestUtil):
        self.req = req

    # ---------- 公开接口 ----------
    def get_products(self, **params):
        return self.req.send("GET", self.PATH, params=params)

    def get_product(self, product_id):
        return self.req.send("GET", f"{self.PATH}/{product_id}")

    def get_related(self, product_id):
        return self.req.send("GET", f"{self.PATH}/{product_id}/related")

    # ---------- admin CRUD ----------
    def create(self, payload: dict):
        return self.req.send("POST", self.PATH, json=payload)

    def update(self, product_id, payload: dict):
        return self.req.send("PUT", f"{self.PATH}/{product_id}", json=payload)

    def delete(self, product_id):
        return self.req.send("DELETE", f"{self.PATH}/{product_id}")
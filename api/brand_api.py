# api/brand_api.py
from utils.request_util import RequestUtil


class BrandApi:
    """品牌资源封装。

    契约要点：
      - GET 公开
      - POST/PUT/DELETE 需 admin
      - POST 成功 201，slug 唯一（冲突 409）
    """

    PATH = "/brands"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        return self.req.send("GET", self.PATH)

    def get(self, brand_id):
        return self.req.send("GET", f"{self.PATH}/{brand_id}")

    def create(self, payload: dict):
        """POST /brands —— 接受任意 dict，支持"缺字段"等错误用例。

        之前签名 create(name, slug) 导致"缺 name"用例 TypeError，
        因为测试代码用 create(**payload) 展开，缺字段时参数不全。
        """
        return self.req.send("POST", self.PATH, json=payload)

    def update(self, brand_id, payload: dict):
        return self.req.send("PUT", f"{self.PATH}/{brand_id}", json=payload)

    def delete(self, brand_id):
        return self.req.send("DELETE", f"{self.PATH}/{brand_id}")
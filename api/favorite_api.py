# api/favorite_api.py
from utils.request_util import RequestUtil


class FavoriteApi:
    """收藏资源封装。

    契约要点（来自 swagger）：
      - POST 成功 200（不是 201），返回 {"product_id", "user_id", "id"}
      - 重复收藏返回 409（冲突）
      - 不存在的 product_id 返回 404
      - 未登录返回 401
      - GET/DELETE 均需登录（文档无 401 的接口未标，但语义上需要）
    """

    PATH = "/favorites"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        return self.req.send("GET", self.PATH)

    def add(self, product_id):
        return self.req.send("POST", self.PATH, json={"product_id": product_id})

    def get(self, favorite_id):
        return self.req.send("GET", f"{self.PATH}/{favorite_id}")

    def delete(self, favorite_id):
        return self.req.send("DELETE", f"{self.PATH}/{favorite_id}")
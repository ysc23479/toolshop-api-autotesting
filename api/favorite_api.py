from utils.request_util import RequestUtil


class FavoriteApi:
    """收藏资源封装"""

    PATH = "/favorites"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        """获取当前登录用户的全部收藏（需登录）。"""
        return self.req.send("GET", self.PATH)

    def add(self, product_id):
        """添加商品到收藏（需登录）。"""
        return self.req.send("POST", self.PATH, json={"product_id": product_id})

    def get(self, favorite_id):
        """获取指定收藏详情（需登录）。"""
        return self.req.send("GET", f"{self.PATH}/{favorite_id}")

    def delete(self, favorite_id):
        """删除指定收藏（需登录）。"""
        return self.req.send("DELETE", f"{self.PATH}/{favorite_id}")
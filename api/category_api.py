# api/category_api.py
from utils.request_util import RequestUtil


class CategoryApi:
    """分类资源封装。"""

    PATH = "/categories"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        return self.req.send("GET", self.PATH)

    def tree(self):
        return self.req.send("GET", f"{self.PATH}/tree")

    def get(self, category_id):
        return self.req.send("GET", f"{self.PATH}/tree/{category_id}")

    def create(self, payload: dict):
        """POST /categories —— 接受任意 dict，支持"缺字段"等错误用例。"""
        return self.req.send("POST", self.PATH, json=payload)

    def delete(self, category_id):
        return self.req.send("DELETE", f"{self.PATH}/{category_id}")
from utils.request_util import RequestUtil

class BrandApi:
    """品牌资源封装"""

    PATH = "/brands"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        """GET /brands —— 获取全部品牌"""
        return self.req.send("GET", self.PATH)

    def get(self, brand_id):
        """GET /brands/{brandId} —— 获取指定品牌"""
        return self.req.send("GET", f"{self.PATH}/{brand_id}")

    def create(self, payload: dict):
        """POST /brands —— 创建品牌"""
        return self.req.send("POST", self.PATH, json=payload)

    def update(self, brand_id, payload: dict):
        """PUT /brands/{brandId} —— 全量更新品牌"""
        return self.req.send("PUT", f"{self.PATH}/{brand_id}", json=payload)

    def delete(self, brand_id):
        """DELETE /brands/{brandId} —— 删除品牌 admin"""
        return self.req.send("DELETE", f"{self.PATH}/{brand_id}")
from utils.request_util import RequestUtil

class CategoryApi:
    """分类资源封装。"""

    PATH = "/categories"

    def __init__(self, req: RequestUtil):
        self.req = req

    def list(self):
        """GET /categories —— 获取全部分类（平铺）"""
        return self.req.send("GET", self.PATH)

    def tree(self, by_category_slug=None):
        """GET /categories/tree —— 获取分类树（含 sub_categories 嵌套）"""
        params = {}
        if by_category_slug is not None:
            params["by_category_slug"] = by_category_slug
        return self.req.send("GET", f"{self.PATH}/tree", params=params)

    def get(self, category_id):
        """GET /categories/tree/{categoryId} —— 获取指定分类（含子分类）"""
        return self.req.send("GET", f"{self.PATH}/tree/{category_id}")

    def create(self, payload: dict):
        """POST /categories —— 创建分类"""
        return self.req.send("POST", self.PATH, json=payload)

    def delete(self, category_id):
        """DELETE /categories/{categoryId} —— 删除分类 admin"""
        return self.req.send("DELETE", f"{self.PATH}/{category_id}")
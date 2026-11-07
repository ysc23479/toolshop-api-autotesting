from utils.request_util import RequestUtil


class ProductApi:
    """产品资源封装"""

    PATH = "/products"

    def __init__(self, req: RequestUtil):
        self.req = req

    def get_products(self, **params):
        """获取产品列表"""
        return self.req.send("GET", self.PATH, params=params)

    def get_product(self, product_id):
        """获取指定产品详情"""
        return self.req.send("GET", f"{self.PATH}/{product_id}")

    def get_related(self, product_id):
        """获取指定产品的相关产品"""
        return self.req.send("GET", f"{self.PATH}/{product_id}/related")
    
    def search(self, **params):
        """按名字关键词搜索产品，支持分页"""
        return self.req.send("GET", f"{self.PATH}/search", params=params)
    
    def create(self, payload: dict):
        """创建产品"""
        return self.req.send("POST", self.PATH, json=payload)

    def update(self, product_id, payload: dict):
        """全量更新指定产品"""
        return self.req.send("PUT", f"{self.PATH}/{product_id}", json=payload)
    
    def patch(self, product_id, payload: dict):
        """局部更新指定产品的部分字段"""
        return self.req.send("PATCH", f"{self.PATH}/{product_id}", json=payload)
    
    def delete(self, product_id):
        """删除指定产品：admin角色"""
        return self.req.send("DELETE", f"{self.PATH}/{product_id}")
from utils.request_util import RequestUtil

class CartApi:
    """购物车资源封装。一个方法对应一个接口"""

    PATH = "/carts"

    def __init__(self, req: RequestUtil):
        self.req = req

    def create_cart(self):
        """POST /carts —— 创建购物车"""
        return self.req.send("POST", self.PATH)

    def get_cart(self, cart_id):
        """GET /carts/{cartId} —— 查询购物车"""
        return self.req.send("GET", f"{self.PATH}/{cart_id}")

    def add_to_cart(self, cart_id, product_id, quantity=1):
        """POST /carts/{id} —— 加入购物车"""
        return self.req.send("POST", f"{self.PATH}/{cart_id}", json={
            "product_id": product_id,
            "quantity": quantity,
        })

    def update_quantity(self, cart_id, product_id, quantity):
        """PUT /carts/{cartId}/product/quantity —— 更新购物车商品数量"""
        return self.req.send("PUT", f"{self.PATH}/{cart_id}/product/quantity", json={
            "product_id": product_id,
            "quantity": quantity,
        })

    def delete_product(self, cart_id, product_id):
        """DELETE /carts/{cartId}/product/{productId} —— 删除购物车商品"""
        return self.req.send("DELETE", f"{self.PATH}/{cart_id}/product/{product_id}")

    def delete_cart(self, cart_id):
        """DELETE /carts/{cartId} —— 删除购物车"""
        return self.req.send("DELETE", f"{self.PATH}/{cart_id}")
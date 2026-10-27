# api/cart_api.py
from utils.request_util import RequestUtil


class CartApi:
    """购物车资源封装。一个方法对应一个接口。

    注意：POST /carts、POST /carts/{id}、GET /carts/{cartId} 在 swagger 里
    没有 401，说明匿名也可调用；DELETE /carts/{cartId} 和
    DELETE /carts/{cartId}/product/{productId} 需要登录，会返回 401。
    """

    PATH = "/carts"

    def __init__(self, req: RequestUtil):
        self.req = req

    def create_cart(self):
        """POST /carts —— 创建购物车，成功 201，返回 {"id": "..."}"""
        return self.req.send("POST", self.PATH)

    def get_cart(self, cart_id):
        """GET /carts/{cartId} —— 查询购物车"""
        return self.req.send("GET", f"{self.PATH}/{cart_id}")

    def add_to_cart(self, cart_id, product_id, quantity=1):
        """POST /carts/{id} —— 加购，成功 200，返回 {"result": "item added or updated"}"""
        return self.req.send("POST", f"{self.PATH}/{cart_id}", json={
            "product_id": product_id,
            "quantity": quantity,
        })

    def update_quantity(self, cart_id, product_id, quantity):
        """PUT /carts/{cartId}/product/quantity —— 更新数量，成功 200，返回 {"success": true}"""
        return self.req.send("PUT", f"{self.PATH}/{cart_id}/product/quantity", json={
            "product_id": product_id,
            "quantity": quantity,
        })

    def delete_product(self, cart_id, product_id):
        """DELETE /carts/{cartId}/product/{productId} —— 成功 204（无体）"""
        return self.req.send("DELETE", f"{self.PATH}/{cart_id}/product/{product_id}")

    def delete_cart(self, cart_id):
        """DELETE /carts/{cartId} —— 成功 204（无体）"""
        return self.req.send("DELETE", f"{self.PATH}/{cart_id}")
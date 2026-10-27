# api/payment_api.py
from utils.request_util import RequestUtil


class PaymentApi:
    """支付校验接口封装。

    注意：/payment/check 是"校验"接口，只验证 payment 参数合法性，
    不实际扣款、不创建订单。它和 POST /invoices 是两码事：
      - /payment/check 返回 {"message": "..."}，只做校验
      - /invoices       才真正下单

    同时承载 GET /payment-methods（原 InvoiceApi 里的方法迁移过来）。
    """

    PATH = "/payment"

    def __init__(self, req: RequestUtil):
        self.req = req

    def check(self, payload: dict):
        return self.req.send("POST", f"{self.PATH}/check", json=payload)

    def get_payment_methods(self):
        return self.req.send("GET", "/payment-methods")
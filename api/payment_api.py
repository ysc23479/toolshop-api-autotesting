from utils.request_util import RequestUtil

class PaymentApi:
    """支付校验接口封装。
    验证 payment 参数合法性，不实际扣款、不创建订单。
    """

    PATH = "/payment"

    def __init__(self, req: RequestUtil):
        self.req = req

    def check(self, payload: dict):
        return self.req.send("POST", f"{self.PATH}/check", json=payload)
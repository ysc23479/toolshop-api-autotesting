from utils.request_util import RequestUtil

class TotpApi:
    """TOTP 两步认证封装"""

    PATH = "/totp"

    def __init__(self, req: RequestUtil):
        self.req = req

    def setup(self):
        """POST /totp/setup —— 为当前登录用户生成 TOTP 密钥与 QR 码 URL """
        return self.req.send("POST", f"{self.PATH}/setup")

    def verify(self, access_token, totp_code):
        """POST /totp/verify —— 提交 6 位 TOTP 码完成启用"""
        return self.req.send("POST", f"{self.PATH}/verify", json={
            "access_token": access_token,
            "totp": totp_code,
        })
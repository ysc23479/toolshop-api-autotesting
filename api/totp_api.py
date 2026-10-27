# api/totp_api.py
from utils.request_util import RequestUtil


class TotpApi:
    """TOTP 两步认证封装。

    契约要点：
      - POST /totp/setup 需登录，返回 {"secret", "qrCodeUrl"}
      - POST /totp/verify 请求体 {"access_token": "...", "totp": "123456"}
        注意 access_token 在 header 已有，body 里再传一遍是冗余字段（可能是 bug）
        验证成功后启用 2FA，后续登录必须输入 6 位码
    """

    PATH = "/totp"

    def __init__(self, req: RequestUtil):
        self.req = req

    def setup(self):
        """POST /totp/setup —— 返回 {"secret": "...", "qrCodeUrl": "..."}"""
        return self.req.send("POST", f"{self.PATH}/setup")

    def verify(self, access_token, totp_code):
        """POST /totp/verify —— 请求体 {access_token, totp}"""
        return self.req.send("POST", f"{self.PATH}/verify", json={
            "access_token": access_token,
            "totp": totp_code,
        })

    def verify_without_token(self, totp_code):
        """POST /totp/verify —— 不传 access_token，探测字段是否真必填"""
        return self.req.send("POST", f"{self.PATH}/verify", json={
            "totp": totp_code,
        })
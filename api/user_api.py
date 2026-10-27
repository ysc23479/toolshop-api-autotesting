# api/user_api.py
from utils.request_util import RequestUtil


class UserApi:
    """用户资源统一封装。

    分层：
      - 鉴权：login / logout / refresh / me
      - 账号生命周期：register / forgot_password / change_password
      - 用户管理：list / get / update / delete / search（admin，待补）
    """

    PATH = "/users"

    def __init__(self, req: RequestUtil):
        self.req = req

    # ---------- 鉴权 ----------
    def login(self, email, password):
        """POST /users/login —— 无需登录"""
        return self.req.send("POST", f"{self.PATH}/login", json={
            "email": email,
            "password": password,
        })

    def logout(self):
        """GET /users/logout —— 需登录态"""
        return self.req.send("GET", f"{self.PATH}/logout")

    def refresh(self):
        """GET /users/refresh —— 需登录态"""
        return self.req.send("GET", f"{self.PATH}/refresh")

    def me(self):
        """GET /users/me —— 需登录态"""
        return self.req.send("GET", f"{self.PATH}/me")

    # ---------- 账号生命周期 ----------
    def register(self, payload: dict):
        """POST /users/register —— 无需登录。

        契约要点：
          - 成功 201，返回完整 user 对象
          - 邮箱重复 409
          - 密码被 haveibeenpwned 收录 422
          - 密码不合规（缺大写/数字/符号）422
        """
        return self.req.send("POST", f"{self.PATH}/register", json=payload)

    def forgot_password(self, email: str):
        """POST /users/forgot-password —— 无需登录。

        契约要点（swagger 已注明）：
          - 成功 200 {"success": true}
          - 实际行为：把密码重置为 "welcome02"
        """
        return self.req.send("POST", f"{self.PATH}/forgot-password", json={
            "email": email,
        })

    def change_password(self, current_password, new_password, new_password_confirmation):
        """POST /users/change-password —— 需登录态。

        契约要点：
          - 成功 200 {"success": true}
          - 旧密码错误 / 新密码不合规 422
          - 新旧密码相同 422
        """
        return self.req.send("POST", f"{self.PATH}/change-password", json={
            "current_password": current_password,
            "new_password": new_password,
            "new_password_confirmation": new_password_confirmation,
        })
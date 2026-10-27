import os
import allure
import pytest
import time
import uuid
from api.user_api import UserApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_key_not_exists,
    assert_json_key,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_user_data():
    return load_yaml("data/user_data.yaml")

def _wrap_cases_with_xfail(cases):
    """把 YAML 里 xfail: true 的用例转成 pytest.mark.xfail(strict=True)"""
    result = []
    for c in cases:
        if c.get("xfail"):
            result.append(pytest.param(
                c,
                marks=pytest.mark.xfail(reason=c.get("reason", ""), strict=True),
                id=c["case_name"],
            ))
        else:
            result.append(pytest.param(c, id=c["case_name"]))
    return result

def _resolve_credentials(case):
    """从 case 或环境变量解析登录凭证。

    规则（关键，不能写错）：
      - case 显式提供 email/password 时优先使用（用于构造非法输入，例如空邮箱、
        错密码）。注意空字符串也是"显式提供"，不能写成 `case.get("email") or ...`
      - 否则按 login_as 从 .env 读取 USER_* / ADMIN_*
    """
    email = case.get("email")
    password = case.get("password")
    login_as = case.get("login_as")

    if email is None and login_as:
        email = os.getenv("USER_EMAIL" if login_as == "user" else "ADMIN_EMAIL")
    if password is None and login_as:
        password = os.getenv("USER_PASSWORD" if login_as == "user" else "ADMIN_PASSWORD")

    return email or "", password or ""


@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-鉴权模块")
class TestLogin:

    # ---------- 登录（数据驱动）----------
    @allure.story("用户登录")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_user_data()["login"],
        ids=lambda c: c["case_name"],
    )
    def test_login(self, req, case):
        email, password = _resolve_credentials(case)
        resp = UserApi(req).login(email, password)

        assert_status(resp, case["expect_status"])

        if case["expect_has_token"]:
            assert_key_exists(resp, "access_token")
            assert_json_key(resp, "token_type", "bearer")
        else:
            assert_key_not_exists(resp, "access_token")
            if "expect_error" in case:
                assert_msg_contains(resp, case["expect_error"])

    # ---------- 登出（成功 + 未登录）----------
    # 重要：logout 会让当前 token 失效，必须用 ephemeral_auth_req，
    #       绝不能用 session 级的 auth_req，否则后续所有用例会变成 401
    @allure.story("用户登出")
    @allure.title("登出成功")
    def test_logout(self, ephemeral_auth_req):
        resp = UserApi(ephemeral_auth_req).logout()
        assert_status(resp, 200)
        assert_msg_contains(resp, "Successfully logged out")

    @allure.story("用户登出")
    @allure.title("未登录登出 → 401")
    def test_logout_unauthorized(self, req):
        resp = UserApi(req).logout()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")

    # ---------- 刷新 token ----------
    # 同样使用 ephemeral_auth_req：refresh 会让旧 token 失效（不确定时按失效处理）
    @allure.story("刷新 token")
    @allure.title("刷新 token 成功")
    def test_refresh(self, ephemeral_auth_req):
        resp = UserApi(ephemeral_auth_req).refresh()
        assert_status(resp, 200)
        assert_key_exists(resp, "access_token")
        assert_json_key(resp, "token_type", "bearer")

    # ---------- 当前用户（只读，可放心用 session 级 auth_req）----------
    @allure.story("当前用户")
    @allure.title("获取当前用户信息")
    def test_me(self, auth_req):
        resp = UserApi(auth_req).me()
        assert_status(resp, 200)
        # 已对照 swagger 确认：返回体至少包含 id / email / enabled
        assert_key_exists(resp, "id")
        assert_key_exists(resp, "email")

    @allure.story("当前用户")
    @allure.title("未登录获取当前用户 → 401")
    def test_me_unauthorized(self, req):
        resp = UserApi(req).me()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")
        # ---------- 密码错误（独立用例，用一次性账号）----------
    @allure.story("用户登录-密码错误")
    @allure.title("账号存在但密码错误 → 401")
    def test_login_wrong_password(self, req, throwaway_user):
        """真正的"密码错误"场景：账号存在，密码错。

        为什么用 throwaway_user：
          - 用户故事 AC4：3 次错误即锁定账号
          - 如果直接用 USER 账号，每跑一次这个测试 USER 就累积 1 次错误
          - 跑 3 次（或跨多轮测试累积）USER 被锁 → 所有依赖 USER 的用例全挂
          - throwaway_user 每次现场注册一个一次性账号，用完即弃

        变量控制：
          - 账号：存在（刚注册）
          - 密码：错误
          - 期望：401 Unauthorized
        """
        resp = UserApi(req).login(throwaway_user["email"], "wrong_password")
        assert_status(resp, 401)
        assert_key_not_exists(resp, "access_token")
        assert_msg_contains(resp, "Unauthorized")
# ============================================================
# 注册模块
# ============================================================
@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-注册模块")
class TestRegister:

    def _build_register_payload(self):
        """构造一份合法的注册 payload。email 带时间戳保证唯一。"""
        suffix = f"{int(time.time())}{uuid.uuid4().hex[:6]}"
        return {
            "first_name": "AutoReg",
            "last_name": "User",
            "address": {
                "street": "Test Street",
                "house_number": "10",
                "city": "New Joaquinberg",
                "state": "Arkansas",
                "country": "DM",
                "postal_code": "100000",
            },
            "phone": "0987654321",
            "dob": "1990-01-01",
            "password": "Kp9#Rt2!wQvX",
            "email": f"autoreg_{suffix}@example.org",
        }

    @allure.story("用户注册")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_user_data()["register"],
        ids=lambda c: c["case_name"],
    )
    def test_register(self, req, case):
        payload = self._build_register_payload()

        # 应用用例级覆盖
        if case.get("override"):
            payload.update(case["override"])
        # 应用字段删除
        for f in case.get("omit_fields", []):
            payload.pop(f, None)

        resp = UserApi(req).register(payload)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    @allure.story("用户注册")
    @allure.title("注册-重复邮箱 → 409")
    def test_register_duplicate_email(self, req):
        """验证邮箱唯一性。

        流程：先注册一个账号 → 用同一 email 再注册一次 → 期望 409。
        不依赖预置数据，每个账号都是现场生成的。
        """
        payload = self._build_register_payload()

        # 第一次注册 → 201
        first = UserApi(req).register(payload)
        assert_status(first, 201)

        # 第二次用同一 email → 409（swagger 明确）
        second = UserApi(req).register(payload)
        # 允许 409 或 422（有的实现把"已存在"归为验证错误返回 422）
        assert second.status_code in (409, 422), (
            f"重复邮箱注册应返回 409 或 422，实际 {second.status_code}: {second.text}"
        )


# ============================================================
# 密码模块（忘记密码 / 修改密码）
# 全部使用 throwaway_user fixture，避免污染主 USER 账号
# ============================================================
@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-密码模块")
class TestPassword:

    # ---------- 忘记密码 ----------
    @allure.story("忘记密码")
    @allure.title("{case_name}")
    @pytest.mark.slow 
    @pytest.mark.parametrize(
        "case",
        load_user_data()["forgot_password"],
        ids=lambda c: c["case_name"],
    )
    def test_forgot_password(self, req, case):
        # 正常场景用一次性账号；非正常场景（不存在的邮箱）用 case 里的 email
        if case.get("email"):
            email = case["email"]
        else:
            # 现场注册一个一次性账号，用它的 email
            import uuid
            suffix = f"{int(time.time())}{uuid.uuid4().hex[:6]}"
            email = f"forgot_{suffix}@example.org"
            reg_payload = {
                "first_name": "Forgot",
                "last_name": "Test",
                "address": {
                    "street": "Test Street", "house_number": "10",
                    "city": "New Joaquinberg", "state": "Arkansas",
                    "country": "DM", "postal_code": "100000",
                },
                "phone": "0987654321",
                "dob": "1990-01-01",
                "password": "Kp9#Rt2!wQvX",
                "email": email,
            }
            reg = UserApi(req).register(reg_payload)
            assert reg.status_code == 201, f"前置注册失败: {reg.text}"

        resp = UserApi(req).forgot_password(email)
        assert_status(resp, case["expect_status"])

    @allure.story("忘记密码")
    @allure.title("忘记密码-密码被重置为 welcome02（swagger 声明的实际行为）")
    def test_forgot_password_changes_password_to_welcome02(self, req, throwaway_user):
        """验证 forgot-password 的实际行为（swagger 明确写了这一点）。

        流程：
          1. 一次性账号已登录（fixture 完成）
          2. 调 forgot-password
          3. 用 welcome02 能登录（说明密码被重置）
          4. 用旧密码不能登录
        """
        resp = UserApi(req).forgot_password(throwaway_user["email"])
        assert_status(resp, 200)

        # 用 welcome02 登录 → 应该成功
        new_login = UserApi(req).login(throwaway_user["email"], "welcome02")
        assert new_login.status_code == 200, (
            f"forgot-password 后应能用 welcome02 登录，实际: {new_login.text}"
        )

        # 用旧密码登录 → 应该失败
        old_login = UserApi(req).login(throwaway_user["email"], throwaway_user["password"])
        assert old_login.status_code == 401, (
            f"forgot-password 后旧密码应失效，实际: {old_login.text}"
        )

    # ---------- 修改密码 ----------
    @allure.story("修改密码")
    @allure.title("{case_name}")
    @allure.issue("BUG-004: 两次新密码不一致应返回 422（请求体验证失败），实际返回 404 Resource not found。")
    @pytest.mark.slow 
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_user_data()["change_password"]),
        ids=lambda c: c["case_name"],
    )
    def test_change_password(self, req, throwaway_user, case):
        current = case.get("current_password") or throwaway_user["password"]
        new_pwd = case["new_password"]
        confirm = case.get("new_password_confirmation") or new_pwd

        resp = UserApi(throwaway_user["req"]).change_password(current, new_pwd, confirm)
        assert_status(resp, case["expect_status"])

        # 验证新密码能登录（仅正常改密码场景）
        if case.get("verify_login_with_new"):
            login = UserApi(req).login(throwaway_user["email"], new_pwd)
            assert login.status_code == 200, (
                f"改密码后新密码应能登录，实际: {login.text}"
            )
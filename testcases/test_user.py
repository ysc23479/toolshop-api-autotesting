import os
import allure
import pytest
import time
import uuid
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta
from api.user_api import UserApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_key_not_exists,
    assert_json_key,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml
from utils.auth_util import build_auth_req

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
    """从环境变量或yaml字段中解析登录凭证"""
    env_map = {
        "admin": ("ADMIN_EMAIL", "ADMIN_PWD"),
        "user": ("CUSTOMER_EMAIL", "CUSTOMER_PWD"),
        "user2": ("CUSTOMER2_EMAIL", "CUSTOMER2_PWD"),
        "user3": ("CUSTOMER3_EMAIL", "CUSTOMER3_PWD"),
    }
    login_as = case.get("login_as")
    if login_as:
        email_key, pwd_key = env_map.get(login_as, ("CUSTOMER_EMAIL", "CUSTOMER_PWD"))
        default_email = os.getenv(email_key) or ""
        default_pwd = os.getenv(pwd_key) or ""
    else:
        default_email = default_pwd = ""

    email = case["email"] if "email" in case else default_email
    password = case["password"] if "password" in case else default_pwd
    return email, password

# 鉴权模块
@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-鉴权模块")
class TestLogin:

    # ---------- 登录 ----------
    @allure.story("用户登录")
    @allure.title("{case[case_name]}")
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

    # ---------- 密码错误 ----------
    @allure.story("用户登录")
    @allure.title("异常登录-账号存在但密码错误")
    def test_login_wrong_password(self, req, throwaway_user):

        resp = UserApi(req).login(throwaway_user["email"], "wrong_password")
        assert_status(resp, 401)
        assert_key_not_exists(resp, "access_token")
        assert_msg_contains(resp, "Unauthorized")

    # ---------- 账号锁定 ----------
    @allure.story("用户登录")
    @allure.title("连续 3 次密码错误账号锁定")
    def test_login_locked_after_3_failures(self, req, throwaway_user):
        api = UserApi(req)
        email = throwaway_user["email"]
        wrong_pwd = "wrong_password"

        for i in range(3):
            with allure.step(f"第{i+1}次错误密码登录"):
                resp = api.login(email, wrong_pwd)
                assert_status(resp, 401)

        with allure.step("第4次尝试登录（账号已锁定，即使密码正确）"):
            resp = api.login(email, throwaway_user["password"])
            assert_status(resp, 423)
            allure.attach("Swagger文档未定义423", name="接口契约备注", attachment_type=allure.attachment_type.TEXT)

    @allure.story("用户登录")
    @allure.title("密码错2次后正确登录，失败计数重置，不会触发锁定")
    def test_login_success_resets_failure_count(self, req, throwaway_user):
        """
        业务规则：密码错误计数，在一次成功登录后清零。
        预期：密码错2次 → 正确登录成功 → 计数重置，再错2次不会锁定。
        """
        api = UserApi(req)
        email = throwaway_user["email"]
        wrong_pwd = "wrong_password"
        right_pwd = throwaway_user["password"]

        with allure.step("第1次错误登录"):
            assert_status(api.login(email, wrong_pwd), 401)
        with allure.step("第2次错误登录"):
            assert_status(api.login(email, wrong_pwd), 401)

        with allure.step("正确密码登录，校验登录成功，计数器重置"):
            resp = api.login(email, right_pwd)
            assert_status(resp, 200)
            assert_key_exists(resp, "access_token")

        with allure.step("重置后，再错2次，仍然没有到达锁定阈值"):
            assert_status(api.login(email, wrong_pwd), 401)
            assert_status(api.login(email, wrong_pwd), 401)

        with allure.step("第5次登录（密码正确）依然可以正常登录，账号未锁定"):
            resp = api.login(email, right_pwd)
            assert_status(resp, 200)

    # ---------- 登出 ----------
    # logout 会让当前 token 失效，须使用 ephemeral_auth_req
    @allure.story("用户登出")
    @allure.title("登出成功")
    def test_logout(self, ephemeral_auth_req):
        resp = UserApi(ephemeral_auth_req).logout()
        assert_status(resp, 200)
        assert_msg_contains(resp, "Successfully logged out")

    @allure.story("用户登出")
    @allure.title("未登录登出")
    def test_logout_unauthorized(self, req):
        resp = UserApi(req).logout()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")

    @allure.story("用户登出")
    @allure.title("登出后，使用已登出的token再次调用登出")
    def test_logout_twice_with_same_token(self, req, env_config, throwaway_user):
        """
        链路：登录 → 登出 → 使用同一个旧token再次登出
        预期：token销毁后，再次使用返回401
        """
        api = UserApi(req)
        email = throwaway_user["email"]
        pwd = throwaway_user["password"]

        with allure.step("1. 登录，拿到有效token"):
            resp_login = api.login(email, pwd)
            assert_status(resp_login, 200)
            old_token = resp_login.json()["access_token"]
            auth_req = build_auth_req(env_config, old_token)

        with allure.step("2. 第一次登出，token失效"):
            resp_logout = UserApi(auth_req).logout()
            assert_status(resp_logout, 200)

        with allure.step("3. 使用已经登出销毁的token，再次调用登出"):
            resp = UserApi(auth_req).logout()
            assert_status(resp, 401)
            assert_msg_contains(resp, "Unauthorized")

    @allure.story("用户登出")
    @allure.title("登出后，原token访问me接口")
    def test_logout_then_me_with_old_token(self, req, env_config, throwaway_user):
        """
        链路：登录 → 登出 → 旧token访问获取当前用户
        验证：登出销毁token，后续所有接口都不可用
        """
        api = UserApi(req)
        email = throwaway_user["email"]
        pwd = throwaway_user["password"]

        with allure.step("1. 登录获取token"):
            resp_login = api.login(email, pwd)
            old_token = resp_login.json()["access_token"]
            auth_req = build_auth_req(env_config, old_token)

        with allure.step("2. 执行登出"):
            UserApi(auth_req).logout()

        with allure.step("3. 旧token访问me接口"):
            resp = UserApi(auth_req).me()
            assert_status(resp, 401)

    # ---------- 刷新 token ----------
    # 同样使用 ephemeral_auth_req：refresh 会让旧 token 失效
    @allure.story("刷新 token")
    @allure.title("刷新 token 成功")
    def test_refresh(self, ephemeral_auth_req):
        resp = UserApi(ephemeral_auth_req).refresh()
        assert_status(resp, 200)
        assert_key_exists(resp, "access_token")
        assert_json_key(resp, "token_type", "bearer")
    
    @allure.story("刷新 token")
    @allure.title("登出后的token，调用刷新token")
    def test_refresh_with_logged_out_token(self, req,env_config, throwaway_user):
        """
        链路：登录 → 登出 → 使用旧token尝试刷新
        """
        api = UserApi(req)
        email = throwaway_user["email"]
        pwd = throwaway_user["password"]

        with allure.step("1. 登录拿到token"):
            resp_login = api.login(email, pwd)
            old_token = resp_login.json()["access_token"]
            auth_req = build_auth_req(env_config, old_token)

        with allure.step("2. 登出销毁token"):
            UserApi(auth_req).logout()

        with allure.step("3. 使用已登出token调用刷新"):
            resp = UserApi(auth_req).refresh()
            assert_status(resp, 401)

    @allure.story("刷新 token")
    @allure.title("刷新token成功后，旧token访问me")
    def test_refresh_old_token_invalid_for_me(self, req, env_config, throwaway_user):

        api = UserApi(req)
        email = throwaway_user["email"]
        pwd = throwaway_user["password"]

        with allure.step("1. 登录，拿到旧token"):
            resp_login = api.login(email, pwd)
            old_token = resp_login.json()["access_token"]
            old_auth_req = build_auth_req(env_config, old_token)

        with allure.step("2. 使用旧token刷新，拿到新token"):
            resp_refresh = UserApi(old_auth_req).refresh()
            assert_status(resp_refresh, 200)
            new_token = resp_refresh.json()["access_token"]

        with allure.step("3. 使用刷新前的旧token访问me"):
            resp = UserApi(old_auth_req).me()
            assert_status(resp, 401)

    # ---------- 当前用户 ----------
    @allure.story("当前用户")
    @allure.title("获取当前用户信息：检验字段完整性")
    def test_me(self, auth_req):
        resp = UserApi(auth_req).me()
        assert_status(resp, 200)
        expect_fields = ["id", "first_name", "last_name", "email", "totp_enabled", "created_at"]
        for field in expect_fields:
            assert_key_exists(resp, field)

    @allure.story("当前用户")
    @allure.title("未登录获取当前用户")
    def test_me_unauthorized(self, req):
        resp = UserApi(req).me()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")

    @allure.story("当前用户")
    @allure.title("获取当前用户信息：不返回敏感字段")
    def test_me_no_sensitive_fields(self, auth_req):
        """校验响应不会返回密码、totp密钥这类敏感信息"""
        resp = UserApi(auth_req).me()
        assert_status(resp, 200)
        forbid_fields = ["password", "totp_secret"]
        for field in forbid_fields:
            assert_key_not_exists(resp, field)


def set_nested_field(body: dict, field_path: str, value):
    """支持 address.street 这种嵌套路径赋值"""
    parts = field_path.split(".")
    target = body
    for p in parts[:-1]:
        if p not in target:
            target[p] = {}
        target = target[p]
    target[parts[-1]] = value

def generate_str(length: int) -> str:
    """生成指定长度测试字符串"""
    return "a" * length

def build_email(total_len: int) -> str:
    """构造总长度为 total_len 的邮箱"""
    suffix = "@test.com"
    prefix_len = total_len - len(suffix)
    if prefix_len < 1:
        raise ValueError("邮箱长度太短")
    rand = uuid.uuid4().hex[:8]
    if prefix_len <= len(rand):
        return (rand[:prefix_len] + suffix)[:total_len]
    return ("a" * (prefix_len - len(rand))) + rand + suffix

def calc_dob_by_age(age: int) -> str:
    """按年龄计算出生日期，返回 yyyy-MM-dd"""
    print(">>> calc_dob_by_age NEW VERSION, today =", date.today())
    birth_day = datetime.now(timezone.utc).date() - relativedelta(years=age)
    print(">>> utc dob =", birth_day)
    return birth_day.strftime("%Y-%m-%d")

def deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base

# 注册模块
@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-注册模块")
class TestRegister:

    
    def _build_register_payload(self, case: dict):
        if case.get("omit_body"):
            return None

        suffix = f"{int(time.time())}{uuid.uuid4().hex[:6]}"
        payload = {
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

        # 长度字段 str_len
        if "str_len" in case:
            cfg = case["str_len"]
            fld = cfg["field"]
            l = cfg["length"]
            set_nested_field(payload, fld, generate_str(l))

        # 年龄自动算dob
        if "age_years" in case:
            payload["dob"] = calc_dob_by_age(case["age_years"])

        # 指定邮箱总长度
        if "email_len" in case:
            payload["email"] = build_email(case["email_len"])

        # override 覆盖顶层key
        if case.get("override"):
            deep_merge(payload, case["override"])

        # 删除字段
        for f in case.get("omit_fields", []):
            payload.pop(f, None)

        return payload

    @allure.story("用户注册")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _wrap_cases_with_xfail(load_user_data()["register"]),
        ids=lambda c: c["case_name"],
    )
    def test_register(self, req, case):
        payload = self._build_register_payload(case)
        resp = UserApi(req).register(payload)
        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id") and case["expect_status"] == 201:
            assert_key_exists(resp, "id")

    @allure.story("用户注册")
    @allure.title("注册-重复邮箱")
    def test_register_duplicate_email(self, req):
        """验证邮箱唯一性。
        流程：先注册一个账号 → 用同一 email 再注册一次 → 期望 409。
        """
        dummy_case = {}
        with allure.step("1. 构造注册payload，首次注册"):
            payload = self._build_register_payload(dummy_case)
            first = UserApi(req).register(payload)
            assert_status(first, 201)

        with allure.step("2. 使用同一个邮箱再次注册，预期冲突"):
            second = UserApi(req).register(payload)
            # 允许 409/422（有的实现把"已存在"归为验证错误返回 422）
            assert second.status_code in (409, 422), (
                f"重复邮箱注册应返回 409/422，实际 {second.status_code}: {second.text}"
            )
    @allure.story("用户注册")
    @allure.title("注册-邮箱大小写重复，校验邮箱唯一性大小写敏感")
    def test_register_email_case_insensitive(self, req):
        """
        链路：小写邮箱注册成功 → 使用同一个邮箱大写版本再次注册
        """
        dummy_case = {}
        with allure.step("1. 构造payload，小写邮箱注册"):
            payload = self._build_register_payload(dummy_case)
            lower_email = payload["email"]
            resp1 = UserApi(req).register(payload)
            assert_status(resp1, 201)

        with allure.step("2. 邮箱改为大写，其他字段不变，再次注册"):
            payload["email"] = lower_email.upper()
            resp2 = UserApi(req).register(payload)
            assert resp2.status_code in (409, 422), (
                f"大小写邮箱冲突，预期409/422，实际 {resp2.status_code}: {resp2.text}"
            )



# 密码模块（忘记密码 / 修改密码）
# 全部使用 throwaway_user fixture
@allure.epic("Toolshop 接口自动化")
@allure.feature("用户-密码模块")
class TestPassword:

    # ---------- 忘记密码 ----------
    @allure.story("忘记密码")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        load_user_data()["forgot_password"],
        ids=lambda c: c["case_name"],
    )
    def test_forgot_password(self, req, case):
        # 正常场景用一次性账号；非正常场景用 case 里的 email
        if case.get("email"):
            email = case["email"]
        else:
            # 现场注册一个一次性账号，用它的 email
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
    @allure.title("忘记密码-密码被重置为 welcome02")
    def test_forgot_password_changes_password_to_welcome02(self, req, throwaway_user):
        """验证 forgot-password 的实际行为。

        流程：
          1. 一次性账号已登录
          2. 调 forgot-password
          3. 用 welcome02 能登录
          4. 用旧密码不能登录
        """
        resp = UserApi(req).forgot_password(throwaway_user["email"])
        assert_status(resp, 200)

        # 用 welcome02 登录应该成功
        new_login = UserApi(req).login(throwaway_user["email"], "welcome02")
        assert new_login.status_code == 200, (
            f"forgot-password 后应能用 welcome02 登录，实际: {new_login.text}"
        )

        # 用旧密码登录应该失败
        old_login = UserApi(req).login(throwaway_user["email"], throwaway_user["password"])
        assert old_login.status_code == 401, (
            f"forgot-password 后旧密码应失效，实际: {old_login.text}"
        )

    # ---------- 修改密码 ----------
    @allure.story("修改密码")
    @allure.title("{case[case_name]}")
    @allure.issue("BUG-004: 两次新密码不一致应返回 422（请求体验证失败），实际返回 404 Resource not found。")
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
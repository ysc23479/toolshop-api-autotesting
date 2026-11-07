import allure
import pytest

from api.user_api import UserApi
from utils.assert_util import (
    assert_status, assert_json_key, assert_msg_contains,
)
from utils.auth_util import build_auth_req


E2E_NEW_PHONE = "0987654322"
E2E_NEW_PWD = "E2ENewPwd@2026"


@allure.epic("Toolshop 接口自动化")
@allure.feature("业务流程-E2E")
@pytest.mark.e2e
class TestUserLifecycleFlow:

    @allure.story("用户生命周期")
    @allure.title("用户流程-注册→查me→改资料→改密→新密登录→登出→旧token失效")
    def test_user_lifecycle_full_flow(self, throwaway_user, env_config, req):

        old_auth_req = throwaway_user["req"]
        api = UserApi(old_auth_req)

        # ---------- Step 1: 查 me ----------
        with allure.step("Step 1: 查 me，确认新账号信息"):
            me_resp = api.me()
            assert_status(me_resp, 200)
            me = me_resp.json()
            user_id = me["id"]
            assert me["email"] == throwaway_user["email"]

        # ---------- Step 2: 改资料 ----------
        with allure.step("Step 2: 改资料，phone 改成新值"):
            patch_resp = api.patch(user_id, {"phone": E2E_NEW_PHONE})
            assert_status(patch_resp, 200)
            # 回查验证
            assert_json_key(api.me(), "phone", E2E_NEW_PHONE)

        # ---------- Step 3: 改密码 ----------
        with allure.step("Step 3: 改密码"):
            cp_resp = api.change_password(
                throwaway_user["password"], E2E_NEW_PWD, E2E_NEW_PWD,
            )
            assert_status(cp_resp, 200)

        # ---------- Step 4: 旧密码登录应 401 ----------
        with allure.step("Step 4: 旧密码登录 → 401"):
            old_login = UserApi(req).login(
                throwaway_user["email"], throwaway_user["password"],
            )
            assert_status(old_login, 401)

        # ---------- Step 5: 新密码登录 → 200 + 拿新 token ----------
        with allure.step("Step 5: 新密码登录 → 200"):
            new_login = UserApi(req).login(throwaway_user["email"], E2E_NEW_PWD)
            assert_status(new_login, 200)
            new_token = new_login.json()["access_token"]
            new_auth_req = build_auth_req(env_config, new_token)

        # ---------- Step 6: 新 token 可用 ----------
        with allure.step("Step 6: 新 token 查 me → 200"):
            assert_status(UserApi(new_auth_req).me(), 200)

        # ---------- Step 7: 改密后旧 token 行为 ----------
        with allure.step("Step 7: 改密后旧 token 查 me"):
            old_me = UserApi(old_auth_req).me()
            assert_status(old_me, 200)                      

            allure.attach(
                "改密码成功后，此前签发的旧 access_token 依然有效（实测 200）。\n"
                "\n"
                "业务上要求改密后用户被登出、旧 token 失效；实测未失效。\n"
                "\n"
                "API文档 未在 POST /users/change-password 响应中声明'是否撤销已签发 token'，属契约缺口。\n"
                "\n"
                "修复建议：服务端 change-password 成功后撤销该用户全部 active tokens。",
                name="安全性发现-改密未失效旧token",
                attachment_type=allure.attachment_type.TEXT,
            )

        # ---------- Step 8: 新 token 登出 ----------
        with allure.step("Step 8: 新 token 登出 → 200"):
            logout_resp = UserApi(new_auth_req).logout()
            assert_status(logout_resp, 200)
            assert_msg_contains(logout_resp, "Successfully logged out")

        # ---------- Step 9: 登出后的新 token → 401 ----------
        with allure.step("Step 9: 登出后再查 me → 401"):
            assert_status(UserApi(new_auth_req).me(), 401)
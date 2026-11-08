import allure
import pytest

from api.totp_api import TotpApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.totp_util import totp_now
from utils.yaml_util import load_yaml


def load_totp_data():
    return load_yaml("data/totp_data.yaml")


# ---------- 内部工具 ----------
def _param_with_marks(cases):
    """yaml case → pytest.param；xfail: true 时注入 mark.xfail(strict=True)。"""
    result = []
    for c in cases:
        marks = []
        if c.get("xfail"):
            marks.append(pytest.mark.xfail(reason=c.get("reason", ""), strict=True))
        result.append(pytest.param(c, marks=marks, id=c["case_name"]))
    return result


def _prepare_secret(totp_api: TotpApi) -> str:
    """调 setup 拿 secret；作为 verify 类用例的前置。"""
    resp = totp_api.setup()
    assert_status(resp, 200)
    return resp.json()["secret"]


def _resolve_code(secret: str, case: dict) -> str:
    """按 case 约定生成 code：
       - code_mode == "correct" → 当前时刻正确码
       - code_mode == "wrong"   → (正确码 + 1) % 10^6
       - 未指定 code_mode        → 直接用 case["code"]
    """
    mode = case.get("code_mode")
    if mode == "correct":
        return totp_now(secret)
    if mode == "wrong":
        correct = int(totp_now(secret))
        return str((correct + 1) % 1_000_000).zfill(6)
    return case.get("code", "")


@allure.epic("Toolshop 接口自动化")
@allure.feature("TOTP 两步认证模块")
class TestTotp:
    """所有 setup / verify / scenario 用例使用 throwaway_user，保证账号状态隔离。"""

    # ============ 1. TOTP 设置 ============
    @allure.story("TOTP 设置")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_totp_data()["setup"]),
    )
    def test_setup(self, throwaway_user, case):
        resp = TotpApi(throwaway_user["req"]).setup()
        assert_status(resp, case["expect_status"])

        if case.get("expect_has_secret"):
            assert_key_exists(resp, "secret")
            assert resp.json()["secret"], "secret 不能为空"
        if case.get("expect_has_qr_url"):
            assert_key_exists(resp, "qrCodeUrl")

    # ============ 2. TOTP 验证 ============
    @allure.story("TOTP 验证")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_totp_data()["verify"]),
    )
    def test_verify(self, throwaway_user, case):
        api = TotpApi(throwaway_user["req"])

        # 前置：setup 拿 secret
        secret = _prepare_secret(api)
        code = _resolve_code(secret, case)

        resp = api.verify(throwaway_user["token"], code)
        assert_status(resp, case["expect_status"])

        if case.get("expect_has_message"):
            assert_key_exists(resp, "message")
        if case.get("expect_error_contains"):
            assert_msg_contains(resp, case["expect_error_contains"])

    # ============ 3. 权限校验 ============
    @allure.story("权限校验")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_totp_data()["unauth"]),
    )
    def test_unauthorized(self, req, case):
        api = TotpApi(req)
        method = case["method"]

        if method == "setup":
            resp = api.setup()
        elif method == "verify":
            resp = api.verify("dummy-token", "123456")
        else:
            pytest.skip(f"未知方法: {method}")

        assert_status(resp, case["expect_status"])
        assert_msg_contains(resp, "Unauthorized")

    # ============ 4. 场景法：完整业务流程 ============
    @allure.story("完整业务流程")
    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_totp_data()["scenario"]),
    )
    def test_full_scenario(self, throwaway_user, case):
        api = TotpApi(throwaway_user["req"])

        # 1. setup 拿 secret
        setup_resp = api.setup()
        assert_status(setup_resp, case["expect_setup_status"])
        secret = setup_resp.json()["secret"]
        assert secret, "setup 未返回 secret"

        # 2. 用 secret 计算当前正确 code
        code = totp_now(secret)

        # 3. verify 启用
        verify_resp = api.verify(throwaway_user["token"], code)
        assert_status(verify_resp, case["expect_verify_status"])
        assert "message" in verify_resp.json(), (
            f"verify 响应缺 message 字段: {verify_resp.json()}"
        )
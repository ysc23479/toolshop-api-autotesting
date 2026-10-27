import allure
import pytest

from api.totp_api import TotpApi
from utils.assert_util import assert_status, assert_key_exists
from utils.totp_util import totp_now


@allure.epic("Toolshop 接口自动化")
@allure.feature("TOTP 两步认证模块")
class TestTotp:
    """所有用例必须用 throwaway_user fixture。

    原因：verify 成功后账号启用 2FA，后续登录必须输 TOTP 码。
    如果用 session 级 USER 账号，会把自己"锁死"。
    """

    @allure.story("TOTP 设置")
    @allure.title("setup 返回 secret 与 qrCodeUrl")
    def test_setup(self, throwaway_user):
        resp = TotpApi(throwaway_user["req"]).setup()
        assert_status(resp, 200)
        assert_key_exists(resp, "secret")
        assert_key_exists(resp, "qrCodeUrl")
        # secret 应该非空
        assert resp.json()["secret"], "secret 不能为空"

    @allure.story("TOTP 完整启用流程")
    @allure.title("setup + verify 成功启用 TOTP")
    def test_setup_and_verify(self, throwaway_user):
        """完整流程：setup 拿 secret → 计算 code → verify → 期望 200。"""
        setup_resp = TotpApi(throwaway_user["req"]).setup()
        assert_status(setup_resp, 200)
        secret = setup_resp.json()["secret"]

        # 用 secret 计算当前 6 位码
        code = totp_now(secret)

        resp = TotpApi(throwaway_user["req"]).verify(throwaway_user["token"], code)
        assert_status(resp, 200)
        # 成功响应：{"message": "TOTP enabled successfully"}
        assert_key_exists(resp, "message")

    @allure.story("TOTP 错误验证码")
    @allure.title("错误 TOTP 码 → 400")
    def test_verify_invalid_code(self, throwaway_user):
        # 先 setup 拿 secret（不 verify）
        setup_resp = TotpApi(throwaway_user["req"]).setup()
        assert_status(setup_resp, 200)

        # 传一个明显错误的码
        resp = TotpApi(throwaway_user["req"]).verify(throwaway_user["token"], "000000")
        # 400 表示验证码错误；如果碰巧 000000 跟当前时间算出的一致，会误判。
        # 概率极小（1/10^6），暂不处理
        assert_status(resp, 400)

    @allure.story("TOTP access_token 字段探测")
    @allure.title("verify 不带 access_token 字段 → 探测其是否必填")
    def test_verify_without_access_token_field(self, throwaway_user):
        """swagger 的 verify 请求体有 access_token 字段，但 header 已经带了 Authorization。

        这是契约冗余（可能是 bug）。本用例探测：
          - 若 200：说明 access_token 字段不是真必填，文档冗余
          - 若 400/422：说明字段真的必填，是冗余但强制的设计

        这个结果决定这条契约是否要登记到"契约偏差"章节。
        """
        setup_resp = TotpApi(throwaway_user["req"]).setup()
        assert_status(setup_resp, 200)
        secret = setup_resp.json()["secret"]
        code = totp_now(secret)

        resp = TotpApi(throwaway_user["req"]).verify_without_token(code)
        # 接受 200（字段可省略）或 4xx（字段必填），都算合法发现
        assert resp.status_code in (200, 400, 422), (
            f"意外状态码: {resp.status_code}, 响应: {resp.text}"
        )
        # 在断言消息里记录实测结果，方便人工登记契约
        assert True
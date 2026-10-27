import allure
import pytest

from api.message_api import MessageApi
from utils.assert_util import (
    assert_status,
    assert_key_exists,
    assert_msg_contains,
)
from utils.yaml_util import load_yaml


def load_message_data():
    return load_yaml("data/message_data.yaml")


BASE_PAYLOAD = {
    "name": "AutoTest User",
    "email": "autotest@example.org",
    "subject": "website",
    "message": "Something is wrong with the website. Please check.",
}


@allure.epic("Toolshop 接口自动化")
@allure.feature("消息模块")
class TestMessage:

    # ---------- 发送消息 ----------
    @allure.story("发送消息")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_message_data()["send"],
        ids=lambda c: c["case_name"],
    )
    def test_send_message(self, req, case):
        payload = dict(BASE_PAYLOAD)
        if case.get("payload"):
            payload.update(case["payload"])
        for f in case.get("omit", []):
            payload.pop(f, None)

        resp = MessageApi(req).send(payload)
        assert_status(resp, case["expect_status"])
        if case["expect_status"] == 200:
            assert_key_exists(resp, "id")
            assert_key_exists(resp, "status")

    # ---------- 列表 ----------
    @allure.story("消息列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        load_message_data()["list"],
        ids=lambda c: c["case_name"],
    )
    def test_list_messages(self, auth_req, admin_req, case):
        client = admin_req if case.get("login_as") == "admin" else auth_req
        resp = MessageApi(client).list()
        assert_status(resp, case["expect_status"])
        assert_key_exists(resp, "data")
        assert_key_exists(resp, "total")

    @allure.story("消息列表")
    @allure.title("未登录查消息 → 401")
    def test_list_messages_unauthorized(self, req):
        resp = MessageApi(req).list()
        assert_status(resp, 401)
        assert_msg_contains(resp, "Unauthorized")

    # ---------- 上传附件 ----------
    @allure.story("消息附件")
    @allure.title("上传 0KB .txt 附件成功")
    def test_attach_file(self, auth_req):
        """用户故事 AC4：仅接受 .txt、大小必须为 0 KB。

        流程：先用 auth_req 发一条消息 → 从 GET /messages 拿最新消息 id → 上传附件。

        "最新消息"的判断：按 created_at 或 id 排序取第一条。
        为了稳健，发消息后 sleep 1 秒，避免服务器时间精度问题。
        """
        import time
        # 1. 发一条消息（带 token 便于后续在 GET 中看到）
        send_payload = dict(BASE_PAYLOAD)
        send_payload["name"] = "Attach Test"
        MessageApi(auth_req).send(send_payload)
        time.sleep(1)

        # 2. 从 GET /messages 拿最新一条的 id
        list_resp = MessageApi(auth_req).list()
        assert_status(list_resp, 200)
        data = list_resp.json()["data"]
        assert data, "账号下没有任何消息，无法测试附件"
        message_id = data[0]["id"]

        # 3. 上传 0KB .txt
        resp = MessageApi(auth_req).attach_file(message_id, file_bytes=b"")
        assert_status(resp, 200)
        assert_key_exists(resp, "success")

    # ---------- 回复消息 ----------
    @allure.story("消息回复")
    @allure.title("回复一条消息")
    def test_reply_message(self, auth_req):
        import time
        # 1. 先发一条消息
        send_payload = dict(BASE_PAYLOAD)
        send_payload["name"] = "Reply Test"
        MessageApi(auth_req).send(send_payload)
        time.sleep(1)

        # 2. 拿 id
        list_resp = MessageApi(auth_req).list()
        data = list_resp.json()["data"]
        assert data, "账号下没有任何消息"
        message_id = data[0]["id"]

        # 3. 回复
        reply_payload = {
            "name": "AutoTest Admin",
            "email": "admin@example.org",
            "subject": "website",
            "message": "Reply from automated test.",
        }
        resp = MessageApi(auth_req).reply(message_id, reply_payload)
        assert_status(resp, 201)
        # swagger 说返回包含 message/id/created_at/user 字段
        assert_key_exists(resp, "id")
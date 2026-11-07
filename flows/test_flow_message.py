"""E2E：消息流转（登录用户）。"""
import time

import allure
import pytest

from api.message_api import MessageApi
from utils.assert_util import assert_status, assert_key_exists


BASE_PAYLOAD = {
    "name": "E2E Tester",
    "email": "e2e@example.org",
    "subject": "website",
    "message": "E2E test message. Something is wrong with the website.",
}


@allure.epic("Toolshop 接口自动化")
@allure.feature("业务流程-E2E")
@pytest.mark.e2e
class TestMessageFlow:

    @allure.story("消息流转")
    @allure.title("消息流程-发送→列表→详情→回复→附件→改状态")
    def test_message_full_flow(self, throwaway_user):
        api = MessageApi(throwaway_user["req"])

        with allure.step("Step 1: 发送消息"):
            payload = dict(BASE_PAYLOAD)
            payload["subject"] = f"e2e-{int(time.time())}"
            send_resp = api.send(payload)
            assert_status(send_resp, 200) 
            message_id = send_resp.json()["id"]
            allure.attach(message_id, name="message_id",
                          attachment_type=allure.attachment_type.TEXT)

        with allure.step("Step 2: 列表能找到"):
            time.sleep(1)  # 等落库
            list_resp = api.list()
            assert_status(list_resp, 200)
            data = list_resp.json().get("data", [])
            assert any(m["id"] == message_id for m in data), "列表里找不到刚发的消息"

        with allure.step("Step 3: 详情可查"):
            get_resp = api.get(message_id)
            assert_status(get_resp, 200)
            assert get_resp.json()["id"] == message_id

        with allure.step("Step 4: 回复"):
            reply_resp = api.reply(message_id, {
                "name": "E2E Admin",
                "email": "e2e-admin@example.org",
                "subject": "website",
                "message": "Reply from E2E flow.",
            })
            assert_status(reply_resp, 201)
            assert_key_exists(reply_resp, "id")

        with allure.step("Step 5: 附件（空文件）"):
            attach_resp = api.attach_file(
                message_id, file_bytes=b"",
                filename="e2e.txt", content_type="text/plain",
            )
            assert_status(attach_resp, 200)
            assert attach_resp.json().get("success") is True

        with allure.step("Step 6: 改状态 → IN_PROGRESS"):
            upd_resp = api.update_status(message_id, "IN_PROGRESS")
            assert_status(upd_resp, 200)
            assert upd_resp.json().get("success") is True

        with allure.step("Step 7: 再查详情，状态已变"):
            detail = api.get(message_id).json()
            assert detail["status"] == "IN_PROGRESS", (
                f"状态未更新，实际: {detail['status']}"
            )
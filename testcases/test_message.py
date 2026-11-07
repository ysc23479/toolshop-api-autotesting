import time

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

# 模块级缓存：多个用例复用同一条真实消息，避免每条都重新发送
_REAL_MESSAGE_ID = None


# ---------- 内部工具 ----------
def _expand(value):
    """支持 yaml 中 {repeat: "x", length: N} 边界值占位符。"""
    if isinstance(value, dict) and "repeat" in value:
        return value["repeat"] * int(value["length"])
    return value


def _build_payload(case: dict) -> dict:
    """按 case 中的 empty_payload / payload / omit 字段构造发送体。"""
    payload = {} if case.get("empty_payload") else dict(BASE_PAYLOAD)
    if case.get("payload"):
        payload.update({k: _expand(v) for k, v in case["payload"].items()})
    for f in case.get("omit", []):
        payload.pop(f, None)
    return payload


def _ensure_message_id(auth_req) -> str:
    """确保当前账号下至少有一条消息，返回最新一条 id（模块内缓存复用）。"""
    global _REAL_MESSAGE_ID
    if _REAL_MESSAGE_ID is not None:
        return _REAL_MESSAGE_ID

    payload = dict(BASE_PAYLOAD)
    payload["subject"] = f"autotest-{int(time.time())}"
    MessageApi(auth_req).send(payload)
    time.sleep(1)  # 等待落库

    resp = MessageApi(auth_req).list()
    data = resp.json().get("data", []) if resp.status_code == 200 else []
    assert data, f"账号下没有任何消息，无法继续: {resp.text}"
    _REAL_MESSAGE_ID = data[0]["id"]
    return _REAL_MESSAGE_ID

def _param_with_marks(cases):
    """case 里 xfail: true 时注入 xfail(strict=True)。
    strict=True：
      - 断言失败→ XFAIL，不算失败
      - 断言成功→ XPASS，strict 下算失败，提醒移除 xfail
    """
    result = []
    for c in cases:
        marks = []
        if c.get("xfail"):
            marks.append(pytest.mark.xfail(reason=c.get("reason", ""), strict=True))
        result.append(pytest.param(c, marks=marks, id=c["case_name"]))
    return result

@allure.epic("Toolshop 接口自动化")
@allure.feature("消息模块")
class TestMessage:

    # ============ 1. 发送消息 ============
    @allure.story("发送消息")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["send"]),
        ids=lambda c: c["case_name"],
    )
    def test_send_message(self, req, case):
        payload = _build_payload(case)
        resp = MessageApi(req).send(payload)

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):              
            assert_key_exists(resp, "id")
        if case.get("expect_success"):
            assert_key_exists(resp, "success")
            assert resp.json()["success"] is True, (
                f"success 字段应为 True，实际: {resp.json()}"
            )

    # ============ 2. 消息列表  ============
    @allure.story("消息列表")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["list"]),
        ids=lambda c: c["case_name"],
    )
    def test_list_messages(self, auth_req, admin_req, case):
        client = admin_req if case.get("login_as") == "admin" else auth_req
        resp = MessageApi(client).list(page=case.get("page"))

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_data"):
            assert_key_exists(resp, "data")
            assert_key_exists(resp, "total")

    # ============ 3. 获取单条消息 ============
    @allure.story("获取单条消息")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["get"]),
        ids=lambda c: c["case_name"],
    )
    def test_get_message(self, auth_req, case):
        if case.get("use_real_message"):
            message_id = _ensure_message_id(auth_req)
        else:
            message_id = case["message_id"]

        resp = MessageApi(auth_req).get(message_id)
        assert_status(resp, case["expect_status"])
        if case.get("expect_body_empty"):          
            assert resp.json() == [], (
                f"期望返回空列表，实际: {resp.json()}"
            )

    # ============ 4. 回复消息 ============
    @allure.story("回复消息")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["reply"]),
        ids=lambda c: c["case_name"],
    )
    def test_reply_message(self, auth_req, case):
        if case.get("use_real_message"):
            message_id = _ensure_message_id(auth_req)
        else:
            message_id = case["message_id"]

        payload = _build_payload(case)
        resp = MessageApi(auth_req).reply(message_id, payload)

        assert_status(resp, case["expect_status"])
        if case.get("expect_has_id"):
            assert_key_exists(resp, "id")
            assert_key_exists(resp, "message")

    # ============ 5. 上传附件 ============
    @allure.story("消息附件")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["attach"]),
        ids=lambda c: c["case_name"],
    )
    def test_attach_file(self, auth_req, case):
        if case.get("use_real_message"):
            message_id = _ensure_message_id(auth_req)
        else:
            message_id = case["message_id"]

        file_bytes = str(case.get("content", "")).encode()
        resp = MessageApi(auth_req).attach_file(
            message_id,
            file_bytes=file_bytes,
            filename=case.get("filename", "test.txt"),
            content_type=case.get("content_type", "text/plain"),
        )
        assert_status(resp, case["expect_status"])
        if case.get("expect_success"):
            assert_key_exists(resp, "success")
        if case.get("expect_error_contains"):    
                    body = resp.json()
                    actual = str(body.get("errors") or body.get("message") or body)
                    assert case["expect_error_contains"] in actual, (
                        f"错误信息不含 {case['expect_error_contains']}，实际: {actual}"
                    )

    # ============ 6. 权限校验 ============
    @allure.story("权限校验")
    @allure.title("{case_name}")
    @pytest.mark.parametrize(
        "case",
        _param_with_marks(load_message_data()["unauth"]),
        ids=lambda c: c["case_name"],
    )
    def test_unauthorized(self, req, case):
        api = MessageApi(req)
        method = case["method"]

        if method == "list":
            resp = api.list()
        elif method == "get":
            resp = api.get("any-id")
        elif method == "reply":
            resp = api.reply("any-id", dict(BASE_PAYLOAD))
        else:
            pytest.skip(f"未知方法: {method}")

        assert_status(resp, case["expect_status"])
        assert_msg_contains(resp, "Unauthorized")
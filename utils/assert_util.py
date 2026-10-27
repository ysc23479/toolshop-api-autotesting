# utils/assert_util.py
import allure
import requests


def assert_status(resp: requests.Response, expected: int = 200):
    """断言 HTTP 状态码"""
    with allure.step(f"断言状态码: 期望 {expected}, 实际 {resp.status_code}"):
        assert resp.status_code == expected, (
            f"状态码断言失败\n"
            f"期望: {expected}\n"
            f"实际: {resp.status_code}\n"
            f"响应体: {resp.text}"
        )


def assert_key_exists(resp: requests.Response, key: str):
    """断言 JSON 响应里存在某个字段"""
    body = resp.json()
    with allure.step(f"断言字段存在: {key}"):
        assert key in body, f"响应里不存在字段 {key}，完整响应: {body}"


def assert_key_not_exists(resp: requests.Response, key: str):
    """断言 JSON 响应里不存在某个字段"""
    body = resp.json()
    with allure.step(f"断言字段不存在: {key}"):
        assert key not in body, f"响应里不该存在字段 {key}，完整响应: {body}"


def assert_json_key(resp: requests.Response, key: str, expected):
    """断言 JSON 响应里某个字段的值"""
    body = resp.json()
    actual = body.get(key)
    with allure.step(f"断言字段 {key}: 期望 {expected}, 实际 {actual}"):
        assert key in body and actual == expected, (
            f"字段断言失败: {key}\n"
            f"期望: {expected}\n"
            f"实际: {actual}\n"
            f"完整响应: {body}"
        )


def assert_msg_contains(resp: requests.Response, expected_msg: str,field: str = None):
    """断言错误消息字段 message包含指定内容"""
    body = resp.json()
    if field:
        actual = body.get(field, "")
    else:
        actual = body.get("message") or body.get("error") or ""
    with allure.step(f"断言错误消息包含: {expected_msg}, 实际: {actual}"):
        assert expected_msg in actual, (
            f"错误消息不包含: {expected_msg}\n"
            f"实际: {actual}\n"
            f"完整响应: {body}"
        )
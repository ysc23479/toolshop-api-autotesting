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
    """断言错误消息字段 message 包含指定内容"""
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

def assert_response_time(resp: requests.Response, max_ms: int):
    """断言响应耗时不超过阈值（单位：毫秒）。
    """
    elapsed_ms = resp.elapsed.total_seconds() * 1000
    with allure.step(
        f"断言响应时间: 期望 <= {max_ms}ms, 实际 {elapsed_ms:.0f}ms"
    ):
        assert elapsed_ms <= max_ms, (
            f"响应时间超阈值\n"
            f"期望: <= {max_ms}ms\n"
            f"实际: {elapsed_ms:.0f}ms\n"
            f"请求: {resp.request.method} {resp.request.url}\n"
            f"状态码: {resp.status_code}"
        )

def assert_sorted(resp, field: str, direction: str = "asc", data_key: str = "data"):
    """断言响应里 data_key 列表按 field 有序（忽略 None 值）。

    :param direction: "asc" 或 "desc"
    """
    body = resp.json()
    data = body.get(data_key) or []
    values = [item[field] for item in data if item.get(field) is not None]
    expected = sorted(values, reverse=(direction == "desc"))
    with allure.step(f"断言 {data_key} 按 {field} {direction} 有序"):
        assert values == expected, (
            f"{field} 未按 {direction} 排序\n"
            f"实际: {values}\n"
            f"期望: {expected}"
        )
# api/message_api.py
from utils.request_util import RequestUtil


class MessageApi:
    """联系消息资源封装。

    契约要点：
      - POST /messages 公开（swagger 无 401）
      - GET /messages 需登录（admin 全看，user 看相关）
      - POST /messages/{id}/reply 需登录
      - POST /messages/{id}/attach-file 是 multipart/form-data，字段名 file，仅接受 0KB .txt
    """

    PATH = "/messages"

    def __init__(self, req: RequestUtil):
        self.req = req

    def send(self, payload: dict):
        """POST /messages —— 发送消息。成功 200 {"success": true}"""
        return self.req.send("POST", self.PATH, json=payload)

    def list(self, page=None):
        """GET /messages —— 分页"""
        params = {}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", self.PATH, params=params)

    def get(self, message_id):
        """GET /messages/{id}"""
        return self.req.send("GET", f"{self.PATH}/{message_id}")

    def reply(self, message_id, payload: dict):
        """POST /messages/{id}/reply —— 需登录"""
        return self.req.send("POST", f"{self.PATH}/{message_id}/reply", json=payload)

    def attach_file(self, message_id, file_bytes: bytes, filename="test.txt",
                    content_type="text/plain"):
        """POST /messages/{id}/attach-file —— multipart 上传。

        用户故事 AC4：仅接受 .txt、大小必须为 0 KB。
        默认传空 bytes（0KB .txt）作为合法数据。
        """
        files = {"file": (filename, file_bytes, content_type)}
        return self.req.send("POST", f"{self.PATH}/{message_id}/attach-file", files=files)
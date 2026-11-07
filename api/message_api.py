# api/message_api.py
from utils.request_util import RequestUtil


class MessageApi:
    """联系消息资源封装"""

    PATH = "/messages"

    def __init__(self, req: RequestUtil):
        self.req = req

    def send(self, payload: dict):
        """POST /messages —— 发送新的联系消息"""
        return self.req.send("POST", self.PATH, json=payload)

    def list(self, page=None):
        """GET /messages —— 获取消息列表(admin 看全部、普通 user 看仅与自己相关的)"""
        params = {}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", self.PATH, params=params)

    def get(self, message_id):
        """GET /messages/{messageId} —— 获取指定消息详情"""
        return self.req.send("GET", f"{self.PATH}/{message_id}")

    def reply(self, message_id, payload: dict):
        """POST /messages/{messageId}/reply —— 回复指定消息"""
        return self.req.send("POST", f"{self.PATH}/{message_id}/reply", json=payload)

    def attach_file(self, message_id, file_bytes: bytes, filename="test.txt",
                    content_type="text/plain"):
        """POST /messages/{messageId}/attach-file —— 给指定消息上传附件（multipart/form-data）"""
        files = {"file": (filename, file_bytes, content_type)}
        return self.req.send("POST", f"{self.PATH}/{message_id}/attach-file", files=files)
    
    def update_status(self, message_id, status: str):
        """PUT /messages/{messageId}/status —— 改消息状态（NEW/IN_PROGRESS/RESOLVED/ON_HOLD）"""
        return self.req.send(
            "PUT", f"{self.PATH}/{message_id}/status",
            json={"status": status},
        )
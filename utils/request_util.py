import requests
import allure

from utils.log_util import get_logger

logger = get_logger(__name__)

class RequestUtil:
    def __init__(self,base_url,timeout=10,refresh_callback=None, refresh_threshold=60):
        self.session = requests.Session()  # 保持会话，自动处理 cookie
        self.base_url = base_url
        self.timeout = timeout
        self.refresh_callback = refresh_callback       # 回调，返回新 token 或 None
        self.refresh_threshold = refresh_threshold     # 剩多少秒就刷新
    
    def _ensure_token_fresh(self):
        """请求前检查 token 剩余有效期，快过期或已过期就主动刷新"""
        if not self.refresh_callback:
            return
        auth = self.session.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return
        from utils.jwt_util import token_expires_in
        remaining = token_expires_in(auth.split(" ", 1)[1])

        # 解析失败跳过，避免每个请求都刷新
        if remaining == -1:
            return

        # 快过期或已过期刷新
        if remaining < self.refresh_threshold:
            new_token = self.refresh_callback()
            if new_token:
                self.session.headers["Authorization"] = f"Bearer {new_token}"
                logger.info(f"token 已自动续期（剩余 {remaining:.0f}s）")

    # 统一请求封装
    def send(self, method, path, **kwargs):
        self._ensure_token_fresh() 
        url = f"{self.base_url.rstrip('/') + '/' + path.lstrip('/')}" # 拼接URL
        kwargs.setdefault("timeout", self.timeout)

        # 请求前打日志
        logger.info(f"请求: {method} {url}")
        payload = next(
            (kwargs[k] for k in ("json", "params", "data", "files") if k in kwargs),
            "无",
        )
        logger.info(f"参数: {payload}")
        try:
            resp = self.session.request(method, url, **kwargs) #发送请求
        except requests.exceptions.Timeout as e:
            logger.error(f"请求超时: {method} {url}, 原因:{e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接失败: {method} {url}, 原因: {e}")
            raise
        except Exception as e:
            logger.error(f"请求异常: {method} {url}, 原因: {e}")
            raise

        # 响应后打日志
        elapsed_ms = resp.elapsed.total_seconds() * 1000
        if elapsed_ms >= 1000:
            elapsed_str = f"{elapsed_ms / 1000:.2f}s"
        else:
            elapsed_str = f"{elapsed_ms:.0f}ms"
        logger.info(f"响应: {resp.status_code}, 耗时: {elapsed_str}, 内容: {resp.text[:500]}")
        
        # 把请求信息附到 Allure 报告
        allure.attach(
            f"{method} {url}\n"
            f"请求体: {payload}",
            name="请求信息",
            attachment_type=allure.attachment_type.TEXT
        )

        # 把响应信息附到 Allure 报告
        allure.attach(
            f"状态码: {resp.status_code}\n"
            f"响应体: {resp.text}",
            name="响应信息",
            attachment_type=allure.attachment_type.TEXT
        )

        return resp #返回响应对象
    
import requests
import allure

from utils.log_util import get_logger

logger = get_logger(__name__)

class RequestUtil:
    def __init__(self,base_url,timeout=10):
        self.session = requests.Session()  # 保持会话，自动处理 cookie
        self.base_url = base_url
        self.timeout = timeout

    # 统一请求封装
    
    def send(self, method, path, **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)

        # 请求前打日志
        logger.info(f"请求: {method} {url}")
        for k in ("json", "params", "data", "files"):
            if k in kwargs:
                payload = kwargs[k]
                break
            else:
                payload = "无"
        logger.info(f"参数: {payload}")
        try:
            resp = self.session.request(method, url, **kwargs)
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
        logger.info(f"响应: {resp.status_code}, 内容: {resp.text[:300]}")
        
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

        return resp
    
from utils.request_util import RequestUtil


class InvoiceApi:
    """发票资源封装。一个方法对应一个接口。"""

    PATH = "/invoices"

    def __init__(self, req: RequestUtil):
        self.req = req

    # ---------- 查询 ----------
    def list(self, page=None):
        """GET /invoices —— admin 获取所有发票，user 只获取相关发票"""
        params = {}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", self.PATH, params=params)

    def get(self, invoice_id: str):
        """GET /invoices/{invoiceId} —— 获取指定发票"""
        return self.req.send("GET", f"{self.PATH}/{invoice_id}")

    def search(self, q: str, page=None):
        """GET /invoices/search —— 按 invoice_number/billing_street/status 搜索"""
        params = {"q": q}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", f"{self.PATH}/search", params=params)

    # ---------- 创建 ----------
    def create(self, payload: dict):
        """POST /invoices —— 创建新发票"""
        return self.req.send("POST", self.PATH, json=payload)

    def create_guest(self, payload: dict):
        """POST /invoices/guest —— 游客结账创建发票"""
        return self.req.send("POST", f"{self.PATH}/guest", json=payload)

    # ---------- 更新 ----------
    def update(self, invoice_id: str, payload: dict):
        """PUT /invoices/{invoiceId} —— 更新指定发票"""
        return self.req.send("PUT", f"{self.PATH}/{invoice_id}", json=payload)

    def patch(self, invoice_id: str, payload: dict):
        """PATCH /invoices/{invoiceId} —— 局部更新指定发票"""
        return self.req.send("PATCH", f"{self.PATH}/{invoice_id}", json=payload)

    def update_status(self, invoice_id: str, status: str, status_message=None):
        """PUT /invoices/{invoiceId}/status —— 更新发票状态"""
        return self.req.send("PUT", f"{self.PATH}/{invoice_id}/status", json={
            "status": status,
            "status_message": status_message,
        })

    # ---------- PDF ----------
    def get_pdf_status(self, invoice_number: str):
        """GET /invoices/{invoice_number}/download-pdf-status —— 查询 PDF 生成状态"""
        return self.req.send("GET", f"{self.PATH}/{invoice_number}/download-pdf-status")

    def download_pdf(self, invoice_number: str):
        """GET /invoices/{invoice_number}/download-pdf —— 下载已生成的 PDF"""
        return self.req.send("GET", f"{self.PATH}/{invoice_number}/download-pdf")
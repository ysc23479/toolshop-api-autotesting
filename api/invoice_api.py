# api/invoice_api.py
from utils.request_util import RequestUtil


class InvoiceApi:
    PATH = "/invoices"

    def __init__(self, req: RequestUtil):
        self.req = req

    # ---------- 查询 ----------
    def list(self, page=None):
        params = {}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", self.PATH, params=params)

    def get(self, invoice_id: str):
        return self.req.send("GET", f"{self.PATH}/{invoice_id}")

    def search(self, q: str, page=None):
        params = {"q": q}
        if page is not None:
            params["page"] = page
        return self.req.send("GET", f"{self.PATH}/search", params=params)

    # ---------- 创建 ----------
    def create(self, payload: dict):
        return self.req.send("POST", self.PATH, json=payload)

    def create_guest(self, payload: dict):
        return self.req.send("POST", f"{self.PATH}/guest", json=payload)

    # ---------- 更新 ----------
    def update(self, invoice_id: str, payload: dict):
        return self.req.send("PUT", f"{self.PATH}/{invoice_id}", json=payload)

    def update_status(self, invoice_id: str, status: str, message: str = ""):
        return self.req.send("PUT", f"{self.PATH}/{invoice_id}/status", json={
            "status": status,
            "status_message": message,
        })

    # ---------- PDF（注意用 invoice_number）----------
    def get_pdf_status(self, invoice_number: str):
        return self.req.send("GET", f"{self.PATH}/{invoice_number}/download-pdf-status")

    def download_pdf(self, invoice_number: str):
        return self.req.send("GET", f"{self.PATH}/{invoice_number}/download-pdf")

    # get_payment_methods 已删除：/payment-methods 属 Payment 资源，
    # 阶段 2 会新建 api/payment_api.py 承载它以及 /payment/check
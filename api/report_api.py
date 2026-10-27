# api/report_api.py
from utils.request_util import RequestUtil


class ReportApi:
    """报表资源封装。

    契约要点：
      - 所有接口需 admin token（普通用户 403）
      - GET /reports/total-sales-of-years 返回数组 [{year, total}]
    """

    PATH = "/reports"

    def __init__(self, req: RequestUtil):
        self.req = req

    def total_sales_of_years(self, years=None):
        params = {}
        if years is not None:
            params["years"] = years
        return self.req.send("GET", f"{self.PATH}/total-sales-of-years", params=params)

    def total_sales_per_country(self):
        return self.req.send("GET", f"{self.PATH}/total-sales-per-country")

    def top10_purchased_products(self):
        return self.req.send("GET", f"{self.PATH}/top10-purchased-products")

    def top10_best_selling_categories(self):
        return self.req.send("GET", f"{self.PATH}/top10-best-selling-categories")
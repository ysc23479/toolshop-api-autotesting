# api/report_api.py
from utils.request_util import RequestUtil


class ReportApi:
    """报表资源封装，所有接口均需 admin 角色"""

    PATH = "/reports"

    def __init__(self, req: RequestUtil):
        self.req = req

    def total_sales_of_years(self, years=None):
        """GET /reports/total-sales-of-years —— 获取最近 N 年每年销售总额"""
        params = {}
        if years is not None:
            params["years"] = years
        return self.req.send("GET", f"{self.PATH}/total-sales-of-years", params=params)

    def total_sales_per_country(self):
        """GET /reports/total_sales_per_country —— 按国家统计销售总额"""
        return self.req.send("GET", f"{self.PATH}/total-sales-per-country")

    def top10_purchased_products(self):
        """GET /reports/top10_purchased_products —— 购买次数 Top10 产品"""
        return self.req.send("GET", f"{self.PATH}/top10-purchased-products")

    def top10_best_selling_categories(self):
        """GET /reports/top10_best_selling_categories —— 销售额 Top10 分类"""
        return self.req.send("GET", f"{self.PATH}/top10-best-selling-categories")
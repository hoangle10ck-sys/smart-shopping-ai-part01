from app.services.collectors.http_collector import HTTPMarketplaceCollector


class ShopeeCollector(HTTPMarketplaceCollector):
    def __init__(self, **kwargs):
        super().__init__("shopee", **kwargs)

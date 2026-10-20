from app.services.collectors.http_collector import HTTPMarketplaceCollector


class LazadaCollector(HTTPMarketplaceCollector):
    def __init__(self, **kwargs):
        super().__init__("lazada", **kwargs)

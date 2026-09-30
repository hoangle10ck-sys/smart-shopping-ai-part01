"""Local noisy-search fixtures; fictional URLs, never substitute Live evidence."""
import asyncio
from urllib.parse import urlsplit

from app.schemas.requirement import RequirementData, RequirementItem
from app.services.search.base import SearchResult
from app.services.extraction.product_page_validator import inspect_page
from tests.fixtures.sales_pages import sales_page


def phone_requirement():
    return RequirementData(category='điện thoại', budget_max=10000000, budget_mode='FLEXIBLE_TARGET',
        budget_target=10000000, preferred_min=9400000, preferred_max=10600000,
        requirements=[RequirementItem(name='camera', value='tốt', priority=4),
                      RequirementItem(name='battery', value='pin lâu', priority=4)])


def product(number):
    return SearchResult(title=f'Samsung Galaxy A{number} 128GB',
        url=f'https://merchant{number % 3}.example/products/samsung-galaxy-a{number}-128gb',
        content=f'Điện thoại Samsung Galaxy A{number} 128GB giá bán 10.000.000 VND. Mua ngay.')


def editorial(number):
    return SearchResult(title='Top điện thoại: Samsung Galaxy A50, Samsung Galaxy A51',
        url=f'https://guide.example/news/phone-guide-{number}',
        content='Samsung Galaxy A50 camera OIS. Samsung Galaxy A51 pin lâu. Bài đánh giá nhiều sản phẩm.')


class NoisyProvider:
    def __init__(self, supply=5, delay=.002):
        self.calls, self.supply, self.delay = [], supply, delay

    async def search(self, query, max_results):
        self.calls.append(query)
        call = len(self.calls)
        await asyncio.sleep(self.delay)
        if '"' in query or query.startswith('site:'):
            return [product(n) for n in range(50, 50 + self.supply)]
        rows = [editorial(call * 5 + i) for i in range(5)]
        if call == 1: rows[-1] = product(49)  # Verified, but out of stock.
        return rows


class LocalPages:
    def __init__(self, delay=.002, price=10000000, initial_in_stock=False):
        self.calls, self.delay = [], delay
        self.price, self.initial_in_stock = price, initial_in_stock

    async def html(self, url):
        self.calls.append(url)
        await asyncio.sleep(self.delay)
        if '/news/' in url:
            return url, ('<h1>Top điện thoại</h1><script type="application/ld+json">'
                         '{"@type":"NewsArticle"}</script><p>Samsung Galaxy A50 camera tốt</p>')
        number = int(urlsplit(url).path.rsplit('-a', 1)[1].split('-')[0])
        return url, sales_page(name=f'Samsung Galaxy A{number} 128GB', price=self.price,
            brand='Samsung', model=f'Galaxy A{number}', category='điện thoại',
            offers={'@type':'Offer', 'price':self.price, 'priceCurrency':'VND',
                    'seller':{'name':urlsplit(url).hostname},
                    'availability':'https://schema.org/' + ('OutOfStock' if number == 49 and not self.initial_in_stock else 'InStock')},
            additionalProperty=[{'name':'camera','value':'50 MP OIS'}, {'name':'battery','value':'5500 mAh'}])

    async def inspect(self, url, **kwargs):
        _, html = await self.html(url)
        return inspect_page(url, html)

    async def _image_loads(self, url): raise AssertionError('No image evidence in fixture')

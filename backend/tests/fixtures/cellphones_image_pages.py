"""Observed product values/CDN envelope; synthetic DOM, NOT captured Live HTML.

Product values come from session 8a713af2. The cdn2.cellphones.com.vn /200x/media/
catalog/product envelope is present in archived fixtures. Opaque filenames and
gallery DOM are intentionally synthetic protocol/ownership cases.
"""
import json
from tests.fixtures.sales_pages import sales_page

PRODUCTS = [
    ('OPPO Reno14 5G 12GB 256GB', 'oppo-reno14', 'OPPO', 15500000),
    ('POCO X8 Pro Max 12GB 256GB', 'xiaomi-poco-x8-pro-max', 'Xiaomi', 13990000),
    ('Samsung Galaxy S25 Ultra 12GB 256GB', 'samsung-galaxy-s25-ultra', 'Samsung', 25990000),
]
OPAQUE = 'https://cdn2.cellphones.com.vn/200x/media/catalog/product/a/b/ab93e80f.webp?width=600&quality=90'


def page(index=0, pattern='json_ld'):
    name, slug, brand, price = PRODUCTS[index]
    url = f'https://cellphones.com.vn/dien-thoai-{slug}.html'
    html = sales_page(name=name, price=price, brand=brand, sku=slug,
                      image=OPAQUE if pattern == 'json_ld' else None)
    if pattern == 'og':
        html += f'<meta property="og:image" content="{OPAQUE}">'
    if pattern in {'gallery', 'picture', 'cross_product', 'carousel'}:
        owner = url if pattern != 'cross_product' else 'https://cellphones.com.vn/dien-thoai-another.html'
        html += f'<div itemscope itemtype="https://schema.org/Product" itemid="{owner}"><div class="product-gallery">'
        if pattern == 'carousel': html += '<div class="related-products">'
        if pattern == 'picture':
            html += f'<picture><source type="image/webp" data-srcset="{OPAQUE} 1x"><img src="/placeholder.png"></picture>'
        else:
            html += f'<img data-original="{OPAQUE}" src="/placeholder.png">'
        if pattern == 'carousel': html += '</div>'
        html += '</div></div>'
    return url, html

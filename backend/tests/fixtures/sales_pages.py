"""Local retailer HTML, never fetched from the Internet in automated tests."""
import json


def sales_page(name='Phone Model 15 128GB', price=9000000, image=None, **extra):
    product = {'@context': 'https://schema.org', '@type': 'Product', 'name': name,
               'offers': {'@type': 'Offer', 'price': price, 'priceCurrency': 'VND',
                          'seller': {'name': 'Test Merchant'}, 'availability': 'https://schema.org/InStock'},
               **extra}
    if image: product['image'] = image
    return f'<html><title>{name}</title><h1>{name}</h1><script type="application/ld+json">{json.dumps(product)}</script><button>Mua ngay</button></html>'

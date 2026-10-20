# Crawler source feasibility matrix

Checked: 2026-10-16. A public URL or API description is not, by itself,
permission to collect or reuse a merchant's product data. No product-page or
storefront product API was queried during this feasibility check.

| Source | Domain / interface | Robots, terms, access | Auth / limits | Example product / observed evidence | Decision |
|---|---|---|---|---|---|
| WooCommerce Store API | Domain is merchant-specific; documented endpoint is `/wp-json/wc/store/v1/products` | Official docs describe public published-product data. They do not grant permission for every store using WooCommerce; each merchant's terms/robots must be checked and entered in the registry. | Docs describe public read access. Per-store policy and rate limits remain merchant-specific. | No merchant selected; no product URL, API response, SKU, or price recorded. Official API docs: https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/ | Adapter target only; no live source is approved by default. |
| Best Buy Developer API | `api.bestbuy.com`, official Products API | Developer terms reviewed 2026-10-16. Use requires accepting the API terms; the terms restrict using content for third-party analysis/review of Best Buy pricing, products, or services. | API key required. | No API request made and no key present. Docs: https://developer.bestbuy.com/apis ; terms: https://developer.bestbuy.com/legal | Not approved for this comparison use case; do not register or enable. |
| Quotes to Scrape JS sandbox | `quotes.toscrape.com/js/` | The operator's `sites.toscrape.com` page explicitly describes it as a web-scraping sandbox and identifies the JavaScript endpoint. Robots was checked by secure preflight on 2026-10-16. | No auth; one bounded smoke request. | HTTP 200; JS-rendered DOM 8,985 bytes; 10 requests observed; one off-host font blocked; no product data. | Approved only as an independent browser runtime smoke source. It is not a merchant/product Live source and contributes zero Product/Offer records. |
| Adafruit | `www.adafruit.com`, public product pages; robots file also identifies `/api/` as disallowed | `https://www.adafruit.com/robots.txt` was read on 2026-10-15: `/api/` is disallowed for `User-agent: *`; `/product/` is not listed as disallowed. The public terms page was reviewed, but no explicit automated-collection permission was established. A sitemap was readable; no product page was fetched. | No API credentials evaluated. No per-host crawl allowance established. | No URL or price was captured. Terms: https://www.adafruit.com/terms_of_service ; robots: https://www.adafruit.com/robots.txt | Not approved: permission is unclear; fail closed. Do not request product pages until the merchant's permission basis is established. |
| Open Food Facts | `world.openfoodfacts.org`, product API | API docs require reviewing terms/ODbL and ask API users to submit an API-usage form. Dataset is food, not the electronics category targeted by the current recommendation scenarios. | Read calls require a custom identifying User-Agent; API docs state read calls do not require authentication. Rate limits apply. | No product API request made; usage form was not submitted. Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/ | Not used for this electronics pilot; not registered. |
| Shopee Vietnam | `shopee.vn` | Existing [collector policy](collector-policy.md) records written-consent restrictions for automated collection and no permission evidence in the repository. | No authenticated access or bypass attempted. | No live request. | `ACCESS_RESTRICTED`; keep collector disabled absent applicable written permission. |
| Lazada Vietnam | `lazada.vn` | Existing [collector policy](collector-policy.md) records restrictions on unauthorized automation; no permission evidence in the repository. | No authenticated access or bypass attempted. | No live request. | `ACCESS_RESTRICTED`; keep collector disabled absent applicable permission. |

## Feasibility outcome

- Public API implementation can be tested offline, but no named electronics
  merchant is approved for Live collection yet.
- Live status: `LIVE_NOT_VERIFIED` for this track. Live product URLs read: 0;
  verified products saved: 0; verified offers saved: 0.
- Do not treat Tavily results, fixtures, documentation examples, or sitemap URLs
  as verified product/price evidence.

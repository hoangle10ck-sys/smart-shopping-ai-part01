# Crawler source feasibility matrix

Checked: 2026-10-29. A public URL or API description is not, by itself,
permission to collect or reuse a merchant's product data. No merchant
product page or storefront API was queried. The Open Facts checks below were
read-only API requests for research-source feasibility. A later bounded Research-only
Open Products Facts sample is documented in the update below; no merchant records were saved.

| Source | Domain / interface | Robots, terms, access | Auth / limits | Example product / observed evidence | Decision |
|---|---|---|---|---|---|
| WooCommerce Store API | Domain is merchant-specific; documented endpoint is `/wp-json/wc/store/v1/products` | Official docs describe public published-product data. They do not grant permission for every store using WooCommerce; each merchant's terms/robots must be checked and entered in the registry. | Docs describe public read access. Per-store policy and rate limits remain merchant-specific. | No merchant selected; no product URL, API response, SKU, or price recorded. Official API docs: https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/ | Adapter target only; no live source is approved by default. |
| Best Buy Developer API | `api.bestbuy.com`, official Products API | Developer terms reviewed 2026-10-16. Use requires accepting the API terms; the terms restrict using content for third-party analysis/review of Best Buy pricing, products, or services. | API key required. | No API request made and no key present. Docs: https://developer.bestbuy.com/apis ; terms: https://developer.bestbuy.com/legal | Not approved for this comparison use case; do not register or enable. |
| Quotes to Scrape JS sandbox | `quotes.toscrape.com/js/` | The operator's `sites.toscrape.com` page explicitly describes it as a web-scraping sandbox and identifies the JavaScript endpoint. Robots was checked by secure preflight on 2026-10-16. | No auth; one bounded smoke request. | HTTP 200; JS-rendered DOM 8,985 bytes; 10 requests observed; one off-host font blocked; no product data. | Approved only as an independent browser runtime smoke source. It is not a merchant/product Live source and contributes zero Product/Offer records. |
| Adafruit | `www.adafruit.com`, public product pages; robots file also identifies `/api/` as disallowed | `https://www.adafruit.com/robots.txt` was read on 2026-10-15: `/api/` is disallowed for `User-agent: *`; `/product/` is not listed as disallowed. The public terms page was reviewed, but no explicit automated-collection permission was established. A sitemap was readable; no product page was fetched. | No API credentials evaluated. No per-host crawl allowance established. | No URL or price was captured. Terms: https://www.adafruit.com/terms_of_service ; robots: https://www.adafruit.com/robots.txt | Not approved: permission is unclear; fail closed. Do not request product pages until the merchant's permission basis is established. |
| Open Food Facts | `world.openfoodfacts.org`, food-product API | Database ODbL, contents DCL, images CC BY-SA; official docs disclaim completeness/accuracy guarantees and ask API users to read reuse terms and submit the API-usage form. | Custom identifying User-Agent; read API needs no authentication. Limits: 15 product reads/minute and 10 searches/minute. | Read-only staging search `coffee`, page size 5: HTTP 200 JSON, total 15,995, sample 5/5 named and imaged, all `product_type=food`. No records saved. API docs: https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/ | Suitable only as optional food Research data, not as electronics or current-price/stock evidence. API form not submitted; no import. |
| Open Products Facts | `world.openproductsfacts.org`, non-food sibling API | Official documentation calls the sibling APIs experimental and says behavior may change; common API behavior follows Open Food Facts. Product-data licensing and attribution are recorded in the Research importer and UI. | Barcode lookup is documented. Legacy text search was verified with one bounded read-only query; staging hostname did not resolve in this environment. | Initial production search: 11 records total. The 2026-10-29 bounded sample update below records the subsequent 11 imported Research rows. Docs: https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/tutorials/scanning-cosmetics-pet-food-and-other-products/ | Bounded Research use only, with attribution; not approved as a merchant collector source. Current price, stock, seller offers and ratings are not established. |
| Shopee Vietnam | `shopee.vn` | Existing [collector policy](collector-policy.md) records written-consent restrictions for automated collection and no permission evidence in the repository. | No authenticated access or bypass attempted. | No live request. | `ACCESS_RESTRICTED`; keep collector disabled absent applicable written permission. |
| Lazada Vietnam | `lazada.vn` | Existing [collector policy](collector-policy.md) records restrictions on unauthorized automation; no permission evidence in the repository. | No authenticated access or bypass attempted. | No live request. | `ACCESS_RESTRICTED`; keep collector disabled absent applicable permission. |

## Feasibility outcome

- Public API implementation can be tested offline, but no named electronics
  merchant is approved for Live collection yet.
- Live status: `LIVE_NOT_VERIFIED` for this track. Live merchant product URLs read: 0;
  LIVE-verified products saved: 0; verified offers saved: 0. The Open Products Facts
  rows below are Research records, not LIVE-verified products or offers.
- Do not treat Tavily results, fixtures, documentation examples, or sitemap URLs
  as verified product/price evidence.

## Bounded Research sample update — 2026-10-29

- The user approved a small Research catalog sample with source attribution and
  separate database/image license notices; prices, stock, ratings, reviews, and Offers
  must remain absent.
- Open Food Facts production search `coffee`, capped at 25: HTTP 503. No retry was made
  and no food records were imported. Earlier staging smoke evidence above remains a
  separate staging result.
- Open Products Facts production search `laptop`, capped at 25: HTTP 200 JSON, 11
  records; 11 had names and valid barcodes, 7 had official image URLs. Six had an
  explicit `Laptops` source category. Other records retain an unclassified category;
  category is not inferred from a query match or product title.
- Importer dry-run: 11 selected/importable, zero invalid/duplicate, 7 images, zero
  price/Offer rows. Local PostgreSQL Compose additive import completed: 11 Research
  products and one import run added. Counts changed from 231 to 242 products, 200 to
  211 Research products, 2 to 3 Research runs; existing 32 offers and 0 historical
  prices were unchanged. No schema or migration changes.
- Imported provenance records ODbL 1.0, Database Contents License (DbCL) v1.0,
  CC BY-SA 4.0 image license when an image exists, retrieval date, barcode, dataset
  source page, and product page. Open Products Facts is experimental; this is not
  evidence of current price, stock, rating, merchant availability, or completeness.
- The API usage form was not submitted. The endpoint was used only for this one bounded
  query. Commercial collector approval remains blocked and Live commerce remains
  `LIVE_NOT_VERIFIED`.

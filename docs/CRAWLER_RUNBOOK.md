# Crawler runbook

## Safety and current status

Live collection is opt-in and the source registry is empty by default. Do not
enable a merchant until its terms, robots policy, and a documented permission
basis have been reviewed for the intended use. A public endpoint alone is not
permission to collect or reuse merchant data.

As of 2026-10-16, no merchant has been approved for this repository and no real
product URL has been fetched. Live status is `LIVE_NOT_VERIFIED`; see
[the source matrix](CRAWLER_SOURCE_MATRIX.md) and
[the evaluation](CRAWLER_EVALUATION.md). Do not use Shopee/Lazada in the generic
collector without the required applicable permission. Stop on robots denial,
401, 403, CAPTCHA, or 429; do not switch to a browser or another access method
to evade a restriction.

## Configure a permitted source

1. Obtain and record the applicable merchant permission and terms review
   externally. Keep sensitive correspondence out of this repository.
2. Review the merchant's `robots.txt` and identify the exact permitted host,
   storefront API or product-page route, rate limits, and data-use restrictions.
3. Back up any existing SQLite database before deployment or schema upgrades.
4. In `backend/.env`, set `DEMO_MODE=false` only when intentionally running the
   existing Live search flow. Leave the source registry empty until the review
   above is complete.
5. After approval, configure `COLLECTOR_SOURCE_REGISTRY_JSON` as a JSON array.
   The following is a **non-functional template**, not an approved merchant:

   ```json
   [
     {
       "source_id": "replace-with-approved-source",
       "domain": "replace-with-approved-host.invalid",
       "kind": "woocommerce_store_api",
       "permission_status": "approved",
       "permission_basis": "Reference to the operator's documented approval",
       "terms_url": "https://replace-with-approved-host.invalid/terms",
       "terms_checked_at": "2026-10-15T00:00:00Z",
       "enabled": true,
       "allowed_paths": ["/wp-json/wc/store/v1/products", "/product", "/robots.txt"],
       "api_path": "/wp-json/wc/store/v1/products",
       "default_currency": "VND",
       "currency_minor_unit": 0,
       "max_pages": 1,
       "max_products": 5
     }
   ]
   ```

   Use `kind: "product_page"` for direct product pages. Do not guess a currency
   or its precision: populate those fields only from verified source evidence.
   `allow_subdomains` defaults to false. IDN/punycode domains are rejected.
   `allowed_paths` is mandatory in practice: list only the product/API prefixes
   and `/robots.txt` that were reviewed; redirects outside them fail closed.
   `COLLECTOR_LIVE_ENABLED` and
   `COLLECTOR_POLICY_CONFIRMED` must both be explicitly enabled for the
   collector service. Keep `COLLECTOR_BROWSER_ENABLED=false` unless the optional
   local renderer has been installed and the approved page genuinely returns a
   JavaScript-only application shell.
6. Restart the backend after configuration changes. Never commit keys,
   correspondence, or private source data.

## Batch-ingest phones, computers, and headphones

After configuring an approved source as described above, run this command from
`backend/`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.ingest_catalog
```

The stricter operator CLI exposes a separate preflight and requires an explicit
Live acknowledgement plus hard caps:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.crawl_products preflight --url "https://APPROVED-HOST/product/example"
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.crawl_products ingest --live --max-products 5 --max-pages 2
```

Both Live policy flags and an approved registry entry are still mandatory;
`--live` does not override either control.

The bounded default queries are `điện thoại smartphone`, `laptop máy tính xách
tay`, `máy tính để bàn desktop`, and `tai nghe headphones`. Override or extend
them with repeatable `--query` arguments; add approved product pages with
repeatable `--url` arguments. The job uses the same source registry, policy
flags, robots/SSRF checks, normalizer, deduplicator, `Product`, `ProductOffer`,
and price-history tables as the recommendation flow. Re-running it is
idempotent for product and offer identities. It exits non-zero and writes no
catalog rows when no approved source produces results.

This is catalog ingestion for the existing deterministic recommendation
pipeline, not model fine-tuning. Product facts, prices, and stock are retained
only from source evidence; an AI model is never trained to invent them.

## Run through the existing search flow

The collector is also wired into the existing on-demand search pipeline:

1. Start the backend and frontend using the normal local instructions in
   [README](../README.md).
2. Create/analyze a requirement to obtain a real `session_id`.
3. Submit the search with one or fewer approved direct product URLs. The search
   request accepts `session_id`, `direct_urls`, and `refresh`; API storefront
   sources are searched from the registered enabled sources when Live search
   runs. `COLLECTOR_MAX_URLS` defaults to 5 and the per-source page/product caps
   are configured in the registration.
4. Inspect the returned status, warnings, source evidence, currency, freshness,
   and stored recommendation snapshot. A successful unit test or fixture is not
   Live evidence.
5. Stop the run and preserve the failure result if access is restricted. Respect
   the returned `Retry-After`; do not immediately retry.

Use a genuine approved URL only after the permission review. The endpoint does
not bypass authentication, policy, robots rules, or network restrictions.

## Local validation and offline benchmark

From `backend/`, run offline tests (no merchant network calls or paid model
calls):

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest
```

Install and reproduce the optional browser runtime smoke (this makes one Live
request to the operator-provided scraping sandbox, not to a merchant):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
$env:CRAWL4_AI_BASE_DIRECTORY=(Resolve-Path '.').Path + '\.runtime'
.\.venv\Scripts\crawl4ai-setup.exe
.\.venv\Scripts\python.exe scripts\smoke_browser.py
```

Expected structured status is `LIVE_SMOKE_OK`. This proves JS rendering and
egress enforcement only; it does not create Product/Offer rows or establish a
permitted merchant source.

The deterministic parser benchmark uses only its checked-in synthetic fixtures:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.run --output ..\crawler-benchmark-output
```

For a manually annotated crawler dataset, the network-free evaluator accepts
`--dataset <json-file>` and writes `report.json`, `records.csv`, and
`summary.md`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 scripts\crawler_benchmark.py --dataset <annotated-dataset.json> --output ..\crawler-benchmark-output
```

The annotated file must contain provenance and ground truth; do not use the
non-functional registry template or fabricated merchant records as a dataset.
The evaluator makes no network calls and redacts URL userinfo, query strings,
and fragments in its CSV output. Both benchmark outputs are offline and must
not be labelled as a Live crawl.
See [benchmark methodology and current results](CRAWLER_EVALUATION.md).

The synthetic, network-free LLM guardrail ablation uses the same two fixtures
with and without quote-verified structured output:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.llm_spec_ablation --output ..\crawler-benchmark-output\llm-spec-ablation.json
```

It uses checked-in simulated model responses, so cost is zero and its results
must not be presented as provider or Live performance.

## Optional Crawl4AI renderer

The normal backend install does not include a browser. To prepare the optional
self-hosted renderer:

```powershell
pip install -r requirements-browser.txt
crawl4ai-setup
crawl4ai-doctor
```

Run the browser only inside a network-isolated host/container that denies
loopback, private/link-local/metadata destinations and off-allowlist navigation;
application-level final-URL validation alone cannot prevent a redirect from
being contacted first. Then set `COLLECTOR_BROWSER_ENABLED=true`. The adapter renders one approved URL,
does not click, submit forms, log in, download files, scroll, use stealth, rotate
proxies, or retry anti-bot failures. It is considered only after a permitted
HTTP response looks like an empty JavaScript application shell; it is never
used after 401/403/429, CAPTCHA, robots denial, or policy denial. Rendered DOM is
fed back into the same deterministic JSON-LD parser.

## Known limitations and recovery

- DNS addresses are checked during preflight, but the current HTTPX transport
  resolves the hostname again when opening the connection; DNS rebinding is not
  pinned/fully prevented. Do not enable an untrusted source until transport-level
  address pinning is implemented and tested.
- Crawl4AI/browser rendering is optional and fixture-tested but has not been
  exercised against a permitted Live JavaScript store. Do not use it to get
  around HTTP 401/403/429, CAPTCHA, or robots restrictions.
- The registry records source-level approval and policy review, not legal advice.
  Recheck it when merchant terms or intended use changes.
- A fetch failure is not an out-of-stock observation. It must not refresh a
  prior successful offer or price timestamp.
- SQLite changes are additive. Back up the database before schema upgrades;
  do not remove the database to repair migration or collector failures.
- LLM fallback is optional and limited to technical specifications with quotes
  verified against fetched text. It must not supply price, SKU, stock, or rating.

# Final product image recovery fix

Branch: `feature/live-search-performance`. Continued from existing WIP; no reset,
undo, restore, clean, commit, merge or tag. No Live API or external page/image fetch
was performed. Production SQLite was opened read-only (`mode=ro`, `query_only`)
only to audit the user-specified session; no schema change, write or backfill.

## A. Root cause and historical evidence

The active flow is search provider -> `ProgressiveRetriever` ->
`ProductImageResolver.inspect(resolve_images=False)` -> `inspect_page` -> image
candidate selection -> bounded HTTP image probes -> raw offer proof -> normalized
product/offer -> `CandidateBuilder.offer_observation` -> recommendation snapshot ->
frontend `ProductImage`.

The recommendation uses its chosen offer's `page_validation.image_url`, not another
merchant's current catalog image. A null image in the offer proof remains null in
the snapshot and reaches the frontend placeholder. This is correct behavior.

Session `de9c2e2a-8c7f-40b0-ab62-ba7e045c0acd` actually persisted **all three** images
as null at the time audited:

| Product | Merchant | Price VND | Verification | Image |
|---|---|---:|---|---|
| OPPO Reno14 5G 12GB 256GB | CELLPHONES | 15,500,000 | VERIFIED_CONTENT | null |
| POCO X8 Pro Max 12GB 256GB | CELLPHONES | 13,990,000 | VERIFIED_CONTENT | null |
| Samsung Galaxy S25 Ultra 12GB 256GB | CELLPHONES | 25,990,000 | VERIFIED_CONTENT | null |

Historical HTML and per-image probe/rejection outcomes were not persisted. The
archived data therefore cannot establish whether each missing image was rejected
during extraction or failed an HTTP probe. No unsupported claim about the precise
Live failure is made. The compact read-only export is
`backend/tests/fixtures/image_snapshot_de9c2e2a.json`.

Reproducible implementation defects found and fixed offline:

- The active selector read only `data-src` or `src`; it omitted `data-original`,
  `data-lazy-src`, `srcset` and other explicit lazy attributes. Older helpers in
  `product_image_resolver.py` were not the active selection path.
- `ImageObject.url or contentUrl` suppressed a valid contentUrl when url was a
  nonempty placeholder. Explicit Product-associated media was not considered.
- JSON-escaped slashes/entity-escaped URLs were not consistently normalized.
- An explicit `-600x600` image size suffix was treated as conflicting model digits.
  Only dimension suffixes are now ignored; arbitrary numbers remain meaningful.
- Deduplication used `(URL, source)` rather than URL, allowing repeated metadata
  entries to occupy the bounded candidate list.
- ImageObject name/caption and social image alt metadata could contradict the
  product without rejection. Transparent pixels and explicit wrong-model image
  redirects also passed the previous image probe checks.

## B. Image source priority

1. `Product.image` from the main Product selected by the existing page validator:
   string, array, ImageObject `url` and `contentUrl`.
2. `Product.associatedMedia` ImageObjects and identity-labelled `itemprop=image`
   img tags on the same page.
3. `og:image:secure_url`, `og:image`, `twitter:image`, `twitter:image:src`, only
   after direct-product validation and rejection of conflicting image alt metadata.
4. Product images with matching alt/title or explicit matching model filename,
   including `data-zoom-image`, `data-original`, `data-src`, `data-lazy-src`,
   `data-image`, `src`, `data-srcset` and `srcset`.

Relative URLs resolve against the actual verified page; protocol-relative URLs
use HTTPS. Escaped URL delimiters/entities are decoded, fragments removed and
duplicates collapsed by normalized URL. URLs are never invented from a model.
There are still at most **five** unique candidates. Failed/broken responses do not
turn a verified product into an invalid offer; absent proof leaves the image null.

## C. Wrong-product and resource safety

- Page identity/price/availability/category acceptance conditions are unchanged.
  Only the image-selection block at the end of `inspect_page` delegates to the new
  image helper. Article, news, review, category and listing gates remain intact.
- JSON-LD images belong to the selected main Product; related Product nodes are
  not mined for images. Gallery position/class alone is insufficient proof.
- Conflicting brand, model/capacity digits, Pro/Max/etc variants, alt/title or
  ImageObject metadata are rejected. Arbitrary numeric filename suffixes are not
  stripped to force a match.
- Data/JavaScript URLs, logos, favicons, banners, placeholders and obvious tracking
  images are rejected. Tiny PNG/GIF header dimensions are checked at probe time.
- Redirects to explicit conflicting model filenames or placeholders are rejected
  before requesting the target. Existing public-address checks, redirect bounds,
  raster MIME/magic checks and maximum download size remain in place.
- HTTP client/stream context managers, existing concurrency limits and timeouts
  remain unchanged. No new network round or lookup provider was added.
- No Google Images, article-image fallback, cross-merchant image borrowing or
  modification of historical recommendations.

## D. Files changed or created in this phase

- `backend/app/services/extraction/product_image_candidates.py` — new image-only
  selector, identity/URL checks and tiny-raster helper.
- `backend/app/services/extraction/product_page_validator.py` — replace only its
  image-selection block with the helper call; product validation gates preserved.
- `backend/app/services/extraction/product_image_resolver.py` — image probe rejects
  explicit conflicting redirects, placeholders and tiny PNG/GIF payloads.
- `backend/tests/unit/test_product_image_recovery.py` — 51 new offline test cases.
- `backend/tests/integration/test_verified_sales_pipeline.py` — retain the original
  JSON-LD scenario and add lazy/srcset parameter cases with all persistence,
  merchant, snapshot/history/detail assertions retained.
- `backend/tests/fixtures/image_snapshot_de9c2e2a.json` — compact historical audit.
- `docs/PRODUCT_IMAGE_RECOVERY_AUDIT.json` — historical versus synthetic results.
- `docs/FINAL_PRODUCT_IMAGE_RECOVERY_REPORT.md` — this report.

No frontend component was edited. The normal Next.js build regenerated its
`next-env.d.ts` declaration; it is no longer different from the tracked production
declaration. No API routes, response schemas, database schema, scoring weights,
budget semantics, retrieval orchestration, dependency or cache version changes.
Existing WIP from earlier phases remains separate from these changes.

## E. Fixture before/after

| Offline check | Before | After |
|---|---|---|
| Initial 46 pattern cases | 28 passed, 18 failed | 46 passed |
| Additional pixel/redirect/metadata safety cases | 5 failed | 5 passed |
| Synthetic same-product lazy markup for the three archived identities | 0 safe candidates | 3 safe candidates |
| Historical recommendations backfilled | 0 | 0 |

The synthetic markup deliberately uses matching product alt plus placeholder src
and `data-original`. It exercises the missing pattern, **not a reconstruction of
unrecorded retailer HTML**. Its synthetic URLs are test data, not claimed real
Live image discoveries. HTTP success/failure checks use mocks; historical snapshot
images remain null. See `PRODUCT_IMAGE_RECOVERY_AUDIT.json` for the distinction.

## F-L. Fresh validation

| Check | Result |
|---|---|
| Existing image/page/persistence baseline before implementation | 57 passed, 0 failed, 2 warnings; 2.07s |
| Final targeted image/page/persistence suite | 110 passed, 0 failed, 2 warnings; 5.99s |
| Full backend `python -B -X utf8 -m pytest` | 745 collected, 745 passed, 0 failed, 0 errors, 2 warnings; 62.50s |
| Frontend `npm test` | 41 passed, 0 failed, 0 skipped; 831.8173ms |
| `npm run lint` | PASS; exit 0, 0 errors, 0 warnings |
| `npm run build` | PASS; exit 0; TypeScript and all routes built |
| `npm run test:e2e` | 15 passed, 0 failed; 39.6s; one worker, zero retries |
| `git diff --check` | PASS; exit 0 |
| Remaining E2E listeners on 13000/18000 | 0 |

Backend warnings are the existing Starlette/httpx deprecation and Windows
permission denied writing pytest cache. Frontend tests emit the existing
MODULE_TYPELESS_PACKAGE_JSON warning; E2E emits NO_COLOR/FORCE_COLOR warnings.
No unclosed client/session warning was observed.

Backend tests create disposable SQLite schemas. E2E uses Demo/local servers and
its own temporary database, with external provider access disabled. Regression
includes direct-product validation, stock, scoring, budget modes, retrieval,
explanation concurrency/timeout/order, session failures and snapshot compatibility.
Existing browser tests confirm valid images render and null/broken images use the
unchanged placeholder. No test was deleted or weakened.

## M. Remaining limitations

- The exact cause of each null image in the specified Live session cannot be
  recovered from the persisted data. Real post-fix image recovery remains unmeasured
  because this phase intentionally performs no Live requests.
- Opaque images rely on their association with the verified main Product/page;
  there is no visual model classifier. Ambiguous gallery images remain null.
- JavaScript-only galleries, arbitrary hydration payloads and unknown structured
  media shapes are not scraped. Existing dealer-variant parsing is unchanged.
- CDN blocking, expiring URLs, hotlink restrictions, transport failures and shared
  retrieval deadline exhaustion can still leave a product without an image.
- PNG/GIF tiny-header checks are bounded checks, not a complete image decoder or
  proof that every raster format is free of tracking pixels.
- Historical snapshots and existing cache entries keep their recorded data; this
  change applies to newly inspected pages without backfill or gratuitous cache bump.

Offline image recovery and safety regressions pass. This is not a new Live
acceptance claim. No commit and no Live API call.

FINAL PRODUCT IMAGE RECOVERY FIX = PASS

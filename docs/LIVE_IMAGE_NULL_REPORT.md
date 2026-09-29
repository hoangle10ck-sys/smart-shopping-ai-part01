# Live image null fix — final offline validation

Validation date: 2026-09-29. Branch: `feature/live-search-performance`.

## Release acceptance update — supplied by the project owner

The subsequent pre-commit request reports **LIVE IMAGE ACCEPTANCE = PASS** for session `07c26761-a327-4c70-ac58-c0db2fa2dc05`, query “Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu”: three candidates, three eligible offers, three recommendations in approximately 28.2 seconds, with 3/3 real images, `image_source=json_ld_product`, direct sales URLs and `VERIFIED_CONTENT`.

Reported products/merchants: OPPO Reno12 5G 12GB 256GB at CellphoneS; Xiaomi Redmi Note 14 Pro Plus 5G 8GB 256GB at CellphoneS; Xiaomi Redmi Note 14 Pro+ 5G 8GB/256GB at Hoàng Hà. The supplied image URL examples are abbreviated, so this report does not invent their full asset paths.

This acceptance is owner-provided evidence, not a Live run performed during the pre-commit audit. It supersedes the release-level “not demonstrated” limitation below for the new session. The dated offline results and historical `8a713af2` root-cause uncertainty remain unchanged; new-session success does not reconstruct the missing old HTML/HAR.

## Original offline validation record

Continued the existing WIP. No reset, restore, clean, commit, merge, tag, Live API call, production database write, or historical snapshot backfill. Frontend source was not changed.

## A. Root causes: established offline versus historical Live

The current WIP initially failed **18 tests** because `ProductImageResolver._image_loads()` imported `raster_prefix`, but that helper was missing from `product_image_candidates.py`. This is an exact, reproducible source defect: the import fails before the image HTTP probe. The retrieval exception handler can leave an otherwise valid offer with a null image. The only application-source edit in this continuation was adding this missing helper after the failing full-suite run. Existing image tests then passed, followed by the full suite.

Other reproducible cases addressed by the existing image WIP:

- Image parsing previously lost `picture/source` siblings and explicit Product gallery ownership. Opaque image URLs without matching alt text could therefore be missed despite explicit same-product ownership.
- The previous probe required HTTP 200, rejecting valid partial-content HTTP 206 responses.
- MIME matching was case-sensitive. Valid values such as `IMAGE/WEBP; charset=binary` could be rejected.
- The previous AVIF signature check missed a compatible `avif` brand behind a `mif1` major brand.
- Reading the full image and rejecting bodies larger than 5 MB was unnecessary for a prefix probe. The current path consumes a bounded prefix and closes the response.

These are **offline causes**, not proof of which condition occurred in the historical Live session. Opaque JSON-LD/OG URLs already worked in the earlier selector; accepting those URLs is not presented as a newly discovered fix. The probe already used GET, so HEAD failure is not claimed as the historical cause.

Historical session `8a713af2-4217-4c00-aeaa-ca6dbd18bf48` contains:

| Recommendation | Merchant | Price (VND) | Historical image URL/source |
| --- | --- | ---: | --- |
| OPPO Reno14 5G 12GB 256GB | CELLPHONES | 15,500,000 | null / null |
| POCO X8 Pro Max 12GB 256GB | CELLPHONES | 13,990,000 | null / null |
| Samsung Galaxy S25 Ultra 12GB 256GB | CELLPHONES | 25,990,000 | null / null |

All three persisted recommendations are `product_page_valid=true`, `VERIFIED_CONTENT`, confidence 95. Their direct product URLs and archived retrieval counts are in [LIVE_IMAGE_NULL_AUDIT.json](LIVE_IMAGE_NULL_AUDIT.json). That execution recorded 5 provider calls, 3 rounds, 13 page attempts, 3 eligible offers and 18,199.245 ms. These are historical values, not a new benchmark or Live run.

No original HTML/HAR, candidate-image list, or per-image probe outcome is available for that execution. Stored text is not the original page HTML. It cannot establish whether JSON-LD/social images existed, whether scripts were double encoded, whether the gallery required hydration, or whether a CDN rejected a request. The missing helper found in today's WIP also cannot be attributed to that historical execution without evidence of its deployed source version.

## B. Candidate extraction

Priority remains selected Product JSON-LD image, same-product structured media, verified-page OG/Twitter image, then product-bound HTML images. Supported HTML attributes include lazy image attributes, `srcset`, `data-srcset`, and associated `picture/source` sets.

Relative URLs, protocol-relative URLs, escaped delimiters, resize query strings and opaque filenames are handled without constructing image URLs from model names. Candidates are deduplicated and capped at five per page.

The implementation is generic. It does not branch on CellphoneS merchant/domain. Product identity, page ownership and response validity determine acceptance.

## C. Probe and resource behavior

- Uses GET with `Range: bytes=0-4095`; no HEAD request is required.
- Accepts HTTP 200 or HTTP 206 with a Content-Range starting at byte zero.
- Normalizes MIME case and parameters; verifies a JPEG/PNG/GIF/WebP/AVIF prefix. The helper also rejects detected 1-pixel PNG/GIF images.
- Consumes at most 4,096 decoded prefix bytes, including when the server ignores Range. This bounds consumed prefix data, not every byte potentially buffered by the transport.
- Retains existing timeout/deadline limits, four-attempt redirect limit, public-URL checks and shared-client lifecycle. Tests confirm the image stream and owned client close without consuming the large response tail.
- Rejects unrelated or unproven redirect identities. HTTP 403 leaves the image null; it does not remove an otherwise valid recommendation.

This is a raster-prefix check, not a complete image decoder or visual model-identification system.

## D. Same-page identity and diagnostics

An explicit matching Product URL/name/SKU owner can bind an opaque gallery image. A CSS class named `product-gallery` alone is insufficient. Cross-product scopes, related-product carousels, explicit conflicting model labels, logos, banners, placeholders and unsafe URLs remain rejected.

New extraction diagnostics contain candidate/accepted counts, presence of JSON-LD/social images, HTML image count and bounded rejection reasons. Probe diagnostics contain the attempted URL, HTTP status, normalized MIME, consumed byte count, acceptance and terminal reason; response bodies are not logged. The current extraction diagnostics do not include a full accepted-URL array or every silently skipped metadata value.

`image_probes` is included in the execution performance diagnostics persisted with the session snapshot. A separate offline API smoke check verified that both HTTP 200 and HTTP 403 cases retain three recommendations and that GET returns identical recommendation data and image probe diagnostics. It used a temporary database, mocked provider/pages/HTTP and a socket guard allowing only local connections. These two checks are additional smoke cases, not extra collected pytest tests. The first smoke launcher blocked Windows' internal socketpair; allowing loopback corrected the validation harness without changing application source.

Diagnostics apply to future executions. Old snapshots are not enriched with current product/image data. Raw historical HTML is still unavailable.

## E. Fixtures and before/after

`cellphones_image_pages.py` covers OPPO Reno14, POCO X8 Pro Max and Samsung Galaxy S25 Ultra with JSON-LD, OG, explicit product gallery and picture/source patterns. Names/prices come from the archived session; the CDN URL envelope was present in archived data. DOM structure and opaque asset names are **synthetic**, not captured CellphoneS HTML, and are not claimed as real recovered images.

The recorded earlier selector baseline found candidates in 6 of 12 pattern cases. Current offline replay finds candidates in all 12. JSON-LD and OG were already supported; gallery/picture ownership accounts for the difference. The JSON audit's current replay fields were regenerated against this continuation's actual source, replacing stale diagnostic shapes from an earlier WIP.

The 26 CellphoneS-pattern unit cases cover the twelve positive combinations, unrelated galleries, explicit wrong models, bounded GET/206/MIME/AVIF, redirects and failure diagnostics. Broader generic fixtures remain in `test_product_image_recovery.py` and `test_product_page_validator.py`.

## F–K. Fresh validation results

Commands ran from backend/frontend respectively, using `backend/.venv/Scripts/python.exe` and Windows `npm.cmd`.

| Validation | Result |
| --- | --- |
| Initial full backend before missing-helper repair | 771 collected; 753 passed; 18 failed; 0 errors; 3 warnings; 64.23 s |
| Targeted image tests after repair | 136 passed; 0 failed; 2 warnings; 5.66 s |
| Final `python -B -X utf8 -m pytest` | **771 collected; 771 passed; 0 failed; 0 errors; 2 warnings; 58.66 s** |
| `npm test` | **41 passed; 0 failed; 0 skipped** |
| `npm run lint` | **PASS**, exit 0; 0 errors / 0 warnings |
| `npm run build` | **PASS**, exit 0; Next.js build, TypeScript and route generation completed |
| `npm run test:e2e` | **15 passed**, exit 0; runner reported 4.9 min |

Targeted command selected `test_cellphones_image_recovery.py`, `test_product_image_recovery.py`, `test_product_page_validator.py` and `test_verified_sales_pipeline.py`.

Final backend warnings: existing Starlette/httpx TestClient deprecation and pytest cache write permission (`WinError 5` for nodeids). The initial failed run also warned about its lastfailed cache. No tests were deleted or weakened. Backend tests use the isolated temporary database fixture, not `smart_shopping.db`. Frontend test output also contained Node's existing `MODULE_TYPELESS_PACKAGE_JSON` notices.

E2E ran successfully through the normal frontend shell command. All fifteen assertions passed, but teardown retained the two test server processes. Stopping the identified test listeners on 13000/18000 let Playwright finish with exit 0. A subsequent listener/process check found neither test listener nor a remaining Node/Python test process. The launcher was not edited. This teardown limitation remains; the 4.9 min includes that delay.

## L. Git and change scope

Branch remains `feature/live-search-performance`. Final `git diff --check` passes; Git's LF-to-CRLF notices are conversion notices, not whitespace errors. No files were staged or committed.

Files written during this continuation:

1. `backend/app/services/extraction/product_image_candidates.py`: missing `raster_prefix` helper, only after actual test failures.
2. `docs/LIVE_IMAGE_NULL_AUDIT.json`: refreshed offline replay/current validation facts.
3. `docs/LIVE_IMAGE_NULL_REPORT.md`: this report.

The resolver, validator, fixtures and tests already in WIP were reviewed and validated, not reimplemented. Other existing changes in Git belong to earlier phases and were preserved. This continuation did not change scoring weights, retrieval, budget semantics, product validation gates, API routes, frontend UI, dependencies, database schema or production data.

## M. Remaining limitations and verdict

- Historical Live root cause remains undetermined without the corresponding HTML/HAR/probe logs.
- Synthetic fixtures prove supported structures; they do not prove the current merchant's real DOM or successful recovery of those three Live images.
- A different opaque asset hash after redirect remains unproven and rejected; JavaScript-only image hydration is not added.
- Future diagnostics improve extraction/probe visibility but are not a complete HTML archive.
- E2E assertions pass; automatic server teardown required manual process cleanup in this environment.

Offline implementation and regression validation: PASS. Historical Live image recovery: not demonstrated; no new Live requests were authorized or made.

**LIVE IMAGE NULL FIX = PARTIAL**

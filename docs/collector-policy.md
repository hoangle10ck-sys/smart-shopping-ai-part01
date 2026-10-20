# Marketplace collector policy

The collector is limited to user-supplied or discovery-supplied public product URLs on
`shopee.vn` and `lazada.vn`. It does not call undocumented marketplace APIs, authenticate,
solve CAPTCHA, rotate proxies/fingerprints, or bypass WAF/rate limits. HTTP 401/403/429 and
human-verification pages produce `ACCESS_RESTRICTED`; they are never interpreted as an
empty catalog.

Before enabling Live collection, the operator must review the current robots directives,
terms, and any contractual/API access applicable to each marketplace and deployment. The
repository does not claim that a public page grants automated collection permission.
Live collection is opt-in and requires both `COLLECTOR_LIVE_ENABLED=true` and
`COLLECTOR_POLICY_CONFIRMED=true`; offline fixtures are only `FIXTURE_TESTED_ONLY`
evidence.

Review recorded 2026-10-15:

- Shopee's published Vietnam Terms of Service state that automated/manual monitoring,
  collection or copying of Shopee content needs prior written consent (apart from the
  stated basic-search-engine exception):
  https://help.shopee.vn/portal/4/article/206856-%C4%90I%E1%BB%80U%20KHO%E1%BA%A2N%20D%E1%BB%8ACH%20V%E1%BB%A4%20%28Phi%C3%AAn%20b%E1%BA%A3n%20ng%C3%A0y%2024%2F4%2F2026%29
- Lazada's Vietnam Terms of Use and Content Services Terms restrict unauthorized
  automated systems and systems that may overload the platform:
  https://www.lazada.vn/terms-of-use/

No written marketplace permission is present in this repository. Therefore the shipped
Live status for both marketplaces is `ACCESS_RESTRICTED`; the adapters and fixtures remain
available, but operators must not flip the confirmation flag without applicable authority.

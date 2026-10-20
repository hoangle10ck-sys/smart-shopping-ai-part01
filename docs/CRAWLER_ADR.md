# ADR: source acquisition order for product ingestion

- **Status:** Accepted for the crawler track.
- **Date:** 2026-10-15.
- **Decision:** Prefer a merchant-approved public storefront API, then a permitted
  product page fetched with bounded HTTPX and deterministic JSON-LD/HTML
  extraction. Use an optional self-hosted browser renderer only when an approved
  page genuinely needs JavaScript. Invoke optional structured LLM extraction
  last, for technical specifications only; deterministic source evidence remains
  authoritative for product identity, price, currency, SKU, stock, and rating.
  Tavily may discover candidate URLs but is not price evidence.
- **Rationale:** Structured APIs provide clearer fields and currency precision;
  deterministic page parsing retains field-level provenance and avoids invented
  values. Browser and LLM layers add operational cost and failure modes, so they
  must not replace a simpler verified source. No marketplace-specific collector
  can establish permission for another merchant or bypass a marketplace policy.
- **Consequence:** The source registry must be empty/fail-closed by default.
  Each merchant requires a documented permission basis and checked policy before
  it can be contacted by an enabled collector. Offline fixtures prove adapter
  behavior only; they do not make the track Live-verified.

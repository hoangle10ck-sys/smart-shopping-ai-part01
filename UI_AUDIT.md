# UI Audit — Smart Product Search & Price Comparison System

**Document Version:** 1.0.0  
**Date:** 2026-10-17  
**Auditor:** Principal Product Designer & Senior Frontend Engineer  
**Repository Architecture:** Next.js 16.4.1 (App Router, Turbopack) + React 19.2.8 + Tailwind CSS v4 + TypeScript 5 + FastAPI Python Backend.

---

## 1. Executive Summary & Repository Baseline

This audit establishes the baseline presentation layer of the **Smart Product Search & Price Comparison System**. The system is a specialized AI-powered product search and price comparison tool, built to analyze natural language user requirements, query search and research catalogs, match observed marketplace offers, calculate multi-criteria suitability scores, and present transparent evidence for buying decisions.

### 1.1 Non-Negotiable Rule: Data Integrity Over UI
- Visual improvements **must never** modify product identity, seller identity, matching algorithms, price calculations, source attributions, external marketplace URLs, search ranking, or comparison logic.
- Missing values (prices, ratings, scores, specifications, stock availability) **must never** be fabricated, coerced to zero, or inferred as positive matches.
- All dynamic bindings and test contracts (unit tests, Playwright E2E suites) must be strictly preserved.

### 1.2 Baseline Verification Status
Prior to introducing any design refactoring, the existing test baseline was executed and verified:
- **Unit & Presentation Tests (`npm test`):** 48 tests passed (0 failed, 0 skipped).
- **ESLint (`npm run lint`):** 0 errors, 0 warnings.
- **Production Build (`npm run build`):** Compiled successfully, all 5 routes statically/dynamically generated without errors.
- **Playwright E2E Tests (`npm run test:e2e`):** 18 tests passed across all viewports (375px, 768px, 1366px, 1920px), search flows, negative feedback, recovery states, and isolation guards.

---

## 2. Route & Screen Inventory

The presentation layer comprises 5 core public routes. There is no mandatory user login, registration, or paywall.

| Route | File Path | Functional Purpose | Key Data Bindings & API Contracts |
|---|---|---|---|
| `/` | `frontend/app/page.tsx` | Home page & Requirement intake | `analyzeRequirement`, `clarifyRequirement`, `executeSearch`, `researchSearch`, `researchStatus`. Form fields: `id="data-mode"`, `id="shopping-query"`, `id="direct-product-url"`, checkboxes for `Shopee` & `Lazada`. |
| `/results/[sessionId]` | `frontend/app/results/[sessionId]/page.tsx` | Session results & recommendations | `getSearchResult(sessionId)`, `executeSearch(refresh=true)`, `createComparison`. Displays `RequirementSummary`, `ResultFilters`, `ProductCard` grid, compare drawer. |
| `/products/[productId]` | `frontend/app/products/[productId]/page.tsx` | Product detail & catalog offers | `getProduct(productId, sessionId)`. Renders hero snapshot (scores, prices, verified badges), `RecommendationDetails`, technical specifications, catalog offers table. |
| `/compare/[comparisonId]` | `frontend/app/compare/[comparisonId]/page.tsx` | Multi-product comparison matrix | `getComparison(comparisonId)`. Shows winner summary, `NOT_COMPARABLE` warning banner, side-by-side cards, horizontal scrolling comparison table, offer breakdown. |
| `/history` | `frontend/app/history/page.tsx` | Historical session lookup | `getHistory()`. Renders 50 recent sessions with timestamps, query text, status tags (`COMPLETED`, `PENDING`, `PROCESSING`, `FAILED`), and links to session results. |

---

## 3. Component & Layout Audit

| Component | File Path | Current Presentation & Issues | Refactoring Opportunities |
|---|---|---|---|
| `SiteHeader` | `components/site-header.tsx` | Minimal header with green badge. Clean but basic. Uses simple borders and plain links. | Elevate to an editorial header with crisp hairline border, refined typography, subtle active pills, accessible skip-link integration. |
| `SiteFooter` | `components/site-footer.tsx` | Text footer with project note. | Clean editorial footer with metadata transparency, system status summary, and structured navigation. |
| `ProductCard` | `components/product-card.tsx` | 3-column grid card. Heavy visual weight, plain placeholder box, long details stack. | Refine card hierarchy: clean image ratio, high-contrast typography, distinct verified status tags, clean price emphasis, and elegant disclosure panels. |
| `ResultFilters` | `components/result-filters.tsx` | 6 inputs/selects in a single grid row. Inputs look blocky. | Professional filter bar with subtle focus rings, clear label hierarchy, integrated active filter tags, responsive collapsing on mobile. |
| `RequirementSummary` | `components/requirement-summary.tsx` | Boxy panel with loose tags and simple definition lists. | Editorial "Demand Brief" presentation: structured cards for budget target/range, purpose, and prioritised constraints. |
| `RecommendationDetails`| `components/recommendation-details.tsx` | Native `<details>` disclosures with default markers and plain table. | Polished custom disclosure styling, refined score weight table, clear provenance cards, verified URL indicators. |
| `RequirementMatches` | `components/requirement-matches.tsx` | Simple cards with colored status text. | Verified criteria cards with micro-status indicators (`matched`, `unmet`, `unknown`), clean typography for requested vs observed values. |
| `ScoreBadge` | `components/score-badge.tsx` | Pale green pill with progress bar. | Precision score meter with clear fraction display (`xx.xx/100`), semantic color tinting, and high contrast. |
| `AvailabilityBadge` | `components/availability-badge.tsx` | Green, red, or neutral grey tag. | Retain exact color logic and strings (`Còn hàng`, `Hết hàng`, `Chưa rõ tồn kho`), polish typography and padding. |
| `ProductImage` | `components/product-image.tsx` | 4:3 image with fallback placeholder. | Retain `safeProductImageUrl` guard; polish placeholder with subtle geometric pattern and clear iconography. |
| `FeedbackPanel` | `components/feedback-panel.tsx` | Interactive thumbs rating with negative reasons dropdown. | Seamless inline feedback widget with tactile button states, refined chip selectors, and smooth confirmation status. |
| `PipelineProgress` | `components/pipeline-progress.tsx` | Animated spinner and skeleton placeholders. | Subtle, high-end pulse skeleton with calm editorial microcopy and progress indicator. |
| `EmptyState` / `ErrorState` | `components/ui-state.tsx` | Centered text with icon and button. | Warm, trustworthy, actionable states with clear paths forward and no dead-ends. |
| `ResearchNotice` | `components/research-notice.tsx` | Yellow notice box for 2023 dataset. | Academic/research provenance badge with clear separation between historical and live purchase data. |

---

## 4. Visual Hierarchy, Color, & Design System Flaws

1. **Color Palette & Contrast**:
   - The current palette relies on `#f6f7f4` (yellowish/greenish off-white background) and `#165b46` (dark forest green) with `#dce4de` borders. While functional, it feels slightly muddy and lacks the razor-sharp crispness of modern editorial design.
   - We will refine the design system tokens to a sophisticated neutral slate/zinc scale (`#fafafa` / `#ffffff` surfaces, `#09090b` / `#18181b` foregrounds, `#e4e4e7` borders) anchored by a restrained, authoritative deep emerald (`#0f766e` / `#047857`) brand accent.
2. **Typography**:
   - Currently uses `font-family: "Segoe UI", Arial, sans-serif;`.
   - We will upgrade to a high-legibility modern system font stack with tabular figures (`font-variant-numeric: tabular-nums`) for currency and scores, balanced tracking, and calibrated font weights (400, 500, 600, 700).
3. **Information Density & Clutter**:
   - The Home page hero currently houses a complex multi-field form (data mode, query, direct URL, source checkboxes) on the right half, creating an asymmetric and intimidating initial impression.
   - We will unify the Home search input into a prominent, human-crafted search hero: an elegant prompt box with instant example chips, while providing an accessible, collapsible "Tùy chọn nâng cao" (Advanced Sources & Mode) drawer so power users retain 100% control over direct URLs and marketplace toggles without cluttering the first-time visitor experience.
4. **Mobile & Viewport Experience**:
   - The comparison table currently relies on horizontal overflow scrolling. While functional and passing Playwright's `noPageOverflow` test, its touch experience and mobile visual cues can be made much smoother with custom scroll shadows and subtle column sticky headers.

---

## 5. Risk Assessment & Verification Strategy

| Risk Category | Potential Impact | Mitigation & Acceptance Strategy |
|---|---|---|
| **Data Fabrication** | Loss of user trust, misleading price claims | Strictly preserve `formatMoney`, `displayScore`, `safeSalesUrl`. Never invent discounts or "best price" badges. |
| **Breaking E2E Selectors** | Test suite failure, broken user journeys | Retain every existing label, accessible name, role, ID, and button text tested in `shopping.spec.ts` and `ui-review.spec.ts`. |
| **Horizontal Page Overflow** | Broken mobile layout, failed responsive audits | Strict CSS container guards, `overflow-x: hidden` on viewport roots, isolated horizontal scroll on tables. |
| **Keyboard Accessibility** | WCAG failure, impaired navigation | Maintain visible `:focus-visible` outlines, skip links, semantic landmarks, and full keyboard submit workflows (`Ctrl+Enter`, `Enter`). |

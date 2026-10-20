# UI Tasks — Implementation Plan & Progress Tracking

**Project:** Smart Product Search & Price Comparison System  
**Visual Direction:** Premium Minimalist Price Comparison Platform  
**Status Legend:** `[ ] Pending`, `[>] In Progress`, `[x] Completed`

---

## Phase A: Audit & Baseline Verification
- [x] **Task A.1:** Audit existing routes, layouts, components, data bindings, and styles.
- [x] **Task A.2:** Run baseline unit tests (`npm test` -> 48 passed).
- [x] **Task A.3:** Run baseline linting (`npm run lint` -> 0 errors, 0 warnings).
- [x] **Task A.4:** Run baseline production build (`npm run build` -> 5 routes generated).
- [x] **Task A.5:** Run baseline Playwright E2E tests (`npm run test:e2e` -> 18 passed).
- [x] **Task A.6:** Create `UI_AUDIT.md` and `UI_TASKS.md`.

## Phase B: Design System Tokens & Base Styles
- [x] **Task B.1:** Refactor `frontend/app/globals.css` with a refined, cohesive color token system (neutral canvas, crisp white surfaces, razor-sharp borders, deep text contrast, and restrained emerald brand accents).
- [x] **Task B.2:** Standardize typography scale, weights, tabular numerals, line heights, and letter spacing.
- [x] **Task B.3:** Polish shared component classes: `.surface`, `.btn`, `.field`, `.tag`, `.money`, `.eyebrow`, `.notice`, `.skeleton`, `.compare-table`.
- [x] **Task B.4:** Verify keyboard focus rings (`:focus-visible`), selection states, and reduced-motion compliance.
- [x] **Task B.5:** Verify build and unit test suite after design token integration.

## Phase C: Header, Footer, and Home Page Experience
- [x] **Task C.1:** Polish `SiteHeader` with crisp hairline border, refined logo icon, and tactile nav links (`Trang chủ`, `Lịch sử`).
- [x] **Task C.2:** Refactor `SiteFooter` with clear system status attribution and editorial typography.
- [x] **Task C.3:** Refactor Home hero (`frontend/app/page.tsx`): create a prominent, human-crafted search centerpiece with integrated prompt textarea, shortcut hints, and responsive actions.
- [x] **Task C.4:** Style prompt suggestion chips (`Điện thoại khoảng 10 triệu...`, `Laptop khoảng 20 triệu...`, `TV khoảng 10 triệu để xem phim`, `Xe máy khoảng 33 triệu...`) with smooth hover and keyboard triggers.
- [x] **Task C.5:** Organize advanced controls (`data-mode`, `direct-product-url`, `Shopee`, `Lazada`) with clean accessible disclosure or grouped layout, preserving exact field IDs and labels.
- [x] **Task C.6:** Polish clarification intake dialog/section, preserving `handleClarificationKeyDown` and exact question/answer workflow.
- [x] **Task C.7:** Polish "Từ ý tưởng đến lựa chọn" 3-step value proposition with editorial iconography and typography.
- [x] **Task C.8:** Verify Home page across viewports (375px to 1920px) and run E2E checks.

## Phase D: Search Results, Filters, and Product Cards
- [x] **Task D.1:** Polish Results header (`frontend/app/results/[sessionId]/page.tsx`): summary stats, data mode indicator (`dataModeLabel`), refresh search action, and data warnings.
- [x] **Task D.2:** Refactor `RequirementSummary` with a structured "Demand Brief" layout for budget target/range, purpose, and prioritised constraints.
- [x] **Task D.3:** Polish `ResultFilters`: sleek filter inputs, dropdowns, min/max price fields, sort selector, and reset action.
- [x] **Task D.4:** Refactor `ProductCard`: clean image presentation (`ProductImage`), verified status tags, clear model/variant specs, honest score display (`ScoreBadge`), and availability indicators.
- [x] **Task D.5:** Refactor `RecommendationDetails`: custom styled disclosures for requirement matches, score breakdown table with exact weights (25/30/20/10/5/10), explanation notes, and structured evidence fields.
- [x] **Task D.6:** Refactor comparison drawer: floating dock for 2-3 selected items with instant "Bỏ chọn" and "So sánh ngay" CTAs.
- [x] **Task D.7:** Polish `FeedbackPanel` with refined tactile thumbs buttons, reason pills, and feedback confirmation.
- [x] **Task D.8:** Verify Results page data contracts and run unit/e2e tests.

## Phase E: Product Detail & Multi-Product Comparison Pages
- [x] **Task E.1:** Polish Product Detail view (`frontend/app/products/[productId]/page.tsx`): editorial two-column hero for recommendation snapshot, exact price formatting, verified store links, and score badge.
- [x] **Task E.2:** Polish Technical Specifications table, Pros & Cons cards, and "Nơi bán trong catalog" offer list with clear merchant separation and source reliability scores.
- [x] **Task E.3:** Polish Comparison view (`frontend/app/compare/[comparisonId]/page.tsx`): AI comparison conclusion banner, `NOT_COMPARABLE` warning alert, side-by-side product cards, and winner badges.
- [x] **Task E.4:** Refactor Comparison Table: clean sticky header, tabular data alignment, keyboard-navigable scroll region, and mobile-friendly column presentation.
- [x] **Task E.5:** Polish Offer/Freshness breakdown and Pros/Cons comparison matrices.

## Phase F: History, Loading, Empty, and Error States
- [x] **Task F.1:** Refactor History view (`frontend/app/history/page.tsx`): clean session cards with formatted timestamps, status pills (`COMPLETED`, `PENDING`, `FAILED`), and clear "Xem lại" actions.
- [x] **Task F.2:** Polish `PipelineProgress`: calm, elegant pulse skeleton and phase indicators without artificial percentages.
- [x] **Task F.3:** Polish `EmptyState` and `ErrorState` in `components/ui-state.tsx` with helpful guidance, retry mechanisms, and zero dead-ends.
- [x] **Task F.4:** Polish `ResearchNotice` to maintain crystal-clear separation between 2023 historical dataset and live marketplace offers.

## Phase G: Responsive, Accessibility, & Interaction QA
- [x] **Task G.1:** Verify all 5 routes at 375px, 768px, 1366px, and 1920px viewports for zero horizontal overflow (`scrollWidth <= window.innerWidth + 1`).
- [x] **Task G.2:** Audit keyboard accessibility: Skip link, tab navigation order, `:focus-visible` rings, dialog escape handling, and keyboard shortcuts (`Ctrl+Enter`, `Enter`).
- [x] **Task G.3:** Audit contrast ratios (text vs background >= 4.5:1, large text/controls >= 3:1).
- [x] **Task G.4:** Audit touch targets (minimum 44x44px for primary interactive elements).

## Phase H: Regression Checks & Final Report
- [x] **Task H.1:** Run full test suite: `npm test` (all 48 unit tests).
- [x] **Task H.2:** Run linter: `npm run lint`.
- [x] **Task H.3:** Run production build: `npm run build`.
- [x] **Task H.4:** Run full Playwright E2E suite: `npm run test:e2e` (all 18 tests).
- [x] **Task H.5:** Produce final `UI_QA_REPORT.md` documenting audited routes, major UI decisions, changed files, verification results, and acceptance confirmation.

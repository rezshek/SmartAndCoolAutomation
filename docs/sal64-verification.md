# SAL-64 verification - 2026-11-13

Measured local evidence in America/New_York. Supplier payloads, real identifiers,
category IDs/mappings, business assumptions and screenshots remain in PostgreSQL or
ignored `local-data/sal64/`. This document contains aggregate evidence only.

## Catalog and database

- Refreshed `origin/main` and created `rezshek/sal-64-product-management` from `962671d`.
- Existing PostgreSQL volume preserved: **50 unique products and 193 unique variants**.
  API traversal checked every variant's parent; browser traversal checked all five
  catalog pages and counted 50 distinct cards, without duplicated channel scenarios.
- All 50 products have source image references. Visible catalog/detail images rendered
  in the browser; additional images and variant inventory are accessible in the workspace.
- Eligibility remains **39 require review, 11 excluded, 0 passed**. No business/compliance
  approval was inferred from imported facts or a successful software test.
- Additive migration `c64a10000001` applied to development; Alembic drift check passed.
  Fresh upgrade, drift, downgrade and re-upgrade passed on the separate disposable test
  database. The imported development database was never downgraded or reset.

## Pricing, categories and content

- Browser checked Woo US, Amazon US and Amazon Canada pricing views on one real product.
  Missing assumptions showed unknown prices/profit/margin. Preview and an explicit
  saved-for-review decision worked; **no real price was approved**.
- Synthetic PostgreSQL integration verifies the unchanged SAL-63 example: $3 supplier +
  $7 freight produces a $19.99 required price and $5 contribution under the fixture's
  fee assumptions. This is not real CJ profitability. Tests cover exact-quote selection,
  fresh-quote invalidation, separate variant decisions, missing FX and exclusions.
- One bounded live Woo category retrieval succeeded: **16 actual categories**, GET-only,
  cached locally. Browser displayed the 16 IDs plus an unmapped option. No store category
  was created or modified; **no real category mapping was approved**. Mocked tests exercise
  mapping approval, stale/different-store rejection, missing-category proposals and cap
  failure retaining the previous cache.
- Amazon product-type/attribute/identifier preparation remains provisional. No SP-API,
  Seller Central scraping, ASIN eligibility or account-specific schema validation occurred.
- **No OpenAI API key is configured.** Five-product live-AI validation is blocked. No
  OpenAI request or live generation cost is claimed. Two mock generations and one manual
  edit on one selected real product produced three retained Woo draft versions, with
  original/previous-version comparison. Only the observed supplier title was verified
  for that smoke test; no safety, material, certification or image-rights claim was made.
- Mock generations made zero provider requests and used zero tokens/$0. Model access,
  copy quality and live token charges require a configured dedicated key. Sourced token
  rates are absent, so future live cost estimates remain unknown until configured.
- Real content remains unapproved. Synthetic tests demonstrate valid Woo content
  approval while pricing stays unpriceable and publishing disabled. Tests also reject
  missing fact/image review, direct mock approval, stale versions/facts and provisional
  Amazon categories. No live listings, products, orders or payments were changed.

## Automated checks

| Check | Local result |
| --- | --- |
| Full Pytest with PostgreSQL | **159 passed**, no skips; all 117 pre-existing tests retained |
| New dashboard cases | 42, including parametrized cases |
| Ruff lint and format | Passed |
| Alembic development upgrade/drift | Passed |
| Disposable PostgreSQL migration round trip | Passed |
| Frontend ESLint / TypeScript | Passed |
| Frontend Node security tests | **2 passed** |
| Next.js production build | Passed, Next.js 16.4.6 / Node 24 |
| Source + wheel build | Passed, offline local cache |
| Package/private-file and configured-secret scans | Passed, zero private paths/vendor-secret matches |

One pre-existing Starlette/httpx TestClient deprecation warning remains. No dependency
change was needed for that warning. Backend and frontend CI jobs are included; hosted
results are reported on the PR rather than inferred from local checks.

## Browser evidence

Playwright exercised the actual local production frontend → fixed local proxy → FastAPI
→ PostgreSQL flow, using the imported catalog. Desktop 1440×1000 and mobile 390×844 were
checked; both catalog and product workspace had no horizontal page overflow. Search,
empty/reset state, pagination, grouped variants, three channel views, cached category
selection, preview/save, fact verification, mock generation, edit/save/regeneration,
version comparison and disabled approval controls were checked. Final console check
reported **0 errors and 0 warnings**.

Two observed failures were fixed and retested: clicking an already-selected channel
could leave the dialog loading; NextURL's loopback-name normalization could reject
legitimate POST/PUT requests. The latter now has a native Node security regression test
covering accepted local origins and rejected public/cross-site requests.

Private evidence files (not committed):

```text
local-data/sal64/catalog-desktop.png
local-data/sal64/catalog-mobile.png
local-data/sal64/product-mobile.png
local-data/sal64/pricing-desktop.png
local-data/sal64/category-desktop.png
local-data/sal64/aggregate-verification.json
```

## Outstanding gates before SAL-65

Real fees/credits, returns/landed costs, Canadian FX/Individual fee, competitive ceilings,
exact freight tracking/zero-price evidence, safety/IP/documentation, category decisions
and image rights remain business inputs. Source observations can expire; no fresh CJ
reads were triggered by this dashboard task. AI remains conservative extractive content
preparation and needs selected-product live validation after key setup.

SAL-65 still needs an explicitly approved safe-product write test for Rank Math
persistence/rendering, CJ linkage and field ownership, plus publication idempotency,
variant selection and reconciliation. Amazon automation additionally needs Professional
access, developer authorization and account/marketplace-specific listing validation.
No deployment, merge, fulfillment or accounting work was performed.

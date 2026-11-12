# SAL-63 verification - 2026-11-12

This is aggregate evidence for the implementation PR. Live supplier payloads, external
IDs, warehouse mappings, credentials, private assumptions and row-level reports stay
in local PostgreSQL or ignored `local-data/sal63/`.

## Real CJ/local PostgreSQL observations

- Imported **50 distinct products and 193 variants**. Three discovery runs completed:
  20 organizer candidates, 20 kitchen-organizer candidates (three overlapping products),
  then 13 pet-brush candidates to reach 50 distinct products.
- All 50 have image references; all 193 variants have prices and observed inventory
  timestamps. These observations do not establish stock availability or compliance.
- Screening: **0 passed, 11 excluded, 39 require review**. Missing safety/IP/document
  evidence was never converted into compliance. No product is approved for publication.
- Initial import/quotes used 69 HTTP attempts/800 estimated points. A continuation using
  the observed US origins consumed 7 attempts/60 points, for **76 attempts/860 points**
  total against the original cap of 80 attempts/1,000 points. Auth calls count toward
  the request cap; no retry or quota rescue was needed.
- First read window: November 12, 3:25-3:27 PM America/New_York. Continuation occurred
  during the same implementation session. Environment live gates were enabled only
  for those processes; private `.env` remains disabled. No images were downloaded.

Each quote below is one unit of one variant, not nationwide or multi-product pricing.
The US-warehouse calls supplied an actual stock ID; its private mapping is retained.
The CN calls did not specify a subwarehouse ID.

| Sample | Origin | Destination | Returned methods | USD cost range | Evidence limit |
| --- | --- | --- | ---: | --- | --- |
| Pet hair brush | CN | US 10001 | 28 | $14.07-$82.98 | Factory stock; tracking not supplied |
| Pet hair brush | CN | US 90001 | 29 | $13.15-$82.98 | Factory stock; tracking not supplied |
| Pet hair brush | CN | CA K1A 0A9 | 16 | $10.99-$39.60 | Factory stock; duties/FX unresolved |
| Book/toy organizer | US warehouse | US 10001 | 36 | $0.00 returned | Zero freight requires verification |
| Book/toy organizer | US warehouse | US 90001 | 36 | $0.00 returned | Zero freight requires verification |
| Book/toy organizer | US warehouse | CA K1A 0A9 | 0 | Unavailable | No methods returned |
| Kitchen organizer | US warehouse | US 10001 | 7 | $0.00 returned | Zero freight requires verification |
| Kitchen organizer | US warehouse | US 90001 | 7 | $0.00 returned | Zero freight requires verification |
| Kitchen organizer | US warehouse | CA K1A 0A9 | 0 | Unavailable | No methods returned |

The first six home/kitchen queries used an explicit CN origin and returned empty
method lists. Inventory inspection identified US-only stock for those variants, so
the continuation used their observed US warehouse. Both sets are retained as distinct
route observations. Zero-priced rows had both `logisticPrice` and `totalPostageFee`
equal to zero; they were not produced by substituting missing data. Tracking was not
explicitly supplied in any returned method. No cheapest method was selected.

## Real samples and pricing disposition

| Real sample | Supplier USD/unit | Freight evidence | Recommended price / margin |
| --- | ---: | --- | --- |
| Book Organizer, Toy Storage Cabinet Organizer, White | $62.00 | US-origin $0 rows; no CA route | UNPRICEABLE / unknown |
| Kitchen Organizer | $31.60 | US-origin $0 rows; no CA route | UNPRICEABLE / unknown |
| Pet hair brush hair brush | $8.13 | CN to US 10001 $14.07-$82.98 | UNPRICEABLE / unknown |

No real selling price or margin is recommended. Required missing inputs: verified
category/referral assumptions, actual Amazon shipping credits (including documented
zero if applicable), Canadian Individual fee/currency, Woo processor schedule, returns
reserve, landed variable costs including duties/taxes, USD/CAD FX with source/date,
commercial price ceilings, service eligibility/tracking evidence and product reviews.
The intentionally incomplete template produces auditable rejection/missing-input
reasons, not apparently profitable recommendations. The hand-checked synthetic $3
supplier/$7 freight example in [the workflow](catalog-pricing.md) produces a $19.99
floor, $5 contribution and 25.0125% margin; it is not a measured CJ opportunity.

Private CLI reports: `local-data/sal63/catalog.json`, `ranked.json`, `ranked.csv`,
`ranked.assumptions.json`; bounded-read summaries are alongside them. Reports include
every retained latest route/method and all active variants for three independent
profiles (Amazon US, Amazon CA, Woo US). They contain no assumed FX or shipping credit.
The final exports contain 884 route/method/profile scenarios: 787 UNPRICEABLE and 97
REJECTED, with no passing scenarios. Scenario counts differ from the 50-product
eligibility counts because one product can have multiple variants, routes and methods.

## Automated and operational validation

All automated commerce calls use MockTransport; the test suite forbids unmocked HTTP.
Real PostgreSQL checks use a separate disposable `smartandcool_test`, never the imported
development database. Coverage includes normalization, reimports/history, removed
variants, missing stock, interrupted/resumed pagination, budget/rate-limit stops,
multiple/empty/stale methods, origin stock, USD/CAD conversions, fee structures,
minimum fees, shipping credits, costs/reserves/ads, threshold rounding, commercial
rejection, exclusions, local-only writes/exports and CSV provenance.

The existing SAL-62 tests are preserved, with only the expected new migration head and
schema assertions updated. Ruff, the full PostgreSQL suite, Alembic upgrade/drift/
downgrade/re-upgrade and package build are required before handoff. Exact final local
and hosted CI outcomes are recorded in the PR checks and delivery report.

Final local results: **107 tests passed** with real PostgreSQL enabled; Ruff lint and
format passed; development upgrade/drift check and disposable downgrade/re-upgrade
passed; locked offline sync and source/wheel builds passed. Package inspection found
no `.env`, private reports, virtual environment or cache entries, and the staged
vendor-credential scan had no matches. Hosted CI is verified separately on the PR.

Known upstream warning: the pinned Starlette/httpx TestClient integration emits the
same future deprecation warning as SAL-62. No dependency update is needed for this task.
No browser/visual QA is claimed: SAL-63 exposes a CLI/service interface and changes no
website, forms or dashboard. No Woo/Amazon writes, SP-API calls, publishing, orders,
payments, fulfillment, accounting, deployment or merge occurred.

# SAL-64 product review workspace

The local Next.js dashboard reads the existing canonical CJ catalog through FastAPI.
Products appear once, with expandable variants and independent Woo US, Amazon US and
Amazon Canada reviews. No publishing, category creation, orders, payments, fulfillment,
accounting, hosting or deployment capabilities are included.

## Local setup

Keep the existing `.env` and PostgreSQL volume. Do not overwrite private settings.
From the repository root:

```powershell
.tools/bin/uv.exe sync --locked
docker compose -p smartandcool-sal62 up -d --wait db
.tools/bin/uv.exe run --locked alembic upgrade head
.tools/bin/uv.exe run --locked uvicorn smartandcool.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal (Node 24 and npm):

```powershell
Set-Location frontend
npm ci --no-audit --no-fund
npm run dev
```

Open `http://127.0.0.1:3000`. For production-build verification locally, use
`npm run build` then `npm run start`. Both frontend scripts bind only to loopback.
The frontend proxies a fixed local API origin; provider keys never reach the browser.
There are no deployment manifests or hosting registrations.

The backend checks the actual client address, Host, Origin and cross-site browser
headers. Only loopback addresses and local frontend/API origins are accepted. An
optional `DASHBOARD_TOKEN` adds a server-to-server bearer check: set the same value in
the root private `.env` and `frontend/.env.local`. This token does not authorize remote
access. Do not publicly expose either service or put them behind a public proxy.
The local reviewer name is an audit label, not a multi-user identity system.

## Browsing and product facts

The catalog searches product titles/CJ IDs and filters categories, variant cost ranges,
inventory observations, origin, eligibility, missing information and saved Woo pricing
readiness. Search/category/cost filtering runs in SQL. Derived screening/evidence filters
run on the server over the small local catalog, before pagination. This intentionally
avoids a search service or extra infrastructure. Reassess query batching for large imports.

Images are original HTTPS references; they are not altered or downloaded by the backend.
The browser loads images directly with no referrer. Unavailable images have a placeholder.
Supplier HTML is displayed as plain text; React escapes supplier attributes. No generated
or supplier HTML is executed. Images and stock observations do not establish commercial
image rights, availability, product safety or channel acceptance.

Variants show separate country/warehouse inventory observations and route-specific
freight evidence, including unavailable/stale/unverified routes. Warehouse totals are
not added to country totals. Missing stock/cost/freight remains unknown. Every pricing
request applies SAL-63's variant-level screening, even after a parent review.

## Pricing review

Choose a channel and active variant, then explicitly select an exact retained freight
quote/method. The form reuses `catalog.report.build_report` and the original Decimal
pricing engine; it does not implement a second financial formula. The small report
extension allows product/variant scoping while preserving CLI behavior.

Enter decimal strings; blanks remain unknown. Defaults remain 25% contribution margin
and $5 USD-equivalent profit. Fees, shipping credits, returns, landed variable costs,
advertising, commercial ceilings, evidence/verification and dated USD/CAD FX can be
reviewed in the form. Advanced JSON exposes the full existing engine configuration.
Canada retains its own currency, FX and Individual fee; it never inherits US approval.

Recalculate changes only the preview. **Save pricing decision** appends the request,
selected result and decision to the audit trail. Only an exact selected scenario with
overall `PASS` receives an approved pricing decision. Other inputs can be saved for
review without inventing an approved price. Decisions are independent by product,
variant and profile. Readiness recalculates current data; changed/stale observations
require a new decision. All active variants need valid saved decisions for product-level
pricing readiness; excluded variants still block channel preparation.

Service verification binds to the exact quote ID, method ID, variant, origin, warehouses,
postal destination and quantity already protected by SAL-63. Selecting a method does not
verify it. Zero-dollar freight needs its own exact-quote evidence; a new quote never
inherits approval from another quote. No live freight reads are triggered by browsing.

## Category mappings

Set `LIVE_CHECKS_ENABLED=true` only in a server process that should allow the requested
read, then use **Retrieve store categories · read only**. The API also requires
`live=true`. Existing read-only Woo credentials are reused. This makes at most five
GET requests of 100 categories, with no retries; reaching the cap saves no partial
snapshot. Errors retain the previous cache. Switch the live setting off afterward.

Woo suggestions are simple category-name matches, not AI approval. Select an actual
cached Woo category ID, record a source/reason, and approve manually. The cache must
belong to the configured store and be under 24 hours old. Store changes, deleted
categories or stale snapshots invalidate mapping readiness. Missing categories are
proposals only; this application cannot create them.

Amazon mappings record a provisional product type, marketplace, existing-ASIN versus
new-catalog path, identifiers/exemption evidence, brand-review references and manually
sourced required attributes. No SP-API or Seller Central requests are made. Exact-ASIN
matching, GTIN exemptions, brand restrictions and required-attribute completeness remain
unverified without account-specific validation. Provisional Amazon mappings cannot be
approved, and block Amazon content approval. A missing Amazon mapping does not block Woo.

## AI configuration and factual grounding

Configure a dedicated project key in the backend private `.env`:

```text
OPENAI_API_KEY=<private dedicated project key>
OPENAI_MODEL=gpt-4.1-mini
AI_LIVE_ENABLED=true
```

Restart the backend. Set project spending limits in the provider account. Optionally
configure `AI_INPUT_USD_PER_MILLION`, `AI_OUTPUT_USD_PER_MILLION` and `AI_PRICE_SOURCE`
using current rates for the configured model. No rates are invented; missing sourced
rates mean estimated cost is unknown. Cached-input discounts are not modeled, so the
estimate uses the configured full input rate. Provider billing remains authoritative.
Use a model supporting strict Responses API JSON Schema output; model access is an
account-specific dependency, not proven by mocked tests.

Without a key/live opt-in, the UI explicitly offers deterministic **mock** generation.
It makes no provider request, reports zero tokens/$0 and cannot be directly approved.
Explicit human edits create a human-reviewed version; final fact/image/category checks
still apply. No automatic bulk-generation loop exists.

Before generating, select and verify exact source facts, including the supplier title,
and record the evidence reviewed. Supplier prose is not automatically true. Source
changes invalidate verification. Reviewers must exclude supplier prompt instructions,
unsupported claims, brands, certifications and safety guarantees.

The first release deliberately uses **extractive generation**: OpenAI selects and orders
verified fact IDs through a strict schema; deterministic composition creates distinct
Woo and Amazon fields. It cannot freely introduce new product claims. The editable
title, description, SEO fields, bullets, alt text and attributes are checked against
verified source phrases. Unknown IDs, extra schema fields, markup, unsupported wording
and stale-version edits are rejected. A limited supplier description therefore yields
limited copy; this is not a general-purpose creative paraphraser or a compliance judge.
Reviewers can shorten/reorder supported copy, but novel factual wording requires source
evidence. SEO titles/slugs and keywords remain suggestions, never ranking guarantees.

Woo drafts contain title, short/detailed descriptions, headings, meta title/description,
keywords, image alt text, slug and source attributes. Amazon drafts contain title,
supported bullets (up to five), description, source attributes and optional search terms.
Fewer than five source-supported bullets are allowed. Amazon search terms start blank
pending product-type permission review. Account/product-type content limits and required
attributes remain provisional; generic field limits are not an Amazon compliance claim.

Each successful generation makes one request, with a 60-second timeout, 1,800 output-token
cap, no provider tools, no retries and `store=false`. Supplier data is clearly marked as
untrusted data in the prompt. A failed/refused/incomplete response saves no draft and
never silently falls back to a mock. Failed requests may still incur provider charges;
successful draft versions retain usage and sourced cost estimates. Review provider
billing for failed-request charges and totals. No image editing or rights inference occurs.

Regeneration and edits append immutable versions. Compare original supplier copy or
any prior version against the current editor. Concurrent writers serialize on the
product row, and edits must name the current base version. Changed verified facts or
supplier observations invalidate previous content approval.

Official implementation references: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
[Woo REST product categories](https://github.com/woocommerce/woocommerce/blob/trunk/docs/apis/rest-api/v3/product-categories.mdx),
[Amazon product detail rules](https://sellercentral.amazon.com/help/hub/reference/external/201911450).
Account-specific Amazon guidance may require Seller Central login and remains unverified.

## Workflow and audit

`IMPORTED → REVIEW_REQUIRED → DRAFT_READY → CONTENT_APPROVED`

Generation starts review and saves a draft-ready version. Editing/regeneration always
creates a new draft-ready version and invalidates prior approval. Review can be reopened.
Content approval requires the current version, current verified facts, explicit fact and
image-rights review, and a reviewed channel category (an approved current ID for Woo).
Amazon's provisional category/schema blockers prevent its content approval.

Eligibility, category, shipping, pricing, content and publishing indicators remain
separate. Approved content may still be commercially unpriceable or ineligible. The
publishing indicator always says **disabled**: there is no publisher in SAL-64 and no
endpoint that can turn publishing on. SAL-65 must implement and independently validate
all commerce checks before exposing any write action.

Migration `c64a10000001` adds three tables only:

| Table | Purpose |
| --- | --- |
| `review_events` | Append-only fact/category/pricing/workflow decisions with reviewer/source/time |
| `listing_versions` | Unique product/profile/version; immutable content, fact snapshot/digest and AI usage |
| `woo_category_cache` | Actual Woo IDs, names/parents, store and retrieval time |

Canonical products, variants, inventories and freight are reused. No raw external payloads,
business assumptions, category mappings or screenshots are committed. The schema upgrade
is additive. Downgrade is tested only on a disposable `*_test` database.

## API

All endpoints are under `/api` and have the local-access guard. `/health` and `/ready`
remain unchanged. FastAPI `/docs` exposes typed request/response contracts.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/settings` | Capability flags only; no credentials |
| GET | `/products` | Search/filter/page unique products |
| GET | `/products/{pid}` | Product, grouped variants, inventory/freight, source-fact candidates |
| PUT | `/products/{pid}/facts` | Verify selected exact source facts with a reference |
| GET | `/products/{pid}/{profile}/pricing?variant_id=...` | Current variant/channel assumptions and scenarios |
| POST | `/products/{pid}/{profile}/pricing/preview` | Non-persistent Decimal recalculation |
| PUT | `/products/{pid}/{profile}/pricing` | Append explicit pricing decision |
| GET | `/products/{pid}/{profile}/review` | Indicators, blockers, versions and audit history |
| PUT | `/products/{pid}/{profile}/category` | Save/approve channel category review locally |
| POST | `/products/{pid}/{profile}/generate` | One selected product/channel; explicit live or mock request |
| PUT | `/products/{pid}/{profile}/draft` | Validate edits and append a version |
| POST | `/products/{pid}/{profile}/transition` | Explicit workflow decision |
| GET | `/categories/woo` | Read current configured-store cache |
| POST | `/categories/woo/refresh?live=true` | Bounded GET-only store read; local cache update |

Profiles: `woo_us`, `amazon_us`, `amazon_ca`. Invalid inputs return sanitized 422s;
unknown products 404; unauthorized/local-origin failures 401/403; database failures
sanitized 503. Provider bodies and validation input values are not echoed.

## Checks and SAL-65 handoff

Run the README backend suite with `TEST_DATABASE_URL` pointing to the disposable database.
Run `npm run lint`, `npm run typecheck` and `npm run build` in `frontend`. CI runs both stacks.
Browser evidence and measured limitations are recorded in [SAL-64 verification](sal64-verification.md).

Before SAL-65: obtain real fee/credit/returns/landed-cost/FX/commercial-cap evidence; review
product safety/IP and exact freight; approve actual category IDs and image rights; validate
the dedicated AI key/model on selected products; refine copy within verified facts; verify
Rank Math persistence/rendering, CJ field ownership, variation linkage and idempotency
through a separately approved safe-product write test. Amazon automation requires a
Professional plan, developer authorization, marketplace-specific schema/GTIN/brand and
listing eligibility. No part of this local review workflow authorizes those live writes.

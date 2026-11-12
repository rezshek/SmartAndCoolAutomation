# SAL-62 integration feasibility

Reviewed 2026-11-12 (America/New_York). Scope: foundation and isolated read-only probes. No product publishing, order creation, payment, webhook registration, deployment, or Phase 2 implementation.

## Evidence labels and outcome

- **VERIFIED:** actually tested; the evidence column says whether this was local, mocked, or live.
- **DOCUMENTED:** official documentation or source supports the capability; no live proof.
- **BLOCKED:** credentials, permission, safe test fixture, or external configuration is missing.
- **UNKNOWN:** the actual account/store behavior has not been confirmed.

| Integration | Implemented and VERIFIED locally | Live authentication | Remaining proof |
| --- | --- | --- | --- |
| CJ | Mocked auth/cache/refresh, catalog/detail/variants/stock, separate US and CA quotes | BLOCKED: no workspace credentials | Actual account access, usable catalog/quotes, warehouse selection, store connection |
| WooCommerce | Mocked HTTPS Basic auth, product/variation/category/attribute GETs, metadata presence | BLOCKED: no URL or read key | Actual product and variant linkage, connector field ownership |
| Rank Math | Mocked presence detection for the three requested keys | BLOCKED: Woo credentials and approved safe write product absent | Persistence, editor recognition, rendered tags, no connector overwrite |
| Amazon | Mocked LWA refresh/cache and marketplace participation GET | BLOCKED: no self-authorized app credentials; seller status UNKNOWN | Professional account, app/roles, US and CA participation, product eligibility |

No live commerce API calls were made. Synthetic fixtures demonstrate implementation behavior only. No real catalog samples, tokens, customer data, or proprietary mappings were saved.

## CJ Dropshipping

### Credentials and authentication

**DOCUMENTED:** obtain the API key through My CJ > Authorization > API; POST `/authentication/getAccessToken` with `apiKey`, then send the returned token in `CJ-Access-Token`. Refresh through POST `/authentication/refreshAccessToken`. Current endpoint docs describe 180-day token lifetimes and a 24-hour server token cache. Use returned expiry timestamps rather than assuming those durations. The adapter reuses tokens in memory, refreshes five minutes early, and stops if CJ returns an expiring cached token. It never logs out or writes tokens to disk. A reusable pair and expiries can be provided through the environment for separate CLI invocations. [Authentication](https://developers.cjdropshipping.com/en/api/api2/api/auth.html), [API-key setup](https://developers.cjdropshipping.com/en/api/start/apikey.html).

**BLOCKED:** no CJ key or token pair is configured. Account permission and actual token expiry behavior are UNKNOWN. For a future persistent worker, store rotated pairs in the hosting secret store; do not repeatedly fetch tokens per catalog page.

### Read contracts

API root: `https://developers.cjdropshipping.com/api2.0/v1/`.

| Endpoint | Method | Use |
| --- | --- | --- |
| `product/listV2` | GET | Keyword `keyWord`, `page`, `size`; one small sample by default |
| `product/query?pid=<pid>` | GET | Facts, images and embedded variants |
| `product/variant/query?pid=<pid>` | GET | Variant IDs/SKUs |
| `product/stock/queryByVid?vid=<vid>` | GET | Warehouse inventory for a variant |
| `product/globalWarehouseList` | GET | DOCUMENTED warehouse discovery; not yet wrapped |
| `logistic/freightCalculate` | POST | Read-only quote using origin, destination, postal code, variant/quantity and optional `storageIdList` |

**DOCUMENTED:** search bounds are page 1-1000 and size 1-100. Preserve supplier IDs, image references and variant attributes before later normalization. [Product reference](https://developers.cjdropshipping.com/en/api/api2/api/product.html).

**VERIFIED, mocked:** auth is cached across sequential reads; expired access tokens use refresh; HTTP-200 failure envelopes are rejected. Both US and CA quote payloads use `startCountryCode`, `endCountryCode`, and `zip`. Monetary JSON numbers remain Decimal.

**DOCUMENTED:** this is the simple quote API; CJ recommends its more detailed calculation for greater accuracy. `logisticPrice` is USD even for Canada. A quote is not a delivery guarantee or complete landed cost. **UNKNOWN:** actual services, duties/taxes, tracked delivery, handling times, and suitable origin/warehouse/postal scenarios. Do not substitute a US quote for Canada or infer CAD prices. [Logistics](https://developers.cjdropshipping.com/en/api/api2/api/logistic.html).

### Limits and webhooks

**DOCUMENTED:** free/lowest-tier access is 1 request/second; higher tiers differ, with separate IP limits. The adapter enforces at least 1.1 seconds between attempts within one sequential instance. Run one CJ check at a time; this is not an account-wide distributed limiter. [Frequency restrictions](https://developers.cjdropshipping.cn/en/api/start/limit.html).

**DOCUMENTED:** CJ now uses points rather than the old daily call count: base 50,000/day, search 50 points, details/variants/stock/freight 10 each. Per-minute replenishment can cause throttling before the daily total is consumed. The rules also describe API suspension after 30 days with no transaction amount; store authorization does not prove API permission. Confirm the account's actual allowance and status. Read-only requests still consume quota. [Points and suspension rules](https://developers.cjdropshipping.cn/en/api/api2/standard/points.html).

**DOCUMENTED:** product/stock and other webhook events exist; HTTPS receivers must acknowledge within three seconds. Failed/timed-out deliveries are not resent; sustained failures can disable delivery. Later work needs authentication/signature validation against the then-current contract, deduplication, quick durable receipt, and polling reconciliation. No receiver or subscription is implemented. [Webhook mechanism](https://developers.cjdropshipping.cn/en/api/start/webhook.html).

### Native WooCommerce route and recommendation

**DOCUMENTED:** CJ supports POST `/listed/publishAsync` for WooCommerce, followed by listing-status polling; store ownership/activation and category prerequisites apply. A queued record is not proof of publication or fulfillment linkage. [Listing API](https://developers.cjdropshipping.com/en/api/api2/api/listed.html).

**DOCUMENTED:** CJ's Woo guide says listing does not automatically synchronize Woo inventory. **UNKNOWN:** this store's connector/version/settings, subsequent price overwrites, and authoritative variant mappings. [CJ Woo help](https://cjdropshipping.com/help-center?keyWord=Woocommerce&navType=search&searchType=content).

Recommendation: retain the existing CJ connection and compare one already-linked Woo variable product with CJ's connection view before selecting a publication path. Native publishing could preserve linkage with less code; drawbacks are async failures, platform-specific field restrictions and uncertain price/content ownership. Direct Woo creation offers field control but must establish CJ mappings independently. Neither route is approved or implemented here.

Next: supply credentials privately; check API activation/points; read one sample with details/stock; quote the chosen variant separately to approved non-customer US and CA postal codes. Have the owner show the corresponding CJ connection and per-variation mapping. A future native-publication/linking experiment requires a named safe product and explicit write approval.

## WooCommerce

**DOCUMENTED:** use `/wp-json/wc/v3/`, HTTPS Basic auth with consumer key/secret in the Authorization header. Generate a separate Read-only key at WooCommerce > Settings > Advanced > REST API for a suitably limited user. Keep CJ's existing connector credentials unchanged. Store subdirectories are supported. Do not put secrets in query strings or follow credential-bearing redirects. [Authentication](https://developer.woocommerce.com/docs/apis/rest-api/authentication/), [current v3](https://developer.woocommerce.com/docs/apis/rest-api/v3/).

**DOCUMENTED:** GET `products`, `products/{id}`, `products/{id}/variations`, `products/categories` and `products/attributes` cover discovery. Product fields include categories, attributes and `meta_data`. [Products](https://developer.woocommerce.com/docs/apis/rest-api/v3/products/), [variations](https://developer.woocommerce.com/docs/apis/rest-api/v3/product-variations/).

**VERIFIED, mocked:** only GET operations are issued, Basic auth stays out of URLs, bounded pagination works, subdirectory roots are preserved, and requested Rank Math key presence can be inspected without printing values.

**BLOCKED:** store root and read credentials absent. **UNKNOWN:** CJ's metadata key names or whether all linkage lives in Woo metadata at all. A SKU match or a fabricated `cj_*` field does not establish linkage. Compare Woo product/variation IDs and SKUs with CJ's own connected-variant records. Inspect authorized metadata privately; never commit a live dump.

**UNKNOWN:** hosting/WAF/plugin rate limits and whether CJ updates prices or inventory on this store. No universal Woo quota is assumed. Respect 429/Retry-After, start with one product, and avoid load or write tests.

Recommendation and next: use the read-only adapter for one existing linked product; record aggregate connection results, whether every variation is mapped, and the owner-confirmed connector settings. Prove preservation on a safe product before implementing direct Woo creation. No orders or customer endpoints are accessed.

## Rank Math SEO

**DOCUMENTED:** Woo product `meta_data` is readable/writable; current Woo source applies metadata updates. This supports using that interface for `rank_math_title`, `rank_math_description` and `rank_math_focus_keyword`. **Inference, not store verification:** these ordinary post-meta keys should be usable through Woo's generic metadata interface, subject to installed versions, permission checks and filters. [Woo product schema](https://developer.woocommerce.com/docs/apis/rest-api/v3/products/), [official controller source](https://github.com/woocommerce/woocommerce/blob/trunk/plugins/woocommerce/includes/rest-api/Controllers/Version3/class-wc-rest-products-controller.php).

**DOCUMENTED:** Rank Math's public headless `GET /wp-json/rankmath/v1/getHead?url=<full-product-url>` returns rendered head markup when the feature is enabled. It is useful for output verification, not evidence of focus-keyword persistence. Rank Math source also has an authenticated `updateMeta` route, but its editor permissions/version coupling do not establish support with a Woo consumer key. [Headless support](https://rankmath.com/kb/headless-cms-support/), [official REST source](https://github.com/rankmath/seo-by-rank-math/blob/master/includes/rest/class-shared.php).

**VERIFIED, mocked:** all three keys are detected in Woo metadata; absent keys are reported as absent, not as proof of incompatibility.

**BLOCKED:** reliable live read/write behavior remains unproven. No write was attempted, no safe product was supplied, and no plugin was created. Read-only Woo credentials cannot establish update permission.

Recommended test after explicit approval:

1. Identify an owner-approved non-selling test product and a separate temporary Write/Read key. Capture only its three original values and relevant IDs in private storage.
2. Update only the three metadata entries through `PUT /wp-json/wc/v3/products/{id}`; use existing metadata IDs when present. Preserve other metadata and CJ mappings.
3. Read back values, check the Rank Math editor, clear relevant cache if authorized, and verify the rendered title/description. Confirm values survive a CJ connector cycle.
4. Restore original values (including deletion of newly introduced test-only entries if needed) and verify restoration.

The eventual payload shape is `{"meta_data":[{"key":"rank_math_title","value":"approved title"}, ...]}`. This is a documented proposal, not implemented write code.

Prefer Woo metadata: simplest, one credential path, no additional plugin. If the approved test fails, diagnose permissions/filters/installed versions first. Only demonstrated failure justifies a small authenticated bridge with an allowlist of these three fields, edit-product capability checks and output validation. WordPress core `wp/v2` meta registration is a separate interface and does not by itself prove Woo behavior.

## Amazon Selling Partner API

### Account and authorization checklist

All actual account prerequisites remain **UNKNOWN**; API testing is **BLOCKED** by missing credentials.

| Prerequisite | Actual status | Next action |
| --- | --- | --- |
| Professional Seller plan and primary-user access | UNKNOWN | Owner checks account plan, identity/verification and access |
| US and CA selling/marketplace eligibility | UNKNOWN | Check each marketplace separately, including Canada currency/tax setup |
| Private developer profile approval | UNKNOWN | Complete profile, roles, use case and security controls |
| Private app registration and LWA credentials | UNKNOWN | Register private seller app after developer approval |
| Self-authorization / refresh token | UNKNOWN | Authorize this app for the seller; store privately |
| Catalog/listing/fees/pricing and participation roles | UNKNOWN | Request Product Listing and Pricing as applicable; the Sellers participation guide requires Seller Partner Insights; verify operation role mappings |
| Product/category/brand/GTIN permissions | UNKNOWN | Check proposed exact products per marketplace |
| CJ seller-of-record fulfillment agreement | UNKNOWN | Obtain packing, invoice, delivery, returns evidence before later fulfillment |

**DOCUMENTED onboarding:** Professional seller accounts can develop private seller applications; register as a private developer in Seller Central > Apps and Services > Develop Apps (or Settings > Developer Profile in Solution Provider Portal after migration). Submit the organization/data-access/use/security information and applicable roles; wait for approval. Then register a private app, obtain LWA client credentials, and self-authorize to obtain a refresh token. Role changes may require reauthorization. No permission is inferred from possession of a Seller Central login. Check [role definitions](https://developer-docs.amazon.com/sp-api/docs/roles-in-the-selling-partner-api), [operation mappings](https://developer-docs.amazon.com/sp-api/docs/role-mappings), and the participation guide's [Seller Partner Insights prerequisite](https://developer-docs.amazon.com/sp-api/docs/get-seller-market-participation). [Registration overview](https://developer-docs.amazon.com/sp-api/docs/sp-api-registration-overview), [private developer steps](https://developer-docs.amazon.com/sp-api/docs/register-as-a-private-developer), [connection and authorization](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api).

**DOCUMENTED auth:** POST `https://api.amazon.com/auth/o2/token` with refresh grant, client ID/secret and refresh token; cache the access token using `expires_in`; send it as `x-amz-access-token`. AWS IAM credentials/SigV4 are no longer required. **VERIFIED, mocked:** this exchange, token reuse and participation GET work with fixtures. [LWA connection](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api), [IAM/SigV4 removal](https://developer-docs.amazon.com/sp-api/changelog/sp-api-will-no-longer-require-aws-iam-or-aws-signature-version-4).

US `ATVPDKIKX0DER` and CA `A2EUQ1WTGCTBG2` use the North America API endpoint. The read probe returns each marketplace's presence and participation flag; success does not prove listing-role or category access. [Marketplace IDs](https://developer-docs.amazon.com/sp-api/docs/marketplace-ids).

### Capabilities and limits

The following are **DOCUMENTED only**; only LWA and participation are implemented.

| API / operation | Endpoint under North America root | Purpose | Default requests/sec; burst |
| --- | --- | --- | --- |
| Sellers / getMarketplaceParticipations | GET `/sellers/v1/marketplaceParticipations` | Check authorized marketplaces | 0.016; 15 |
| Catalog Items / getCatalogItem | GET `/catalog/2022-04-01/items/{asin}` | Existing-ASIN facts/matching; search also available | 2; 2 |
| Listings Items / getListingsItem | GET `/listings/2021-08-01/items/{sellerId}/{sku}` | Seller listing state/issues; later PUT/PATCH publishing | 5; 10 |
| Product Type Definitions / getDefinitionsProductType | GET `/definitions/2020-09-01/productTypes/{productType}` | Marketplace/seller-specific JSON Schema | 5; 10 (variable plans) |
| Product Fees / getMyFeesEstimateForASIN | POST `/products/fees/v0/items/{Asin}/feesEstimate` | Proposed-price fee estimate, not an actual charge | 1; 2 |
| Product Pricing / getItemOffers | GET `/products/pricing/v0/items/{Asin}/offers` | Offer comparisons; additional pricing versions exist | 0.5; 1 |
| Listings Restrictions / getListingsRestrictions | GET `/listings/2021-08-01/restrictions` | Seller/ASIN/category restriction checks | 5; 10 |

References: [participation](https://developer-docs.amazon.com/sp-api/reference/getmarketplaceparticipations), [catalog](https://developer-docs.amazon.com/sp-api/reference/getcatalogitem), [listings](https://developer-docs.amazon.com/sp-api/reference/getlistingsitem), [definitions](https://developer-docs.amazon.com/sp-api/reference/getdefinitionsproducttype), [fees](https://developer-docs.amazon.com/sp-api/reference/getmyfeesestimateforasin), [pricing](https://developer-docs.amazon.com/sp-api/reference/getitemoffers), [restrictions](https://developer-docs.amazon.com/sp-api/reference/getlistingsrestrictions).

These are operation defaults, not measured quotas or a shared global allowance. Limits vary by application/seller/operation and can change. Later workers must use each operation's rate-limit headers when available, handle 429 and maintain separate budgets. A missing header is not unlimited access. [Usage plans](https://developer-docs.amazon.com/sp-api/docs/usage-plans-and-rate-limits). The participation probe is for occasional manual checks; it does not schedule polling.

For matching, use Catalog Items identifiers and exact attributes; never reuse an ASIN for a different product. New catalog contributions require the product type schema and a legitimate identifier or an applicable category/brand GTIN exemption. Exemption does not grant brand/category/product approval. Apply through Seller Central's Add Products workflow for the exact brand/category combination if eligible; retain the approval privately. [US GTIN exemption guidance](https://sellercentral.amazon.com/gp/help/external/200426310), [Canada guidance](https://sellercentral.amazon.ca/help/hub/reference/external/G200426310). Use seller/marketplace-specific definitions and restrictions, then the appropriate existing-ASIN offer or new-item flow. Accepted submissions can still develop asynchronous errors and need later state verification. [Listing workflow](https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide), [restrictions](https://developer-docs.amazon.com/sp-api/reference/getlistingsrestrictions).

**DOCUMENTED compliance:** the seller must be the seller of record, ensure packaging/invoices identify only the seller, and accept/process returns. Supplier branding or another retailer's identity can violate Amazon policy. **UNKNOWN:** CJ's fulfillment for these exact products satisfies those requirements, promised delivery/tracking and return destinations in both markets. Do not activate Phase 2 based on generic CJ marketing. Obtain contractual and controlled physical-order evidence under a later approval. [Amazon dropshipping policy](https://sellercentral.amazon.com/gp/help/external/help.html?itemID=201808410&language=en_US).

Recommendation: finish authorization and eligibility work before building any publisher. Use separate market data and schema/fee snapshots; request only the operation roles needed now. Customer/address roles and any restricted-data token requirements belong to later fulfillment work.

## Operational safeguards

All API requests have finite timeouts, at most three attempts, bounded exponential retry for transient transport/429/5xx failures, and Retry-After support. Cooldowns exceeding 30 seconds stop the check rather than retrying early. Authentication/permission/validation failures are not blindly retried; CJ business errors inside HTTP 200 fail closed. Redirects and ambient HTTP proxy credentials are disabled.

Application logs are JSON with configured-secret redaction, URL/credential-pattern masking, no exception payloads and no arbitrary extra fields. Request/SQL/access log propagation is disabled. Do not add raw response/request logging. The adapters expose no publishing/order/payment methods; CLI probes require both `--live` and `LIVE_CHECKS_ENABLED=true`. The flag authorizes only those read operations and token exchange, not future writes.

Automated HTTP calls use MockTransport; an autouse fixture rejects unmocked HTTP. The database test requires a separately named disposable `*_test` database. The initial migration only establishes version history; there are no speculative domain tables.

## Verification record and handoff

**VERIFIED locally:** Python 3.12.10; locked uv setup; Ruff lint/format; mocked unit tests; real PostgreSQL 17.7 connectivity; fresh upgrade to `0001_foundation`; downgrade/re-upgrade on a separate disposable database; Alembic schema drift check; Uvicorn startup; browser HTTP 200 with expected JSON for /health and /ready. Hosted CI status belongs to the PR checks; do not infer it from local results.

One upstream Starlette warning currently notes future deprecation of its httpx TestClient integration. The current pinned version passes; reassess that dependency when updating the lock.

Before SAL-63: provide CJ access privately, confirm points/API activation, choose actual origin/warehouse and representative non-customer US/CA postal scenarios, and record live catalog/variant/stock/freight results. Woo linkage/Rank Math round-trip proof and Amazon onboarding remain explicit downstream launch gates. SAL-63 normalization can use these adapters and fixtures while live checks are pending, but must not claim measured profitability or integration success.

## SAL-63 measured update (2026-11-12)

The earlier SAL-62 credential blockers above are historical. During SAL-63, authorized
CJ reads imported 50 products/193 variants and retained 15 route-specific freight
responses (including unavailable routes). Total: 76 HTTP attempts and 860 estimated CJ
points, below the frozen 80/1,000 validation caps. No marketplace mutation occurred.

CN pet-brush freight returned 28 priced methods to US 10001 ($14.07-$82.98 USD), 29 to
US 90001 ($13.15-$82.98), and 16 to CA K1A 0A9 ($10.99-$39.60). The home/kitchen samples
are stocked in US warehouses: CN queries returned no methods; observed-US-warehouse
queries returned zero-priced US methods and no Canada methods. These are retained
supplier responses, not free-shipping guarantees. No response supplied tracking proof.
The actual origin checks are essential; a country-level sample cannot be reused for
other products, warehouses, quantities or destinations.

Full sanitized evidence, counts, limitations and business-input blockers are in
[SAL-63 verification](sal63-verification.md). Woo's prior read-only success is
owner-reported in SAL-63; this run did not repeat Woo or call Amazon. The account is
Individual; Professional-plan SP-API onboarding remains deferred. No Rank Math or CJ
field-ownership write verification is claimed.

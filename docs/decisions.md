# Decisions, assumptions, and open questions

## Accepted planning decisions (2026-11-12)
1. Project: SmartAndCoolAutomation in GitHub; Linear SmartAndCool is the single task tracker. Do not duplicate GitHub Issues.
2. Modular monolith: FastAPI, PostgreSQL, Next.js, Railway/Vercel, GitHub CI. Plan for later orders without implementing them in Phase 1.
3. Supplier master = CJ; pricing/content/approval master = Commerce Core; published listing masters = respective channels.
4. Initial US listing launch, Canada modeled explicitly as a separate market. Target initial low-risk home, kitchen organization and pet accessories. No batteries.
5. Price/margin based on auditable deterministic calculation and real freight, not LLM estimates. Manual initial approval and fail-closed eligibility/price gates.
6. Reuse existing CJ-Woo connection and test CJ native publishing rather than rebuilding it unnecessarily. Amazon through SP-API after access is granted.
7. WooCommerce Rank Math SEO optimized separately from Amazon content.
8. Phase 2 preferred Amazon -> Woo -> CJ fulfillment path so completed Woo orders can enter QuickBooks with no dedicated paid Amazon integration. Only one CJ submission route for each imported order.
9. QuickBooks previously synced completed Woo orders; currently disabled. Amazon marketplace-facilitator taxes excluded from Woo revenue/tax liability when remitted by Amazon; track original breakdown separately. Reconcile fees and bank payouts through an Amazon Clearing account to prevent duplicate revenue.

## Unverified / decisions pending
- Amazon Professional seller account and SP-API app registration, product-category permissions and future restricted shipping-address role.
- Exact CJ native Woo publishing behavior, variant linking, stock/status transitions, webhook failures and pricing ownership.
- Availability and behavior of chosen Woo-to-QuickBooks connector after reactivation; payment mapping and duplicate safeguards.
- Rank Math REST metadata support without companion plugin.
- Amazon policy-compliant CJ packaging, shipping SLA and return destination.
- Which business location/warehouse and supported postal-code shipping scenarios to use for US/CA profit screening.
- Rate, foreign exchange, duty/customs and tax assumptions for Canada; category-specific regulatory/documentation checks.
- Whether separate Amazon->QuickBooks connector is included without additional charges (optional alternative); do not subscribe blindly.
- Repo visibility is currently public. Recommend private before adding proprietary data. Never commit secrets or customer information.

## Change control
When a decision changes, edit this file in the same PR as affected code, and update relevant Linear issue status/acceptance criteria. Architectural changes requiring a different fulfillment route must include duplicate-prevention and reconciliation tests.

## SAL-62 implementation decisions (2026-11-12)

These refine the accepted planning decisions; they do not replace the supplier, channel, fulfillment or accounting ownership decisions.

1. Use uv with a committed lockfile and Python 3.12 for the tested baseline. Use a `src` Python package and one FastAPI application factory; defer the dashboard until a review workflow needs it. This keeps setup and maintenance small.
2. Use synchronous SQLAlchemy/psycopg and httpx for current bounded workloads. Sync HTTP routes keep database calls off the event loop. No async database stack or background infrastructure is justified by the current scope.
3. PostgreSQL 17 Compose is loopback-only, with a persistent development volume and a separate disposable test database. Alembic runs explicitly and begins with a version-only baseline; do not invent future domain schemas.
4. Integration adapters expose no publishing/order/payment methods. Live CLI reads require two opt-ins; publishing will need its own explicit authorization and controls later. Avoid speculative feature flags that imply a working publisher.
5. CJ's current official contracts use listV2 keyword search, destination-specific freight, points quotas and returned token-expiry dates. Use conservative per-instance pacing and process-local token caching for sequential manual checks. Distributed scheduling and persistent rotation are deferred.
6. CJ documentation reports no redelivery of failed webhooks and no automatic Woo inventory sync at listing. Retain reconciliation as a launch requirement; actual connector behavior remains unverified.
7. Rank Math's simplest candidate is Woo `meta_data` for the three specified keys. Core schema/source support is not a live persistence proof. Prefer this route for fewer moving parts; an approved round-trip/editor/render/CJ-cycle test must pass. A bridge adds security and maintenance cost and is justified only by demonstrated incompatibility.
8. Keep Amazon configuration minimal: self-authorized private app + LWA token exchange and marketplace-participation read. Do not introduce obsolete IAM/SigV4 setup. Actual Professional account, approved roles, category/GTIN permissions and both marketplace statuses remain unknown.
9. Preserve the existing CJ-Woo connection. Native CJ async publication may simplify variant linking, but field ownership and async error behavior need an approved experiment before choosing it over direct Woo publication.
10. Keep all live payloads and mappings private. This task makes no repository-visibility change. The historical public-repository warning remains applicable; no permission to publish proprietary evidence is implied.

See [integration feasibility](integration-feasibility.md) for primary sources, tested-versus-documented labels, risks and next steps.

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

## Amazon selling-plan constraint (2026-11-12)
- Account owner reports that Seller Central is currently on the **Individual** selling plan after previously downgrading to avoid the $39.99 monthly Professional charge. This is owner-reported; no seller account verification was performed.
- Amazon's official plan comparison and SP-API registration documents state Individual sellers do **not** have SP-API, bulk uploads/feeds, or custom non-media shipping-rate controls. Do not promise direct API/third-party API access on this plan.
- **Decision:** do not upgrade solely for SAL-63. Prioritize live CJ + Woo **read-only** validation, product economics, content drafting, and Woo publishing. Build an Amazon manual listing package (copy/images/attributes/pricing) as an interim pathway, but do not scrape Seller Central or attempt to bypass plan restrictions.
- Model Amazon Individual economics separately: $0.99 per unit sold in addition to category referral fees, Amazon-set non-media shipping credits, and real CJ fulfillment cost. Professional modeling uses $39.99/month and omits the Individual per-unit fee; compare plan-level break-even based on actual volume, contribution and automation benefits.
- **Amazon SP-API work remains gated on Professional upgrade and developer authorization**. A temporary upgrade/downgrade is not a sustainable route to ongoing automated listings/orders, because plan downgrades remove Professional-only capabilities.
- The owner reports CJ and Woo keys have been created; live connectivity and correct account permissions remain **UNVERIFIED** until read-only probes complete. Never put credentials in source control or Linear.
- References: https://sell.amazon.com/developers ; https://sellercentral.amazon.com/gp/help/external/64491 ; https://sell.amazon.com/blog/amazon-professional-vs-individual-selling-plan .

## SAL-63 live-access handoff (2026-11-12)
- **Owner-reported local verification, not independently replayed by this document:** `uv` 0.13.7 installed on Windows; Python 3.12.10; PostgreSQL 17.7; 43 tests, Ruff, migrations, and FastAPI /health + /ready all passed. Repository `main` was clean at the time of the report.
- **CJ live:** API authentication, catalog search, product detail, variants, inventory and a SKU matched to an existing Woo variation. No quota errors observed during the probes.
- **Woo live:** read-only authentication, products, categories, attributes and variations passed. Three Rank Math metadata keys were present. **Writing, persistence in editor, and rendered SEO tags remain unverified.** The SKU match alone does not prove every variation has a working CJ fulfillment link or establish price/stock ownership.
- **One-unit, CN-origin sample freight:** US destination ZIP 10001 had 20 priced methods (USD $11.01–$82.98); Canada K1A 0A9 had 10 methods (USD $8.97–$17.70). No subwarehouse ID was returned, so CJ selected a warehouse. Quotes are destination/product/quantity specific; **not** proof of other ZIPs, tracking, delivery SLAs, customs, taxes, or total landed costs. Store quotes with origin/destination/method/variant/quantity/time and quote status.
- Credentials are in the user's local, git-ignored `.env`. Live-check opt-in was switched off after testing. No values or real CJ/Woo product IDs are included in public documentation.
- **Decision:** Begin SAL-63 locally with CJ ingestion, safe screening, destination-specific cost snapshots and a deterministic pricing engine. Amazon remains Individual, so use configurable provisional fee schedules and manually sourced price benchmarks; label unverified economics and never imply SP-API fee estimates. No product publishing or orders as part of SAL-63.
- **Open gates for later:** Rank Math write/render test and CJ field ownership before SAL-65; Amazon Professional/SP-API and policy compliance before Amazon automation. Canada requires separate FX, duties and tax review.

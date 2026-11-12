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

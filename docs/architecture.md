# Architecture — SmartAndCool Automation

## Objective
Build a maintainable, modular-monolith product automation system. The platform maintains a canonical supplier catalog and separate marketplace listings. Fulfillment is a later phase, designed now to avoid unnecessary rework.

## System boundaries
- **CJ Dropshipping:** authoritative supplier product/variant data, cost, warehouse, stock and available freight; existing WooCommerce connection for CJ-linked products.
- **Commerce Core (FastAPI):** product screening, normalized data, freight/cost snapshots, deterministic profitability, AI content generation with factual checks, approval, category mapping, publishing orchestration, reconciliation, exception handling.
- **PostgreSQL:** products, variants, cost_quotes, listing_drafts, channel_listings, category_mappings, jobs, audit_events; future orders/order_lines/fulfillment_events/settlements. Monetary values are DECIMAL + currency. Unique external IDs and idempotency keys enforce deduplication.
- **WooCommerce:** storefront and a potential fulfillment/accounting hub; direct Woo REST and CJ native Woo publishing are both evaluated. Confirm whether CJ synchronization overwrites merchant-managed fields.
- **Amazon:** SP-API Listings Items for initial submissions; Catalog Items/Product Type Definitions for matching and schema validation; Product Fees/Pricing for fee and competitive-price checks; JSON_LISTINGS_FEED only when justified. Existing-ASIN offers and new catalog contributions require different listing behavior.
- **Rank Math:** title/description/focus-keyword fields, with REST meta support verified; add minimal WordPress bridge only if necessary.
- **Dashboard:** product discovery, review/approval, listings, exceptions only.

## Product-listing flow (Phase 1)
1. Search/import CJ candidate and preserve original facts and media references; normalize product, variants and warehouse stock.
2. Apply product exclusions and Amazon eligibility gates (category, brand/IP, GTIN/exemption, required attributes, documentation, compliant images).
3. Quote tracked freight by variant/destination/warehouse for US and Canada; record quote time and delivery estimates. Don't use unsupported destinations or assume one rate works nationwide.
4. Compute channel- and market-specific price based on supplier cost, shipping, fees, FX, returns allowance and targeted profit; compare against competitive price. Never let an LLM calculate financial results.
5. Generate distinct factual Woo SEO and Amazon listing drafts; reject unsupported claims and attribute mismatches.
6. Map Woo categories and Amazon product-type definitions; approve manually.
7. Publish independently to Woo and Amazon; persist IDs, asynchronous submission/polling status, errors and verification. A submitted Amazon listing is not necessarily active/buyable.
8. Reconcile stock, costs and listing status on schedule; pause unsafe/unprofitable listings under defined rules. Use webhook updates when available, with periodic reconciliation for missed events.

## Order flow (Phase 2 — not active)
Preferred path to validate: Amazon order -> Commerce Core -> **one** externally-paid WooCommerce order -> existing Woo-to-CJ fulfillment -> CJ tracking -> WooCommerce and Amazon shipment confirmation. Completion can trigger Woo-to-QuickBooks sync.

**Critical controls:**
- Unique constraint on (amazon_marketplace_id, amazon_order_id); persist Woo order ID, CJ order ID and shipment IDs.
- No direct Commerce Core -> CJ order submission for Amazon-origin orders while Woo -> CJ owns fulfillment.
- Import external Amazon payment without running checkout or charging the customer again. Mark processing only after paid/fulfillable status verified. Suppress unwanted emails.
- Confirm CJ ingests API-created Woo orders and does not double-fulfill them. Verify Woo stock side effects and one fulfillment path in a real controlled test.
- Complete Woo order only after confirmed shipping/tracking, following connector expectations, with idempotent transitions.
- Returns, cancellations, split shipments, partial refunds, address permissions and exception queues must be explicitly handled before auto-fulfillment.
- If Woo-created Amazon orders cannot reliably trigger CJ, revisit route; do not activate parallel routing.

## Accounting intent
Woo completed orders sync to QuickBooks through the user's existing or restored connector. The historical preferred Woo representation for Amazon sales is **product revenue + customer shipping revenue**, excluding marketplace-facilitator taxes already remitted by Amazon, while preserving original tax metadata.

Illustration: $38.97 product + $4.49 charged shipping = $43.46 Woo sales. Amazon withheld $3.22 + $0.37 tax, charged $7.51 fees, resulting in $35.95 earnings. Do not treat an Amazon payout as new revenue. Verify actual settlement statements and whether other refunds/fees affect deposits.

Target Amazon Clearing account: debit clearing for gross merchant proceeds; post Amazon fees/adjustments; clear against actual bank deposits. Reconcile fees and payouts monthly (including ads, refunds and FX), not as duplicated sales. Confirm QuickBooks connector supports payment/account mapping and completed-status trigger; otherwise adjust before go-live. Consult bookkeeper for tax/recognition specifics, including Canada.

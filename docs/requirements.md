# MVP requirements, scope and acceptance

## Phase 1 — listing MVP
**In scope:** CJ product and variation ingestion; images and supplier facts; US and CA cost/shipping quotes; item screening; configurable profitability engine; factual AI content for Woo SEO and Amazon; separate category mappings and channel drafts; human review; Woo publishing with Rank Math; Amazon SP-API listing if authorized; inventory/cost reconciliation; audit/errors and retries.

**Out of scope now:** fully automated paid orders, automatic CJ purchase/payment, QuickBooks integration changes, sophisticated inventory ERP, autonomous agents, microservices, bulk feeds, unapproved product publishing, broad consumer product categories.

## Launch gates
- No battery/electrical items. Exclude supplements, food, medication, cosmetics, branded replicas, children's safety equipment, and other higher-risk goods. Validate kitchen food-contact documentation if any.
- US first, Canada a separate market with verified Amazon eligibility, tracked delivery, taxes/customs and CAD conversion. Do not silently copy US shipping/price to Canada.
- Margin target >=25% and contribution profit >=$5 per unit are proposed defaults, not guarantees. Count product cost, shipping, marketplace fees, returns reserve and relevant costs; advertising scenario separately. Reject when competitive price does not support margin.
- Manual approval required for initial publication. No AI-invented product properties, compliance or images.
- Amazon seller account/SP-API access and appropriate restricted roles for future shipping addresses: **unknown / unverified**.
- Confirm CJ can fulfill Amazon orders compliantly under Amazon seller-of-record, packaging, delivery and return rules before activating Phase 2.
- WooCommerce CJ connection is reported connected; verify API-created product publishing and CJ variant linkage in test.
- Rank Math confirmed as chosen plugin; verify REST metadata behavior; no bridge plugin without demonstrated need.
- QuickBooks currently inactive. Existing connector name and completed-order behavior unverified; do not reactivate until Phase 2 testing.

## Tests / definition of done
- Import 50 CJ candidates including usable variants/media with stable identifiers and deduplicated reimports.
- US and CA destination freight calculations produce auditable quotes and deterministic cost/margin values, including missing quote handling.
- Produce fact-checked channel-specific drafts and reject excluded/unqualified products.
- Publish and verify at least 10 Woo products with CJ linkage, variations, merchant-managed price and Rank Math SEO; prevent duplicates on retries.
- When Amazon access and listing eligibility permit, publish and verify a small US test set; otherwise record the explicit blocker, not a fabricated success.
- Demonstrate reconciliation, transient failure retry, stale quote rules, margin-triggered pause, and audit events.
- No customer data or API keys committed. Automated tests/CI pass before merging.

## Implementation order
1. Foundation + integrations feasibility.
2. CJ catalog, freight and pricing.
3. AI content, screening and approval.
4. Woo/Rank Math publication.
5. Amazon authorization/matching/publication.
6. Listing reconciliation and launch test.
7. Separate later phase: Amazon -> Woo -> CJ + QuickBooks reconciliation and returns.

## API validation checklist
CJ auth/limits, catalog variants, shipping by destination and warehouse, native Woo publishAsync behavior, webhooks; Woo product/variation APIs, source IDs, status/stock/tax side effects; Rank Math metadata persistence; Amazon developer registration, marketplace permissions, catalog product type, fee estimate, submission statuses. Treat undocumented behavior as an integration hypothesis until verified.

## SAL-62 foundation acceptance (separate from the later listing MVP)

Implemented scope: locked Python 3.12+/FastAPI backend, PostgreSQL/SQLAlchemy/Alembic infrastructure, local Compose database, centralized environment configuration, redacted JSON application logs, small read-only integration adapters/probes, unit and PostgreSQL smoke tests, backend CI and evidence documentation. Next.js remains the future dashboard stack; it is not needed for this foundation.

Acceptance checks:

- Locked setup, backend startup, independent liveness/readiness, actual PostgreSQL connectivity and fresh migrations.
- Ruff lint/format, mocked provider success/failure/auth/retry tests, disabled-by-default CLI probes, and a disposable PostgreSQL migration round trip/drift check.
- GitHub Actions runs the same gates with a PostgreSQL service; hosted results are reported through PR checks.
- Live CJ catalog/freight and Woo/Rank Math evidence when credentials and any required test approval exist; otherwise explicit blockers. Mocked proof must never be called live integration verification.
- Amazon account/authorization/marketplace/eligibility checklist; no assumed access.
- No publishing, orders, payments, deployment, customer data, committed credentials or Phase 2 execution.

The 50-product import and 10-product publication criteria above are later MVP gates, not implemented or claimed by SAL-62. [Integration feasibility](integration-feasibility.md) records the handoff and pending proofs.

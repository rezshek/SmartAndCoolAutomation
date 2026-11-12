# SmartAndCool Automation

A lean commerce automation platform for importing CJ Dropshipping products, evaluating profitability, generating channel-specific content, and publishing to WooCommerce and Amazon. Future fulfillment imports Amazon orders into WooCommerce, uses the existing CJ connection, and supports QuickBooks accounting.

**Status:** Planning / discovery. No live publishing or fulfillment is enabled.

## Markets and product scope
- United States first; Canada supported as a separate market with CAD pricing, shipping, tax and marketplace validation.
- Initial candidates: home organization, non-electrical kitchen organizers, low-risk pet accessories.
- Exclude batteries/electrical devices, ingestibles, supplements, pet medication, counterfeit/branded replicas, and regulated/high-risk items. Food-contact items require documentation.
- Initial manual approval. Target contribution margin 25% and minimum unit profit $5, both configurable; exclude ads/overhead unless explicitly modeled.

## Tracking
- [Linear SmartAndCool](https://linear.app/shekarlabs/project/smartandcool-15fb4267a008): consolidated work items and status (no duplicate GitHub Issues).
- [Architecture](docs/architecture.md): system boundaries and processing flows.
- [Requirements and acceptance](docs/requirements.md): scope, rules, verification and risks.
- [Decisions and open questions](docs/decisions.md): assumptions, confirmed decisions and unresolved dependencies.

## Planned stack
Python/FastAPI + PostgreSQL + SQLAlchemy/Alembic, httpx/Pydantic, Next.js/TypeScript, GitHub Actions; Railway API/cron jobs and Vercel dashboard. No microservices, Redis or Celery unless justified by observed workload.

## Delivery
1. API access and scaffold.
2. CJ catalog, shipping, profitability and AI content.
3. WooCommerce publication and Rank Math.
4. Amazon US listing authorization, matching and publication.
5. Reconciliation and controlled scale.
6. Later: end-to-end order fulfillment and accounting.

Never commit credentials, tokens, customer addresses, or financial exports. Use environment secrets and sanitized fixtures.

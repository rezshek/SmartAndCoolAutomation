# SmartAndCool Automation

A lean commerce automation platform for importing CJ Dropshipping products, evaluating profitability, generating channel-specific content, and publishing to WooCommerce and Amazon. Future fulfillment imports Amazon orders into WooCommerce, uses the existing CJ connection, and supports QuickBooks accounting.

**Status:** SAL-62 foundation implemented; live integrations await credentials and verification. No live publishing or fulfillment is enabled.

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

## Stack
Python/FastAPI + PostgreSQL + SQLAlchemy/Alembic, httpx/Pydantic, Next.js/TypeScript, GitHub Actions; Railway API/cron jobs and Vercel dashboard. No microservices, Redis or Celery unless justified by observed workload.

## Delivery
1. API access and scaffold.
2. CJ catalog, shipping, profitability and AI content.
3. WooCommerce publication and Rank Math.
4. Amazon US listing authorization, matching and publication.
5. Reconciliation and controlled scale.
6. Later: end-to-end order fulfillment and accounting.

Never commit credentials, tokens, customer addresses, or financial exports. Use environment secrets and sanitized fixtures.

## Local development (SAL-62)

Requirements: Python 3.12+, uv 0.13.7 and Docker with Compose. Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/) or `python -m pip install uv==0.13.7`.

From the repository root (PowerShell):

```powershell
Copy-Item .env.example .env
uv sync --locked
docker compose -p smartandcool-sal62 up -d --wait db
uv run --locked alembic upgrade head
uv run --locked uvicorn smartandcool.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

POSIX shells use `cp .env.example .env`; the remaining commands are the same. The lockfile covers runtime/dev dependencies; `.python-version` selects 3.12. Run `uv lock` only for intentional dependency updates and commit the reviewed lockfile.

- `GET http://127.0.0.1:8000/health`: liveness, HTTP 200 without a database query.
- `GET http://127.0.0.1:8000/ready`: bounded PostgreSQL `SELECT 1`, HTTP 200 or sanitized 503. Apply migrations separately before starting; readiness is not a schema-version check.
- `/docs`: generated FastAPI reference. There are no commerce/write routes.
- PostgreSQL is bound to `127.0.0.1:54329`. Example credentials are for local use only. Keep the named volume; `docker compose -p smartandcool-sal62 stop` stops this project's containers without deleting data.

### Validation

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked alembic check
uv build
```

Unit tests use synthetic fixtures and mocked HTTP. To also run the PostgreSQL smoke test, create a separate disposable database (it must end in `_test`):

```powershell
docker compose -p smartandcool-sal62 exec -T db createdb -U smartandcool smartandcool_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://smartandcool:local-dev-only@127.0.0.1:54329/smartandcool_test"
uv run --locked pytest
```

Run `createdb` once. POSIX equivalent: `export TEST_DATABASE_URL='postgresql+psycopg://smartandcool:local-dev-only@127.0.0.1:54329/smartandcool_test'`. The test upgrades, checks, downgrades and re-upgrades that disposable database. It never resets the development database. GitHub Actions performs lint/format, fresh migrations, drift validation, the full suite with PostgreSQL and a package build; no integration secrets are required.

Alembic's initial revision establishes history only. SAL-63 adds canonical domain models with new reviewed migrations. Run `uv run alembic revision --autogenerate -m "description"` after importing new models in the migration environment; inspect every generated migration.

### Read-only integration checks

See [integration feasibility](docs/integration-feasibility.md) for official contracts, evidence, blockers and approved-test requirements. Put credentials in the ignored `.env` privately. Create a **separate Read-only** Woo key; preserve the existing CJ connector key.

Checks require both `LIVE_CHECKS_ENABLED=true` and `--live`:

```powershell
$env:LIVE_CHECKS_ENABLED = "true"
uv run --locked sca-check cj --live
uv run --locked sca-check woo --live --product-id 123
uv run --locked sca-check amazon --live
```

Replace 123 with an owner-selected existing product ID. For freight, use the actual variant ID, origin/warehouse and a non-customer destination postal code. Example argument shapes:

```text
uv run --locked sca-check cj --live --product-id <pid> --variant-id <vid> --origin CN --destination US --postal-code <US-postal> --warehouse-id <storage-id>
uv run --locked sca-check cj --live --variant-id <vid> --origin CN --destination CA --postal-code <CA-postal> --warehouse-id <storage-id>
```

Quote calls use POST but do not create orders or charges; CJ reads consume API points. Run one CJ check at a time. Outputs contain counts/presence flags only. An empty freight-options result is not a usable quote. A successful Woo read does not prove CJ linkage or Rank Math persistence; Amazon participation does not prove listing eligibility. Disable the flag after use. Never paste secrets or raw live payloads into commits, issues, logs or PRs.

### Repository layout

```text
src/smartandcool/        settings, JSON logging, database, FastAPI factory, CLI checks
src/smartandcool/integrations/
                        small CJ, Woo and Amazon read-only adapters
migrations/             Alembic environment and reviewed revisions
tests/                  mocked unit tests, synthetic fixtures, optional PostgreSQL smoke
docs/                   architecture, requirements, decisions, integration evidence
.github/workflows/      backend CI
```

No dashboard is scaffolded yet. Railway/Vercel remain future hosting targets; deployment, product publication and Phase 2 are outside SAL-62.

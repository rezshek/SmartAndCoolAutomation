# SAL-63 catalog, freight and pricing

The existing Python/FastAPI/PostgreSQL foundation now has a sequential CLI and small
service functions. There are no new HTTP routes, dependencies, publishers, order
operations, dashboard, scheduler or AI classifiers. Amazon Individual economics are
modeled locally; no SP-API access is assumed.

## Database and audit trail

Revision `73d0224df33d` adds seven tables after the untouched SAL-62 revision:

| Table | Purpose |
| --- | --- |
| products | Canonical CJ product ID, supplier SKU, category, description, image URLs/metadata, attributes, USD price, weight and last sync |
| variants | Globally unique CJ variant ID, parent, supplier SKU, attributes/barcode, image, USD price, grams and mm dimensions, active flag, sync/inventory times |
| product_snapshots | Immutable original detail/variant/search facts, source/unit/currency basis, SHA-256 digest and first observation; identical facts deduplicated |
| inventory_snapshots | Timestamped country totals and separate subwarehouse CJ/factory facts; unknown is nullable, never zero |
| freight_quotes | Exact variant, batch quantity, destination postal/country, origin, requested warehouse IDs, timestamp, local expiry policy and original response, including empty routes |
| shipping_methods | All returned methods, exact USD costs, raw delivery estimates, parsed day range, nullable tracking and source facts |
| catalog_import_runs | Frozen query, next page, saved pending discoveries and completed IDs; product + progress commit atomically |

Money/measurements use `NUMERIC(20,6)` and explicit currency/units; calculations use
`Decimal`. Foreign keys, stable-ID primary keys and nonnegative/quantity/destination/
expiry constraints protect writes. Product/variant upserts are idempotent; later
imports retain old snapshots and mark disappeared variants inactive. Missing new
inventory invalidates previous current inventory. Snapshot timestamps describe
observations, not supplier inventory guarantees. Country totals and subwarehouse
stock are never added together. Factory inventory remains a review flag.

Migrations run explicitly. Upgrade is additive. Downgrade drops these domain tables
and is tested only on a disposable `*_test` database; never downgrade an imported
development catalog. No application-startup migrations or production writes are added.

## Workflow (PowerShell)

Use the existing local PostgreSQL container and private `.env`. Keep all exports and
business assumptions in ignored `local-data/`. The CLI refuses non-loopback databases
and output paths outside that directory. Do not share supplier payloads or mappings
in the public repository. Do not overwrite an existing `.env`.

```powershell
uv sync --locked
uv run --locked alembic upgrade head
New-Item -ItemType Directory -Force local-data | Out-Null
Copy-Item docs/pricing.example.json local-data/pricing.json

# These five commands need both gates; reads consume CJ points.
$env:LIVE_CHECKS_ENABLED = "true"
uv run --locked sca-catalog categories --live --output local-data/categories.json
uv run --locked sca-catalog search --live --keyword "organizer" --size 25 --output local-data/search.json
uv run --locked sca-catalog import --live --run-id home-candidates --keyword "organizer" --limit 50 --call-budget 60 --point-budget 1000
# Add --category-id <actual-third-level-ID> to search/import when selected from categories.
uv run --locked sca-catalog stock --live --variant-id <actual-VID>
uv run --locked sca-catalog quote --live --variant-id <actual-VID> --origin CN --destination US --postal-code 10001 --quantity 1
uv run --locked sca-catalog quote --live --variant-id <actual-VID> --origin CN --destination CA --postal-code "K1A 0A9" --quantity 1
Remove-Item Env:LIVE_CHECKS_ENABLED

# These operations use only local records, and do not require live credentials.
uv run --locked sca-catalog runs
uv run --locked sca-catalog inspect --product-id <actual-PID> --output local-data/product.json
uv run --locked sca-catalog report --config local-data/pricing.json --output local-data/ranked.json
uv run --locked sca-catalog report --config local-data/pricing.json --output local-data/ranked.csv
```

Replace placeholders with IDs from your private exports. For other postal samples,
call quote explicitly; use `--warehouse-id <stockId>` when known (repeatable),
`--quantity` for a batch, and `--ttl-hours 1..24` for the local freshness window.
An area ID is not a subwarehouse stock ID. Origin/warehouse matching is checked
against current inventory when reporting. CN is an explicit sample, never an inferred
origin. No automatic selection of the cheapest method occurs; every method is a
separate scenario requiring tracking, service eligibility and delivery checks.

Defaults: 10 HTTP attempts and 1,000 estimated points per invocation; all auth calls
and retries count against the HTTP budget. Search costs 50 estimated points, current
product/variant/stock/freight reads 10; estimates are conservative for unlisted
product reads. CJ `pointsInfo.remaining` is honored when returned. Point exhaustion
stops without retry; long provider cooldowns stop. Other transient errors retain
SAL-62's maximum three attempts and 1.1-second minimum CJ pacing. No parallel CJ
workers. Pagination is capped at 20 pages and imports at 100 IDs per run.

After a failed or interrupted import, previously committed products remain available:

```powershell
$env:LIVE_CHECKS_ENABLED = "true"
uv run --locked sca-catalog import --live --run-id home-candidates --resume --call-budget 30 --point-budget 500
Remove-Item Env:LIVE_CHECKS_ENABLED
```

Resume uses the saved query/limits, including pending page items, instead of changed
CLI search arguments. `COMPLETE` means that run reached its target, available results,
or page cap; inspect the returned count. A fresh run can reimport/update the same
products without duplicates. Authentication caching remains process-local; use the
existing optional private token pair to reuse authentication across short CLI runs.
Never retry login loops or rotate keys to bypass quota/access failures.

## Pricing formula and assumptions

Each profile is independently calculated for its channel and market. `category_policies`
can override a complete policy under `[profile-name][CJ-category-ID]`; an override
must retain the profile's market/channel/currency. Category assignment and flat
referral schedule/minimum are explicit assumptions, provisional unless verified with
a source. Tiered or otherwise unsupported real fee schedules require review rather
than claiming the flat-rate model is exact.

For one unit, define `R = item_price + actual_shipping_revenue`. Supplier price and
batch freight/quantity are converted to the market currency using the supplied FX:

```text
referral = max(R * referral_rate, referral_minimum)     [Amazon only]
payment  = R * processing_rate + processing_fixed     [Woo only]
returns  = R * returns_rate
ads      = R * advertising_rate + advertising_unit_cost
profit   = R - supplier - freight/quantity - referral - individual_fee
             - payment - returns - ads - additional_unit_cost
margin   = profit / R
```

Fees/reserves are rounded up to market cents; the item-price floor is rounded up,
then actual profit/margin are checked again at that precision. The engine solves
both the percentage referral and minimum referral branches and chooses a floor
meeting both configurable thresholds (defaults 25% margin and USD-equivalent $5).
Costs/FX conversions retain Decimal precision. USD/CAD conversion supports both
directions; FX has source, aware timestamp, verified flag and maximum age. No FX is
fetched or invented. Canadian selling prices and fixed fees retain explicit currency.
The default Individual fee is the owner's **provisional USD $0.99** assumption; the
Canadian fee/currency must be independently supplied/verified before approval.

Actual shipping credits/revenue must be supplied, including an explicit zero when
justified. No missing Amazon credit becomes free shipping or presumed revenue.
Returns reserve and additional variable costs must also be explicit. Additional
costs include applicable duties, import charges, unrecoverable taxes, packaging and
other per-unit costs; an explicit zero still requires a verified landed-cost source.
Supplier/freight costs are not evidence that these charges are zero. Taxes collected
and remitted on the customer's behalf are outside merchant revenue; store/payment
tax-fee differences must be included in configured variable costs or remain under review.

The checked-in template intentionally leaves critical inputs null. Fill them privately
with documented business inputs. `fees_verified`, `shipping_revenue_verified`,
`landed_costs_verified` and their sources control provisional labeling, not arithmetic.
`advertising_rate`/`advertising_unit_cost` enable an optional scenario. A supplied
`max_price` or `competitor_price` is an item-price ceiling in market currency; either
can reject an unrealistic required price. No ceiling means commercial review is needed.

Results distinguish `UNPRICEABLE` (critical missing/stale inputs), `REJECTED` (exclusion,
unavailable stock, untracked/too-slow service or price cap failure), `NEEDS_REVIEW`
(conditional economics or unresolved evidence), and `PASS` (manual-review shortlist,
never a listing approval or compliance certification). Report both `pricing_status`
and overall status; an arithmetically profitable scenario can fail eligibility/service.
Stale supplier costs or freight are not used for a new recommendation. A newer empty
quote invalidates earlier methods for that exact route. Default quote validity is a
24-hour **local policy**, not a supplier price guarantee. Missing inventory and service
data remain review flags; stock quantity is checked at the quoted origin/warehouse.

Product rules exclude explicit electrical/battery, ingestible/medical/cosmetic,
child-safety and known replica/IP signals. Food-contact and regulatory claims need
document references; unknown product facts, safety and IP always need manual review.
Rules are conservative keyword screening and can overflag products; absence of a
keyword is no compliance proof. Private `product_reviews[PID]` records source,
`safety_reviewed`, `ip_clear`, `food_contact_documents` and `regulatory_documents`.
Product summary counts screen parents; each scenario also screens the variant title
and attributes. A parent manual review cannot override a prohibited variant.
Private `service_reviews` require the exact `quote_id` and `method_id` from a report,
plus matching `method`/`destination`/`origin`, a source, `tracking_verified` and `eligible`.
Reviews without those IDs are rejected. Approval applies only to that method on that
quote and expires with the quote; a fresh quote or changed variant, postal code,
warehouse or quantity needs a new review. A method name alone never proves tracking.
Zero-priced freight additionally needs `zero_price_verified` with that review's source;
the supplier's returned zero is not treated as a free-shipping guarantee. Method errors
or contradictory monetary totals remain unpriceable.

Ranked JSON includes the full input policy and generation time. CSV has an adjacent
`.assumptions.json` with the same provenance and summary. Both include product/variant,
category, market, supplier/freight currencies, route, method and quote validity,
selling-price floor, fees, reserves, profit, USD profit, margin and review/rejection
reasons. Supplier-controlled CSV text is escaped against formula execution. Ranking
is for manual comparison; the report never chooses or books a shipping method.

### Hand-checkable synthetic example (not a real recommendation)

Synthetic USD supplier $3 + freight $7, Amazon referral 15%, Individual fee $0.99,
returns reserve 5%, explicit zero shipping revenue/other costs, and a $100 ceiling:
required item price **$19.99**, referral **$3.00**, reserve **$1.00**, contribution
**$5.00**, margin **25.0125%**. All fees/credits in this example are synthetic test
inputs. A known $4.49 shipping credit reduces item price to $15.50 while the referral
base remains $19.99. A competitor cap of $8 rejects it (contribution -$4.59).

## Verification and remaining business work

Automated tests mock every external HTTP call; PostgreSQL tests use a disposable
`*_test` database and exercise actual migrations, constraints, upserts, checkpoints
and report joins. No test contacts CJ/Woo/Amazon. Run the README CI commands with
`TEST_DATABASE_URL` configured. See [live evidence](sal63-verification.md) for measured
counts, freight samples, actual-vs-synthetic distinctions and remaining assumptions.

Current contracts checked on 2026-11-12: [CJ product/variant/inventory](https://developers.cjdropshipping.com/en/api/api2/api/product.html),
[freight costs](https://developers.cjdropshipping.com/en/api/api2/api/logistic.html),
[points](https://developers.cjdropshipping.cn/en/api/api2/standard/points.html), and
[frequency limits](https://developers.cjdropshipping.com/en/api/api2/standard/limit.html).
Account quotas/access and returned fields can differ; the bounded live results are
observations, never nationwide delivery, compliance or hidden-cost guarantees.

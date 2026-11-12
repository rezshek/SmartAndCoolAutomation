# SmartAndCool Automation — credential onboarding

**No secret values belong in this file, GitHub, Linear, issues, PRs, screenshots, or chats.** The repository is currently public. Use an ignored local `.env` or a secret manager. Do not share credentials with an AI assistant or paste outputs containing tokens.

Scope: SAL-63 needs **CJ and WooCommerce read-only** access; Amazon onboarding can begin in parallel; Rank Math uses Woo metadata and requires no separate credential for the planned path. QuickBooks, OpenAI, Railway and Vercel are **not required** to begin SAL-63.

## CJ Dropshipping (required now)
1. Sign in at [CJ Dropshipping](https://www.cjdropshipping.com/).
2. If needed, go to **Apps → Install App**, find **API** in **Others**, and install it. Installation alone does not create a key.
3. Open [My CJ — API authorization](https://www.cjdropshipping.com/my.html#/authorize/API). Click **Add API**.
4. Enter a name such as `SmartAndCoolAutomation`, choose **Type: API Key**, and confirm. In the listing, find the activated API Key and use **Copy**.
5. Store privately as `CJ_API_KEY` in local `.env`. Do **not** generate a separate MCP token; the backend uses REST.
6. Client code obtains and refreshes access/refresh tokens from this key. The access token is server-side; don't paste it in docs/chat.
7. Inspect your CJ API status and points. Per the June 2026 points model, API calls cost points; **30 consecutive days with zero CJ transaction amount can suspend access**. If suspended, reactivate through the API page; don't keep rotating keys.
8. For US and Canada quotes, select a real CJ variant, actual origin/warehouse and non-customer destination postal codes. Never assume a generic quote is nationwide or includes duties.

Official: [Create key](https://developers.cjdropshipping.com/en/api/start/apikey.html), [token mechanics](https://developers.cjdropshipping.com/en/api/start/token.html), [points/suspension](https://developers.cjdropshipping.cn/en/api/api2/standard/points.html).

## WooCommerce (required now)
1. Log into your existing site's WordPress **WP Admin**.
2. Open **WooCommerce → Settings → Advanced → REST API → Add Key**.
3. Description: `SmartAndCoolAutomation SAL-63 Read Only`. Select an appropriate administrator/service user.
4. Set **Permissions: Read**, then **Generate API Key**. Copy both **Consumer Key** and **Consumer Secret** immediately; the secret may not be recoverable later.
5. Keep the CJ plugin/store authorization untouched. This is an **additional, independent credential** for our read probes.
6. Set `WOO_BASE_URL` to the **HTTPS site root** (including WordPress subdirectory if used), without `/wp-json/`; set `WOO_CONSUMER_KEY` and `WOO_CONSUMER_SECRET` in ignored local `.env`.
7. Find one *existing CJ-linked product* in Woo **Products** and note its product ID and one variation ID. Do not create a new product/order.
8. Later, before publication, generate a **separate Read/Write key** with minimum necessary permission and an explicit safe-product test. Do not replace the read-only key prematurely.

Official: [Woo REST API keys and authentication](https://developer.woocommerce.com/docs/apis/rest-api/authentication/).

## Rank Math (no new key now)
- Uses WooCommerce product metadata: `rank_math_title`, `rank_math_description`, `rank_math_focus_keyword` (read behavior to be verified).
- Read-only inspection does **not** prove that Rank Math persists or renders the values. A write/readback/editor/render test requires explicit approval and a safe test product.
- Rank Math's optional headless `getHead` API can verify rendered metadata, if enabled. It is not required just to use Rank Math with WordPress.
- Do not build a WordPress bridge before proving the default Woo metadata path fails.

Official: [Rank Math headless metadata](https://rankmath.com/kb/headless-cms-support/).

## Amazon Selling Partner API (start onboarding; not required to begin SAL-63)
1. Sign in as the **Primary User** to [Seller Central](https://sellercentral.amazon.com/). Check whether your account is **Professional**, not Individual. Amazon requires Professional status for a private seller developer app.
2. Open **Apps and Services → Develop Apps**. If migrated, use [Solution Provider Portal](https://solutionproviderportal.amazon.com/) / Developer Central.
3. Complete **Developer Profile** as a **Private Developer** for your own company/store. Submit truthful contact, use-case, data access and security information. Request only roles needed for catalog/listing/pricing; generally **Product Listing**, **Pricing**, and **Selling Partner Insights** for marketplace participation. Verify individual operation mappings. Do not request customer-address/restricted roles until the fulfillment phase.
4. Wait for profile approval. Respond to review requests.
5. In Developer Central, **Add new app client** for a private seller app named `SmartAndCoolAutomation`. Select approved roles; save the app.
6. Open **Edit app → View under LWA credentials**. Privately copy **Client ID** and **Client Secret**.
7. For the seller account, select **Authorize app** / self-authorize. This generates a **Refresh Token**; store it privately. Self-authorization requires primary-user access.
8. Put these in ignored local `.env`: `AMAZON_CLIENT_ID`, `AMAZON_CLIENT_SECRET`, `AMAZON_REFRESH_TOKEN`. The application exchanges refresh tokens for short-lived access tokens; AWS IAM keys/SigV4 are not required for current SP-API auth.
9. Verify US and Canada marketplace participation separately. This is not proof of category approval, listing permissions or CJ-compatible dropshipping compliance.
10. Keep customer-order PII and related restricted role authorization for Phase 2.

Official: [Private developer registration](https://developer-docs.amazon.com/sp-api/docs/register-as-a-private-developer), [app registration](https://developer-docs.amazon.com/sp-api/docs/registering-your-application), [view LWA credentials](https://developer-docs.amazon.com/sp-api/docs/viewing-your-application-information-and-credentials), [self-authorization](https://developer-docs.amazon.com/sp-api/docs/self-authorization), [role mappings](https://developer-docs.amazon.com/sp-api/docs/role-mappings).

## Local, read-only checks (PowerShell)
Run from your repository root with no live credentials printed:
```powershell
Copy-Item .env.example .env   # Only if .env does not already exist
notepad .env                   # Enter values privately; never commit
```

Set `LIVE_CHECKS_ENABLED=true` in `.env` temporarily; the CLI **also** requires `--live` and is read-only in SAL-62:
```powershell
uv run --locked sca-check cj --live
uv run --locked sca-check woo --live --product-id 123
uv run --locked sca-check amazon --live
```
Replace 123 with an existing linked product ID. Amazon probe is optional until authorization succeeds. For freight use a real CJ product/variant/warehouse and a non-customer postal code:
```powershell
uv run --locked sca-check cj --live --product-id <PID> --variant-id <VID> --destination US --postal-code <ZIP> --origin CN
uv run --locked sca-check cj --live --variant-id <VID> --destination CA --postal-code <CANADIAN_POSTAL> --origin CN
```
(The `<...>` markers are placeholders—substitute real values.) If a product is shipping from a US warehouse, adjust `--origin` and specify its verified `--warehouse-id` if applicable. Set `LIVE_CHECKS_ENABLED=false` afterward.

Only share **sanitized** outcomes: provider, success/failure, number of catalog items or freight methods, and error category/code without API tokens or full response bodies.

## Later-stage services
- **OpenAI**: only for SAL-64 content generation; create a dedicated project API key under OpenAI's API platform, store server-side, set spend limits. Never use a personal chat subscription as an assumed API credential.
- **QuickBooks**: no credential/subscription needed for SAL-63. Phase 2 will verify the previous Woo->QB connector, completed-order trigger and Amazon Clearing account.
- **Railway/Vercel**: no credentials necessary for local SAL-63. Link deployments later with environment-level secrets, not secrets in the GitHub repo.

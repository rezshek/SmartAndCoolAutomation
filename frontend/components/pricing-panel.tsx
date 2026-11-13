"use client";

import { useEffect, useState } from "react";
import { Calculator, Save } from "lucide-react";
import {
  api,
  label,
  money,
  type Config,
  type Detail,
  type Money,
  type Policy,
  type PriceRow,
  type PriceView,
  type Profile,
} from "@/lib/api";
import { Badge, Field, Notice } from "./ui";

export function PricingPanel({
  id,
  profile,
  detail,
  variant,
  onVariant,
  onSaved,
}: {
  id: string;
  profile: Profile;
  detail: Detail;
  variant: string;
  onVariant: (v: string) => void;
  onSaved: () => Promise<void>;
}) {
  const [view, setView] = useState<PriceView | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const [advanced, setAdvanced] = useState("");
  useEffect(() => {
    let active = true;
    api<PriceView>(
      `products/${id}/${profile}/pricing?variant_id=${encodeURIComponent(variant)}`,
    )
      .then((d) => {
        if (!active) return;
        setView(d);
        const next = { ...d.config, variant_id: variant };
        if (next.variant_id !== d.config.variant_id) {
          next.quote_id = null;
          next.method_id = null;
        }
        setConfig(next);
        setAdvanced(JSON.stringify(next, null, 2));
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, profile, variant]);
  function update(patch: Partial<Config>) {
    setConfig((c) => (c ? { ...c, ...patch } : c));
    setDirty(true);
    setMessage("");
  }
  function policy(key: string, value: Policy[string]) {
    if (config) update({ policy: { ...config.policy, [key]: value } });
  }
  async function calculate(save: boolean) {
    if (!config) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api<PriceView>(
        `products/${id}/${profile}/pricing${save ? "" : "/preview"}`,
        save ? "PUT" : "POST",
        config,
      );
      setView(next);
      setDirty(false);
      setAdvanced(JSON.stringify(config, null, 2));
      setMessage(
        save
          ? "Pricing decision saved. Commercial approval still requires every check to pass."
          : "Preview recalculated. No saved decision changed.",
      );
      if (save) await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recalculation failed");
    } finally {
      setBusy(false);
    }
  }
  const rows = view?.rows.filter((r) => r.variant_id === variant) || [];
  const selected = rows.find(
    (r) => r.quote_id === config?.quote_id && r.method_id === config?.method_id,
  );
  const row = selected || rows[0];
  const variantData = detail.variants.find((v) => v.cj_id === variant);
  const monetary = (key: string) => config?.policy[key] as Money | null;
  const moneyInput = (key: string, title: string) => (
    <Field name={title}>
      <div className="money-input">
        <input
          inputMode="decimal"
          value={monetary(key)?.amount ?? ""}
          placeholder="Unknown"
          onChange={(e) =>
            policy(
              key,
              e.target.value
                ? {
                    amount: e.target.value,
                    currency:
                      monetary(key)?.currency ||
                      String(config?.policy.currency),
                  }
                : null,
            )
          }
        />
        <select
          aria-label={`${title} currency`}
          value={monetary(key)?.currency || String(config?.policy.currency)}
          onChange={(e) =>
            policy(key, {
              amount: monetary(key)?.amount || "",
              currency: e.target.value,
            })
          }
        >
          <option>USD</option>
          <option>CAD</option>
        </select>
      </div>
    </Field>
  );
  const decimalInput = (key: string, title: string, hint?: string) => (
    <Field name={title} hint={hint}>
      <input
        inputMode="decimal"
        value={String(config?.policy[key] ?? "")}
        placeholder="Unknown"
        onChange={(e) => policy(key, e.target.value || null)}
      />
    </Field>
  );
  const textInput = (key: string, title: string) => (
    <Field name={title}>
      <input
        value={String(config?.policy[key] ?? "")}
        onChange={(e) => policy(key, e.target.value || null)}
      />
    </Field>
  );
  if (!detail.variants.some((v) => v.active))
    return (
      <div className="empty">This product has no active variants to price.</div>
    );
  if (!config || !view)
    return error ? (
      <div role="alert" className="error-box">
        {error}
      </div>
    ) : (
      <div className="empty">Loading pricing assumptions…</div>
    );
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h3>Understand the unit economics</h3>
          <p>
            Decimal calculations from SAL-63 · targets default to 25% margin and
            $5 USD contribution.
          </p>
        </div>
        <Badge value={row?.status || "UNPRICEABLE"} />
      </div>
      <div className="form-grid">
        <Field name="Selected variant">
          <select value={variant} onChange={(e) => onVariant(e.target.value)}>
            {detail.variants
              .filter((v) => v.active)
              .map((v) => (
                <option value={v.cj_id} key={v.cj_id}>
                  {v.title || v.sku || v.cj_id} ·{" "}
                  {money(v.supplier_price, v.currency)}
                </option>
              ))}
          </select>
        </Field>
        <Field
          name="Freight quote and method"
          hint="Selection alone does not verify a method. Approval is bound to this exact quote and route."
        >
          <select
            value={
              config.method_id ? `${config.quote_id}:${config.method_id}` : ""
            }
            onChange={(e) => {
              const chosen = rows.find(
                (r) => `${r.quote_id}:${r.method_id}` === e.target.value,
              );
              update({
                quote_id: chosen?.quote_id || null,
                method_id: chosen?.method_id || null,
              });
            }}
          >
            <option value="">No freight method selected</option>
            {rows
              .filter((r) => r.method_id)
              .map((r) => (
                <option
                  key={`${r.quote_id}:${r.method_id}`}
                  value={`${r.quote_id}:${r.method_id}`}
                >
                  {r.origin} → {r.country} {r.postal_code} · {r.method} ·{" "}
                  {money(r.freight_total_original)} · quote #{r.quote_id}
                </option>
              ))}
          </select>
        </Field>
      </div>
      <div className="price-summary">
        <div>
          <small>Supplier cost</small>
          <strong>
            {money(variantData?.supplier_price, variantData?.currency)}
          </strong>
        </div>
        <div>
          <small>Required selling price</small>
          <strong>
            {dirty ? "Recalculate" : money(row?.required_price, row?.currency)}
          </strong>
        </div>
        <div>
          <small>Contribution profit</small>
          <strong>{dirty ? "—" : money(row?.profit, row?.currency)}</strong>
        </div>
        <div>
          <small>Contribution margin</small>
          <strong>
            {dirty || row?.margin == null
              ? "—"
              : `${(Number(row.margin) * 100).toFixed(2)}%`}
          </strong>
        </div>
      </div>
      {dirty && (
        <Notice>
          Assumptions changed. Recalculate to see a current preview.
        </Notice>
      )}
      {!config.method_id && (
        <Notice>
          No freight method is selected. Any displayed calculation is an
          unselected scenario; it cannot establish a saved price.
        </Notice>
      )}
      {row && (
        <>
          <dl className="cost-breakdown">
            {[
              ["Supplier", "supplier_cost"],
              ["CJ freight / unit", "freight_cost"],
              ["Customer shipping revenue", "shipping_revenue"],
              ["Referral fee", "referral_fee"],
              ["Individual seller fee", "individual_fee"],
              ["Payment fees", "payment_fee"],
              ["Returns reserve", "returns_reserve"],
              ["Additional variable costs", "additional_cost"],
              ["Advertising scenario", "advertising_cost"],
            ].map(([title, key]) => (
              <div key={key}>
                <dt>{title}</dt>
                <dd>
                  {dirty ? "—" : money(row[key] as string | null, row.currency)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="route-info">
            <strong>
              {selected ? "Selected route" : "Scenario information"}
            </strong>
            <p>
              {row.origin || "Unknown origin"} → {row.country}{" "}
              {row.postal_code || ""} · {row.method || "No available method"} ·
              Quantity {row.quantity ?? "unknown"}
            </p>
            <p>
              Warehouses: {row.warehouse_ids?.join(", ") || "Not specified"} ·
              Expires:{" "}
              {row.expires_at
                ? new Date(String(row.expires_at)).toLocaleString()
                : "Not quoted"}
            </p>
          </div>
          {!dirty && row.reasons.length > 0 && (
            <Notice>
              <strong>Missing assumptions & review requirements</strong>
              <ul>
                {row.reasons.map((r) => (
                  <li key={r}>{label(r)}</li>
                ))}
              </ul>
            </Notice>
          )}
        </>
      )}
      <h3 className="section-heading">Financial assumptions</h3>
      <p className="muted">
        Enter decimal strings. A blank means unknown. Explicit zero values still
        need evidence.
      </p>
      <div className="form-grid">
        {profile.startsWith("amazon") ? (
          <>
            {textInput("category", "Fee category / product type")}
            {decimalInput(
              "referral_rate",
              "Referral rate",
              "Fraction: 0.15 means 15%",
            )}
            {decimalInput("referral_minimum", "Minimum referral fee")}
            {moneyInput("individual_fee", "Individual seller fee")}
          </>
        ) : (
          <>
            {decimalInput(
              "processing_rate",
              "Payment processing rate",
              "Fraction: 0.029 means 2.9%",
            )}
            {decimalInput("processing_fixed", "Fixed payment fee")}
          </>
        )}
        {moneyInput("shipping_revenue", "Customer shipping credit / revenue")}
        {decimalInput("returns_rate", "Returns reserve rate")}
        {moneyInput("additional_unit_cost", "Additional variable cost / unit")}
        {decimalInput("advertising_rate", "Advertising rate scenario")}
        {moneyInput("advertising_unit_cost", "Fixed advertising / unit")}
        {decimalInput("min_margin", "Minimum contribution margin")}
        {decimalInput("min_profit_usd", "Minimum contribution profit · USD")}
        {decimalInput("competitor_price", "Competitive price ceiling")}
        {decimalInput("max_price", "Maximum selling price")}
        {textInput("fee_source", "Fee schedule source")}
        {textInput(
          "shipping_revenue_source",
          "Shipping credit / revenue source",
        )}
        {textInput("landed_cost_source", "Landed variable cost source")}
      </div>
      <div className="check-grid">
        {[
          ["fees_verified", "Country-specific fees verified"],
          ["shipping_revenue_verified", "Actual shipping revenue verified"],
          [
            "landed_costs_verified",
            "Duties, taxes and variable costs verified",
          ],
        ].map(([key, text]) => (
          <label className="check" key={key}>
            <input
              type="checkbox"
              checked={Boolean(config.policy[key])}
              onChange={(e) => policy(key, e.target.checked)}
            />
            {text}
          </label>
        ))}
      </div>
      <details className="review-details">
        <summary>Foreign exchange · required for CAD calculations</summary>
        <div className="form-grid">
          <Field name="USD to CAD">
            <input
              inputMode="decimal"
              value={config.fx?.usd_to_cad || ""}
              placeholder="Unknown"
              onChange={(e) =>
                update({
                  fx: e.target.value
                    ? {
                        usd_to_cad: e.target.value,
                        source: config.fx?.source || "",
                        observed_at:
                          config.fx?.observed_at || new Date().toISOString(),
                        verified: config.fx?.verified || false,
                        max_age_hours: 24,
                      }
                    : null,
                })
              }
            />
          </Field>
          <Field name="FX evidence source">
            <input
              value={config.fx?.source || ""}
              disabled={!config.fx}
              onChange={(e) =>
                update({
                  fx: config.fx
                    ? { ...config.fx, source: e.target.value }
                    : null,
                })
              }
            />
          </Field>
          <Field name="Observed at · ISO date/time">
            <input
              value={config.fx?.observed_at || ""}
              disabled={!config.fx}
              onChange={(e) =>
                update({
                  fx: config.fx
                    ? { ...config.fx, observed_at: e.target.value }
                    : null,
                })
              }
            />
          </Field>
          <label className="check">
            <input
              type="checkbox"
              disabled={!config.fx}
              checked={config.fx?.verified || false}
              onChange={(e) =>
                update({
                  fx: config.fx
                    ? { ...config.fx, verified: e.target.checked }
                    : null,
                })
              }
            />
            FX verified
          </label>
        </div>
      </details>
      <details className="review-details">
        <summary>Exact-quote freight verification</summary>
        {selected ? (
          <>
            <p className="muted">
              This evidence applies only to quote #{selected.quote_id}, method #
              {selected.method_id}, {selected.origin} → {selected.country}{" "}
              {selected.postal_code}. A new quote needs a new review.
            </p>
            <Field name="Freight verification source">
              <input
                value={
                  config.service_reviews.find(
                    (r) =>
                      r.quote_id === selected.quote_id &&
                      r.method_id === selected.method_id,
                  )?.source || ""
                }
                onChange={(e) =>
                  updateService(selected, "source", e.target.value)
                }
              />
            </Field>
            {[
              ["tracking_verified", "Tracking verified"],
              ["eligible", "Service eligible for this product and route"],
              [
                "zero_price_verified",
                "Zero-dollar freight specifically verified",
              ],
            ].map(([key, text]) => (
              <label key={key} className="check">
                <input
                  type="checkbox"
                  checked={Boolean(
                    config.service_reviews.find(
                      (r) =>
                        r.quote_id === selected.quote_id &&
                        r.method_id === selected.method_id,
                    )?.[key as "tracking_verified"],
                  )}
                  onChange={(e) =>
                    updateService(selected, key, e.target.checked)
                  }
                />
                {text}
              </label>
            ))}
          </>
        ) : (
          <p>Select an exact freight quote and method first.</p>
        )}
      </details>
      <details className="review-details">
        <summary>Product safety and IP evidence</summary>
        <Field name="Review evidence source">
          <input
            value={config.product_review?.source || ""}
            onChange={(e) => updateProductReview("source", e.target.value)}
          />
        </Field>
        {[
          ["safety_reviewed", "Safety reviewed"],
          ["ip_clear", "Brand and IP clear"],
          ["food_contact_documents", "Food-contact documentation reviewed"],
          [
            "regulatory_documents",
            "Required regulatory documentation reviewed",
          ],
        ].map(([key, text]) => (
          <label className="check" key={key}>
            <input
              type="checkbox"
              checked={Boolean(
                config.product_review?.[key as "safety_reviewed"],
              )}
              onChange={(e) => updateProductReview(key, e.target.checked)}
            />
            {text}
          </label>
        ))}
      </details>
      <details className="review-details">
        <summary>Advanced assumptions · full engine configuration</summary>
        <p className="muted">
          Load current values, edit JSON, then apply. Saving still requires the
          explicit save action below.
        </p>
        <button
          className="secondary"
          onClick={() => setAdvanced(JSON.stringify(config, null, 2))}
        >
          Load current assumptions
        </button>
        <textarea
          aria-label="Advanced pricing JSON"
          className="code-editor"
          rows={15}
          value={advanced}
          onChange={(e) => setAdvanced(e.target.value)}
        />
        <button
          className="secondary"
          onClick={() => {
            try {
              setConfig(JSON.parse(advanced) as Config);
              setDirty(true);
              setError("");
            } catch {
              setError("Invalid JSON");
            }
          }}
        >
          Apply to preview form
        </button>
      </details>
      <Field name="Decision source / reason">
        <input
          value={config.source}
          onChange={(e) => update({ source: e.target.value })}
        />
      </Field>
      {error && (
        <div role="alert" className="error-box">
          {error}
        </div>
      )}
      {message && (
        <p role="status" className="success-message">
          {message}
        </p>
      )}
      <div className="actions">
        <button
          className="secondary"
          disabled={busy}
          onClick={() => calculate(false)}
        >
          <Calculator size={16} />
          {busy ? "Calculating…" : "Recalculate preview"}
        </button>
        <button
          className="primary"
          disabled={busy || config.source.length < 3}
          onClick={() => calculate(true)}
        >
          <Save size={16} />
          Save pricing decision
        </button>
        {view.saved && (
          <span className="muted">
            Last decision: {label(view.saved.decision)}
          </span>
        )}
      </div>
    </div>
  );

  function updateService(row: PriceRow, key: string, value: string | boolean) {
    if (!config || !row.quote_id || !row.method_id || !row.method) return;
    const existing = config.service_reviews.find(
      (r) => r.quote_id === row.quote_id && r.method_id === row.method_id,
    );
    const item = {
      quote_id: row.quote_id,
      method_id: row.method_id,
      method: row.method,
      origin: row.origin,
      destination: row.country,
      source: "",
      tracking_verified: false,
      eligible: false,
      zero_price_verified: false,
      ...existing,
      [key]: value,
    };
    update({
      service_reviews: [
        ...config.service_reviews.filter(
          (r) => r.quote_id !== row.quote_id || r.method_id !== row.method_id,
        ),
        item,
      ],
    });
  }
  function updateProductReview(key: string, value: string | boolean) {
    if (!config) return;
    update({
      product_review: {
        source: "",
        safety_reviewed: false,
        ip_clear: false,
        food_contact_documents: false,
        regulatory_documents: false,
        ...config.product_review,
        [key]: value,
      },
    });
  }
}

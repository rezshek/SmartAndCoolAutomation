"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ArrowLeft, ExternalLink, X, ShieldCheck, Check } from "lucide-react";
import {
  api,
  channels,
  label,
  money,
  type Category,
  type Detail,
  type Profile,
  type Review,
  type Settings,
  type Mapping,
} from "@/lib/api";
import { Badge, Field, Notice, ProductImage } from "./ui";
import { PricingPanel } from "./pricing-panel";
import { ContentPanel } from "./content-panel";

export function ProductWorkspace({
  id,
  initialSection,
  settings,
  onClose,
}: {
  id: string;
  initialSection: string;
  settings: Settings | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [profile, setProfile] = useState<Profile>("woo_us");
  const [section, setSection] = useState(initialSection);
  const [variant, setVariant] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const load = useCallback(async () => {
    const [d, r] = await Promise.all([
      api<Detail>(`products/${id}`),
      api<Review>(`products/${id}/${profile}/review`),
    ]);
    setDetail(d);
    setReview(r);
    setVariant((v) => v || d.variants.find((v) => v.active)?.cj_id || "");
  }, [id, profile]);
  useEffect(() => {
    let active = true;
    void Promise.resolve()
      .then(load)
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [load]);
  useEffect(() => {
    closeRef.current?.focus();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = before;
    };
  }, []);
  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <div
        className="workspace"
        role="dialog"
        aria-modal="true"
        aria-label="Product review"
        ref={root}
        onKeyDown={(e) => {
          if (e.key === "Escape" && !busy) onClose();
          if (e.key === "Tab") {
            const focusable = Array.from(
              root.current?.querySelectorAll<HTMLElement>(
                "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
              ) || [],
            ).filter((el) => el.offsetParent !== null);
            const first = focusable[0],
              last = focusable.at(-1);
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <header className="workspace-header">
          <button
            className="text-button"
            ref={closeRef}
            onClick={onClose}
            disabled={busy}
          >
            <ArrowLeft size={17} />
            Back to catalog
          </button>
          <span className="muted">Product review</span>
          <button
            className="icon-button"
            aria-label="Close product"
            onClick={onClose}
            disabled={busy}
          >
            <X size={21} />
          </button>
        </header>
        {error && (
          <div role="alert" className="error-box">
            {error}
          </div>
        )}
        {!detail || !review ? (
          <div className="empty">Loading product details…</div>
        ) : (
          <>
            <div className="workspace-title">
              <div>
                <div className="eyebrow">
                  {detail.product.category_name || "CATEGORY MISSING"}
                </div>
                <h2>{detail.product.title}</h2>
                <p className="cj-id">CJ · {id}</p>
              </div>
              <Badge value={review.state} />
            </div>
            <div
              className="channel-tabs"
              role="group"
              aria-label="Sales channel"
            >
              {Object.entries(channels).map(([key, name]) => (
                <button
                  key={key}
                  className={profile === key ? "selected" : ""}
                  onClick={() => {
                    if (profile === key) return;
                    setProfile(key as Profile);
                    setReview(null);
                  }}
                >
                  {name}
                  <small>{key === "amazon_ca" ? "CAD" : "USD"}</small>
                </button>
              ))}
            </div>
            <div className="readiness-strip">
              {Object.entries(review.indicators).map(([k, v]) => (
                <div key={k}>
                  <small>{label(k)}</small>
                  <Badge value={v} />
                </div>
              ))}
            </div>
            <Tabs.Root value={section} onValueChange={setSection}>
              <Tabs.List
                className="section-tabs"
                aria-label="Product review sections"
              >
                {[
                  ["overview", "Product & variants"],
                  ["pricing", "Pricing review"],
                  ["category", "Category mapping"],
                  ["content", "Listing content"],
                  ["approval", "Approvals & history"],
                ].map(([key, text]) => (
                  <Tabs.Trigger key={key} value={key}>
                    {text}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
              <Tabs.Content value="overview">
                <div className="overview-grid">
                  <div>
                    <div className="detail-main-image">
                      <ProductImage
                        src={detail.product.images[0]}
                        alt={detail.product.title}
                      />
                    </div>
                    <div className="image-gallery">
                      {detail.product.images.map((url, i) => (
                        <a
                          key={url}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open source image ${i + 1}`}
                        >
                          <ProductImage
                            src={url}
                            alt={`${detail.product.title}, source ${i + 1}`}
                          />
                        </a>
                      ))}
                    </div>
                    <small className="muted">
                      Source images · commercial-use rights need review
                    </small>
                  </div>
                  <div>
                    <h3>Supplier information</h3>
                    <dl className="facts-list">
                      <div>
                        <dt>CJ product ID</dt>
                        <dd>{id}</dd>
                      </div>
                      <div>
                        <dt>Supplier SKU</dt>
                        <dd>{detail.product.sku || "Not supplied"}</dd>
                      </div>
                      <div>
                        <dt>CJ category</dt>
                        <dd>
                          {detail.product.category_name || "Not supplied"}
                        </dd>
                      </div>
                      <div>
                        <dt>Supplier cost from</dt>
                        <dd>{money(detail.product.supplier_cost)} USD</dd>
                      </div>
                      <div>
                        <dt>Last imported</dt>
                        <dd>
                          {detail.product.synced_at
                            ? new Date(
                                detail.product.synced_at,
                              ).toLocaleString()
                            : "Unknown"}
                        </dd>
                      </div>
                    </dl>
                    <h3>Original supplier description</h3>
                    <p className="source-description">
                      {detail.product.description || "No description supplied."}
                    </p>
                    <details>
                      <summary>Supplier attributes</summary>
                      <dl className="facts-list">
                        {Object.entries(detail.product.attributes || {}).map(
                          ([k, v]) => (
                            <div key={k}>
                              <dt>{k}</dt>
                              <dd>
                                {typeof v === "string" ? v : JSON.stringify(v)}
                              </dd>
                            </div>
                          ),
                        )}
                      </dl>
                    </details>
                    {detail.product.exclusion_reasons.length > 0 && (
                      <Notice>
                        <strong>Eligibility needs attention</strong>
                        <ul>
                          {detail.product.exclusion_reasons.map((r) => (
                            <li key={r}>{label(r)}</li>
                          ))}
                        </ul>
                      </Notice>
                    )}
                  </div>
                </div>
                <h3 className="section-heading">
                  Variants{" "}
                  <span className="muted">({detail.variants.length})</span>
                </h3>
                <div className="variant-list">
                  {detail.variants.map((v) => (
                    <details key={v.cj_id}>
                      <summary>
                        <span>
                          {v.title ||
                            Object.values(v.attributes).join(" · ") ||
                            v.sku ||
                            v.cj_id}
                        </span>
                        <strong>{money(v.supplier_price, v.currency)}</strong>
                        <Badge
                          value={v.active ? v.eligibility[0] : "INACTIVE"}
                        />
                      </summary>
                      <div className="variant-details">
                        <div>
                          <p className="cj-id">{v.cj_id}</p>
                          <p>{v.sku}</p>
                          <dl className="facts-list">
                            {Object.entries(v.attributes).map(([k, val]) => (
                              <div key={k}>
                                <dt>{k}</dt>
                                <dd>{JSON.stringify(val)}</dd>
                              </div>
                            ))}
                            <div>
                              <dt>Weight / dimensions</dt>
                              <dd>
                                {v.weight_g ?? "?"} g · {v.length_mm ?? "?"} ×{" "}
                                {v.width_mm ?? "?"} × {v.height_mm ?? "?"} mm
                              </dd>
                            </div>
                          </dl>
                          {v.eligibility[1].map((r) => (
                            <p key={r} className="warning-text">
                              {label(r)}
                            </p>
                          ))}
                        </div>
                        <div>
                          <h4>Inventory observations</h4>
                          {v.image_url && (
                            <div className="variant-image">
                              <ProductImage
                                src={v.image_url}
                                alt={v.title || v.sku}
                              />
                            </div>
                          )}
                          {v.inventory.length ? (
                            v.inventory.map((s, i) => (
                              <div className="inventory-row" key={i}>
                                <strong>{s.country || "Unknown origin"}</strong>
                                <span>
                                  {s.warehouse_id
                                    ? `Warehouse ${s.warehouse_id}`
                                    : "Country total"}
                                </span>
                                <span>
                                  Quantity {s.quantity ?? "unknown"} · CJ{" "}
                                  {s.cj_quantity ?? "?"} · Factory{" "}
                                  {s.factory_quantity ?? "?"}
                                </span>
                                <small>
                                  {new Date(s.observed_at).toLocaleString()}
                                </small>
                              </div>
                            ))
                          ) : (
                            <p>No inventory observation available.</p>
                          )}
                          <h4 className="section-heading">
                            Destination freight
                          </h4>
                          {v.shipping.length ? (
                            v.shipping.map((route) => (
                              <div
                                className="inventory-row"
                                key={route.quote_id}
                              >
                                <strong>
                                  {route.origin} → {route.destination}{" "}
                                  {route.postal_code}
                                </strong>
                                <span>
                                  {route.method_count} observed methods ·
                                  quantity {route.quantity}
                                </span>
                                <Badge value={route.status} />
                                <small>
                                  Expires{" "}
                                  {new Date(route.expires_at).toLocaleString()}{" "}
                                  · Sample route only
                                </small>
                              </div>
                            ))
                          ) : (
                            <p className="muted">
                              US / Canada freight has not been quoted for this
                              variant.
                            </p>
                          )}
                          <small className="muted">
                            Country totals and warehouse rows are separate; do
                            not add them together.
                          </small>
                        </div>
                      </div>
                    </details>
                  ))}
                </div>
              </Tabs.Content>
              <Tabs.Content value="pricing">
                <PricingPanel
                  key={`${profile}-${variant}`}
                  id={id}
                  profile={profile}
                  detail={detail}
                  variant={variant}
                  onVariant={setVariant}
                  onSaved={load}
                />
              </Tabs.Content>
              <Tabs.Content value="category">
                <CategoryPanel
                  key={`${profile}-${review.category?.source || ""}`}
                  id={id}
                  profile={profile}
                  detail={detail}
                  mapping={review.category}
                  settings={settings}
                  busy={busy}
                  run={run}
                />
              </Tabs.Content>
              <Tabs.Content value="content">
                <ContentPanel
                  key={`${profile}-${review.drafts[0]?.version || 0}`}
                  id={id}
                  profile={profile}
                  detail={detail}
                  review={review}
                  settings={settings}
                  busy={busy}
                  run={run}
                />
              </Tabs.Content>
              <Tabs.Content value="approval">
                <ApprovalPanel
                  id={id}
                  profile={profile}
                  review={review}
                  busy={busy}
                  run={run}
                />
              </Tabs.Content>
            </Tabs.Root>
          </>
        )}
      </div>
    </div>
  );
}

type Run = (fn: () => Promise<unknown>) => Promise<void>;

function CategoryPanel({
  id,
  profile,
  detail,
  mapping,
  settings,
  busy,
  run,
}: {
  id: string;
  profile: Profile;
  detail: Detail;
  mapping: Mapping | null;
  settings: Settings | null;
  busy: boolean;
  run: Run;
}) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadError, setLoadError] = useState("");
  const [selected, setSelected] = useState(String(mapping?.category_id || ""));
  const [suggestion, setSuggestion] = useState(mapping?.suggestion || "");
  const [source, setSource] = useState(mapping?.source || "");
  const [path, setPath] = useState(mapping?.listing_path || "new_catalog");
  const [asin, setAsin] = useState(mapping?.asin || "");
  const [gtin, setGtin] = useState(mapping?.gtin || "");
  const [exemption, setExemption] = useState(
    mapping?.gtin_exemption_source || "",
  );
  const [brand, setBrand] = useState(mapping?.brand_review_source || "");
  const [required, setRequired] = useState(
    (mapping?.required_attributes || []).join("\n"),
  );
  const [attributes, setAttributes] = useState(
    JSON.stringify(mapping?.attributes || {}, null, 2),
  );
  useEffect(() => {
    api<Category[]>("categories/woo")
      .then(setCategories)
      .catch((e) => setLoadError(e.message));
  }, []);
  const terms = detail.product.category_name
    .toLowerCase()
    .split(/\W+/)
    .filter((w) => w.length > 3);
  const matches = categories
    .map((c) => ({
      ...c,
      score: terms.filter((t) => c.name.toLowerCase().includes(t)).length,
    }))
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  const woo = profile === "woo_us";
  const save = (approved: boolean) =>
    run(() =>
      api(`products/${id}/${profile}/category`, "PUT", {
        source,
        category_id: woo && selected ? Number(selected) : null,
        suggestion,
        approved,
        listing_path: path,
        asin: asin || null,
        gtin: gtin || null,
        gtin_exemption_source: exemption || null,
        brand_review_source: brand || null,
        required_attributes: required
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        attributes: JSON.parse(attributes),
      }),
    );
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h3>
            {woo
              ? "Map to your WooCommerce store"
              : "Prepare an Amazon product type"}
          </h3>
          <p>
            CJ category:{" "}
            <strong>{detail.product.category_name || "Unknown"}</strong>
          </p>
        </div>
        {mapping?.status && <Badge value={mapping.status} />}
      </div>
      {woo ? (
        <>
          <Notice>
            Choose an existing store category. Missing categories can be
            proposed here for later creation.
          </Notice>
          <div className="actions">
            <button
              className="secondary"
              disabled={busy || !settings?.woo_read_enabled}
              onClick={() =>
                run(async () => {
                  await api("categories/woo/refresh?live=true", "POST");
                  setCategories(await api<Category[]>("categories/woo"));
                })
              }
            >
              Retrieve store categories · read only
            </button>
            <small className="muted">
              {categories.length} cached categories
              {categories[0]
                ? ` · ${new Date(categories[0].retrieved_at).toLocaleString()}`
                : ""}
            </small>
          </div>
          {!settings?.woo_read_enabled && (
            <p className="muted">
              Enable LIVE_CHECKS_ENABLED server-side to retrieve categories
              using the existing read-only credentials.
            </p>
          )}
          {loadError && <p role="alert">{loadError}</p>}
          {matches.length > 0 && (
            <div className="suggestions">
              <small>Suggested name matches · manual review required</small>
              {matches.map((c) => (
                <button
                  className="secondary"
                  key={c.id}
                  onClick={() => setSelected(String(c.id))}
                >
                  {c.name} · #{c.id}
                </button>
              ))}
            </div>
          )}
          <Field name="Existing WooCommerce category">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">No mapping selected</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · #{c.id}
                </option>
              ))}
            </select>
          </Field>
          <Field name="Propose a missing category">
            <input
              value={suggestion}
              onChange={(e) => setSuggestion(e.target.value)}
              placeholder="Category to consider creating in a later ticket"
            />
          </Field>
        </>
      ) : (
        <>
          <Notice>
            Individual seller plan: account-specific category validation is
            unavailable. Every Amazon mapping stays provisional, and content
            approval remains blocked until category requirements can be
            validated.
          </Notice>
          <div className="form-grid">
            <Field name="Suggested Amazon product type">
              <input
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder="Enter a manually researched product type"
              />
            </Field>
            <Field name="Listing approach">
              <select value={path} onChange={(e) => setPath(e.target.value)}>
                <option value="new_catalog">
                  Potential new catalog listing
                </option>
                <option value="existing_asin">Exact existing-ASIN match</option>
              </select>
            </Field>
            <Field name="Exact matched ASIN">
              <input
                value={asin}
                onChange={(e) => setAsin(e.target.value.toUpperCase())}
                placeholder="10-character ASIN, if verified"
              />
            </Field>
            <Field name="GTIN">
              <input
                value={gtin}
                onChange={(e) => setGtin(e.target.value)}
                placeholder="Verified identifier, if available"
              />
            </Field>
            <Field name="GTIN exemption evidence">
              <input
                value={exemption}
                onChange={(e) => setExemption(e.target.value)}
              />
            </Field>
            <Field name="Brand/restriction review evidence">
              <input value={brand} onChange={(e) => setBrand(e.target.value)} />
            </Field>
            <Field name="Required attributes · one per line">
              <textarea
                value={required}
                onChange={(e) => setRequired(e.target.value)}
                rows={4}
              />
            </Field>
            <Field name="Verified attribute values · JSON">
              <textarea
                value={attributes}
                onChange={(e) => setAttributes(e.target.value)}
                rows={4}
              />
            </Field>
          </div>
          <p className="muted">
            Required-attribute lists are manually sourced and may be incomplete.
            New listings need a valid GTIN or an applicable brand/category
            exemption. Existing-ASIN offers need an exact product match.
            Suggestions confer no listing permission.
          </p>
        </>
      )}
      <Field name="Review source / reason">
        <input
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="Reference and reason for this mapping"
        />
      </Field>
      <div className="actions">
        <button
          className="secondary"
          disabled={busy || source.length < 3}
          onClick={() => save(false)}
        >
          Save {woo ? "mapping draft" : "provisional suggestion"}
        </button>
        {woo && (
          <button
            className="primary"
            disabled={busy || !selected || source.length < 3}
            onClick={() => save(true)}
          >
            <Check size={16} />
            Approve category mapping
          </button>
        )}
      </div>
      {mapping?.blockers && (
        <ul className="blocker-list">
          {mapping.blockers.map((b) => (
            <li key={b}>{label(b)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ApprovalPanel({
  id,
  profile,
  review,
  busy,
  run,
}: {
  id: string;
  profile: Profile;
  review: Review;
  busy: boolean;
  run: Run;
}) {
  const [source, setSource] = useState("");
  const [facts, setFacts] = useState(false);
  const [images, setImages] = useState(false);
  const draft = review.drafts[0];
  const transition = (state: string) =>
    run(() =>
      api(`products/${id}/${profile}/transition`, "POST", {
        state,
        source,
        version: draft?.version || null,
        facts_checked: facts,
        images_rights_reviewed: images,
      }),
    );
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h3>Content approval</h3>
          <p>
            Approve the current content version independently of its commercial
            readiness.
          </p>
        </div>
        <Badge value={review.state} />
      </div>
      <div className="workflow">
        {["IMPORTED", "REVIEW_REQUIRED", "DRAFT_READY", "CONTENT_APPROVED"].map(
          (state, i) => (
            <span
              key={state}
              className={review.state === state ? "current" : ""}
            >
              {i + 1}. {label(state)}
            </span>
          ),
        )}
      </div>
      <Notice>
        Publishing stays disabled. Approved copy does not override shipping,
        pricing, eligibility, category or image requirements.
      </Notice>
      <Field name="Decision reference / reason">
        <input value={source} onChange={(e) => setSource(e.target.value)} />
      </Field>
      <label className="check">
        <input
          type="checkbox"
          checked={facts}
          onChange={(e) => setFacts(e.target.checked)}
        />
        I checked this version against verified supplier facts.
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={images}
          onChange={(e) => setImages(e.target.checked)}
        />
        I reviewed image-use rights and channel image requirements.
      </label>
      <div className="actions">
        {review.state === "IMPORTED" && (
          <button
            className="primary"
            disabled={busy || source.length < 3}
            onClick={() => transition("REVIEW_REQUIRED")}
          >
            Start review
          </button>
        )}
        {review.state === "DRAFT_READY" && (
          <button
            className="primary"
            disabled={busy || source.length < 3 || !facts || !images}
            onClick={() => transition("CONTENT_APPROVED")}
          >
            <ShieldCheck size={17} />
            Approve content v{draft?.version}
          </button>
        )}
        {["DRAFT_READY", "CONTENT_APPROVED"].includes(review.state) && (
          <button
            className="secondary"
            disabled={busy || source.length < 3}
            onClick={() => transition("REVIEW_REQUIRED")}
          >
            Return to review
          </button>
        )}
      </div>
      {review.state === "REVIEW_REQUIRED" && draft && (
        <button
          className="secondary"
          disabled={busy || source.length < 3}
          onClick={() => transition("DRAFT_READY")}
        >
          Mark current draft ready
        </button>
      )}
      <h3 className="section-heading">Requirements before publication</h3>
      <ul className="blocker-list">
        {review.blockers.map((b) => (
          <li key={b}>{label(b)}</li>
        ))}
      </ul>
      <h3 className="section-heading">Decision history</h3>
      <div className="audit-list">
        {review.audit.length ? (
          review.audit.map((e) => (
            <details key={e.id}>
              <summary>
                <span>
                  {label(e.kind)} · {e.profile}
                </span>
                <small>
                  {new Date(e.created_at).toLocaleString()} · {e.actor}
                </small>
              </summary>
              <pre>{JSON.stringify(e.payload, null, 2)}</pre>
            </details>
          ))
        ) : (
          <p className="muted">No review decisions saved yet.</p>
        )}
      </div>
      <a
        className="reference-link"
        href="https://sellercentral.amazon.com/help/hub/reference/external/201911450"
        target="_blank"
        rel="noreferrer"
      >
        Amazon content guidance <ExternalLink size={13} />
      </a>
    </div>
  );
}

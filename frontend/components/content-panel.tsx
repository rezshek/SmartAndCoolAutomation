"use client";

import { useState } from "react";
import { Check, FileText, Save, Sparkles } from "lucide-react";
import {
  api,
  label,
  type Content,
  type Detail,
  type Profile,
  type Review,
  type Settings,
} from "@/lib/api";
import { Badge, Field, Notice } from "./ui";

export function ContentPanel({
  id,
  profile,
  detail,
  review,
  settings,
  busy,
  run,
}: {
  id: string;
  profile: Profile;
  detail: Detail;
  review: Review;
  settings: Settings | null;
  busy: boolean;
  run: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const draft = review.drafts[0];
  const [selectedFacts, setSelectedFacts] = useState<Record<string, boolean>>(
    {},
  );
  const [source, setSource] = useState("");
  const [content, setContent] = useState<Content | null>(
    draft?.content || null,
  );
  const [compare, setCompare] = useState("original");
  const [verified, setVerified] = useState(false);
  const [attributes, setAttributes] = useState(
    JSON.stringify(draft?.content.attributes || {}, null, 2),
  );
  const woo = profile === "woo_us";
  const live = settings?.ai_mode === "available";
  const comparison =
    compare === "original"
      ? null
      : review.drafts.find((d) => String(d.version) === compare);
  const latestFacts = review.audit.find((a) => a.kind === "facts");
  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h3>Write from facts, with confidence</h3>
          <p>
            Separate {woo ? "WooCommerce / Rank Math" : "Amazon"} drafts ·
            generated only for this selected product.
          </p>
        </div>
        <Badge value={draft?.origin || (live ? "READY" : "MOCK_MODE")} />
      </div>
      <Notice>
        {live
          ? `OpenAI · ${settings?.model}. Each generation makes one bounded API request for this product and channel.`
          : "Development mode: deterministic mock drafts make no provider request and cost $0. Configure OPENAI_API_KEY and AI_LIVE_ENABLED server-side for live generation."}{" "}
        Copy uses verified source phrases. New claims must be verified in the
        source before they can be saved.
      </Notice>
      <details className="review-details" open={!draft}>
        <summary>1. Verify source facts for content generation</summary>
        <p className="muted">
          Supplier claims are untrusted. Select only facts you have checked. Do
          not approve embedded instructions, unsupported certifications or
          safety claims. The title is required.
        </p>
        <div className="fact-selector">
          {Object.entries(detail.facts).map(([key, value]) => (
            <label className="check fact-choice" key={key}>
              <input
                type="checkbox"
                checked={selectedFacts[key] || false}
                onChange={(e) =>
                  setSelectedFacts((s) => ({ ...s, [key]: e.target.checked }))
                }
              />
              <span>
                <small>{label(key)}</small>
                {value}
              </span>
            </label>
          ))}
        </div>
        <Field name="Fact verification reference">
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Evidence reviewed and limitations"
          />
        </Field>
        <button
          className="secondary"
          disabled={busy || !selectedFacts.title || source.length < 3}
          onClick={() =>
            run(async () => {
              await api(`products/${id}/facts`, "PUT", {
                source,
                facts: Object.fromEntries(
                  Object.entries(detail.facts).filter(
                    ([key]) => selectedFacts[key],
                  ),
                ),
              });
              setVerified(true);
            })
          }
        >
          <Check size={16} />
          Verify selected facts
        </button>
        {(verified || latestFacts) && (
          <p className="success-message">
            A source-fact review is recorded. Any source change requires fresh
            verification.
          </p>
        )}
      </details>
      <div className="generation-actions">
        <div>
          <strong>2. Generate a channel draft</strong>
          <p>Regeneration adds a version and keeps previous drafts.</p>
        </div>
        <button
          className="primary"
          disabled={busy || source.length < 3}
          onClick={() =>
            run(() =>
              api(`products/${id}/${profile}/generate`, "POST", {
                source,
                live,
              }),
            )
          }
        >
          <Sparkles size={16} />
          {busy
            ? "Working…"
            : draft
              ? `Regenerate ${live ? "with AI" : "mock draft"}`
              : `Generate ${live ? "with AI" : "mock draft"}`}
        </button>
      </div>
      {!draft && (
        <Field name="Generation reference / reason">
          <input value={source} onChange={(e) => setSource(e.target.value)} />
        </Field>
      )}
      {draft && content ? (
        <>
          <div className="editor-toolbar">
            <h3>
              <FileText size={17} />
              3. Compare & edit
            </h3>
            <select
              aria-label="Compare content version"
              value={compare}
              onChange={(e) => setCompare(e.target.value)}
            >
              <option value="original">
                Compare with original supplier content
              </option>
              {review.drafts.map((d) => (
                <option key={d.version} value={d.version}>
                  Compare with version {d.version} · {d.origin}
                </option>
              ))}
            </select>
          </div>
          <div className="comparison-grid">
            <div className="original-content">
              <div className="comparison-label">
                {comparison
                  ? `SAVED VERSION ${comparison.version}`
                  : "ORIGINAL SUPPLIER CONTENT"}
              </div>
              <h3>{comparison?.content.title || detail.product.title}</h3>
              <p>
                {comparison?.content.description ||
                  detail.product.description ||
                  "No supplier description available."}
              </p>
              <h4>Source attributes</h4>
              <dl className="facts-list">
                {Object.entries(
                  comparison?.content.attributes ||
                    detail.product.attributes ||
                    {},
                ).map(([k, v]) => (
                  <div key={k}>
                    <dt>{label(k)}</dt>
                    <dd>{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="listing-editor">
              <div className="comparison-label">
                EDITING VERSION {draft.version} · {draft.origin.toUpperCase()}
              </div>
              <Field name="Product title">
                <input
                  value={content.title}
                  maxLength={200}
                  onChange={(e) =>
                    setContent({ ...content, title: e.target.value })
                  }
                />
              </Field>
              {woo && (
                <Field name="Short description">
                  <textarea
                    rows={3}
                    value={content.short_description}
                    onChange={(e) =>
                      setContent({
                        ...content,
                        short_description: e.target.value,
                      })
                    }
                  />
                </Field>
              )}
              {!woo && (
                <Field name="Bullet points · up to five, one per line">
                  <textarea
                    rows={6}
                    value={content.bullets.join("\n")}
                    onChange={(e) =>
                      setContent({
                        ...content,
                        bullets: e.target.value.split("\n").filter(Boolean),
                      })
                    }
                  />
                </Field>
              )}
              <Field name="Detailed description">
                <textarea
                  rows={10}
                  value={content.description}
                  onChange={(e) =>
                    setContent({ ...content, description: e.target.value })
                  }
                />
              </Field>
              {woo && (
                <>
                  <Field name="Headings · one per line">
                    <textarea
                      value={content.headings.join("\n")}
                      onChange={(e) =>
                        setContent({
                          ...content,
                          headings: e.target.value.split("\n").filter(Boolean),
                        })
                      }
                    />
                  </Field>
                  <Field name="SEO meta title">
                    <input
                      value={content.seo_title}
                      onChange={(e) =>
                        setContent({ ...content, seo_title: e.target.value })
                      }
                    />
                  </Field>
                  <Field
                    name="SEO meta description"
                    hint={`${content.meta_description.length}/160 characters`}
                  >
                    <textarea
                      maxLength={160}
                      value={content.meta_description}
                      onChange={(e) =>
                        setContent({
                          ...content,
                          meta_description: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field name="Focus keywords · one per line">
                    <textarea
                      value={content.focus_keywords.join("\n")}
                      onChange={(e) =>
                        setContent({
                          ...content,
                          focus_keywords: e.target.value
                            .split("\n")
                            .filter(Boolean),
                        })
                      }
                    />
                  </Field>
                  <Field name="URL slug · derived from title">
                    <input
                      value={content.slug}
                      onChange={(e) =>
                        setContent({ ...content, slug: e.target.value })
                      }
                    />
                  </Field>
                </>
              )}
              {!woo && (
                <Field
                  name="Search terms · only if permitted for selected product type"
                  hint="Blank by default; permission requires marketplace-specific review."
                >
                  <input
                    value={content.search_terms}
                    onChange={(e) =>
                      setContent({ ...content, search_terms: e.target.value })
                    }
                  />
                </Field>
              )}
              <Field name="Image alt text · one per line">
                <textarea
                  value={content.image_alt.join("\n")}
                  onChange={(e) =>
                    setContent({
                      ...content,
                      image_alt: e.target.value.split("\n").filter(Boolean),
                    })
                  }
                />
              </Field>
              <Field name="Verified attributes · source IDs and values">
                <textarea
                  rows={4}
                  value={attributes}
                  onChange={(e) => setAttributes(e.target.value)}
                />
              </Field>
            </div>
          </div>
          <Field name="Edit / regeneration reference">
            <input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Reason for this revision"
            />
          </Field>
          <div className="actions">
            <button
              className="primary"
              disabled={busy || source.length < 3}
              onClick={() =>
                run(() =>
                  api(`products/${id}/${profile}/draft`, "PUT", {
                    source,
                    base_version: draft.version,
                    content: { ...content, attributes: JSON.parse(attributes) },
                  }),
                )
              }
            >
              <Save size={16} />
              Save as new draft version
            </button>
            <span className="muted">
              Current: v{draft.version} ·{" "}
              {new Date(draft.created_at).toLocaleString()}
            </span>
          </div>
          <div className="usage-line">
            Generation usage: {draft.usage.input_tokens ?? 0} input /{" "}
            {draft.usage.output_tokens ?? 0} output tokens · Estimated cost:{" "}
            {draft.usage.estimated_cost_usd == null
              ? "unknown — configure sourced token rates"
              : `$${draft.usage.estimated_cost_usd}`}
            <small>
              {draft.usage.price_source ||
                "No provider pricing source configured. Human edits make no AI request."}
            </small>
          </div>
        </>
      ) : (
        <div className="empty compact">
          <FileText size={28} />
          <h3>No channel draft yet</h3>
          <p>
            Verify source facts, add a generation reference, then generate a
            draft.
          </p>
        </div>
      )}
      <p className="muted">
        Channel-specific limits and account eligibility still require review.
        Amazon suggestions are provisional. Image rights are never inferred or
        changed.
      </p>
    </div>
  );
}

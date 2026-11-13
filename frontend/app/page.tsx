"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Boxes,
  Search,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  LayoutGrid,
  Tags,
  Calculator,
  FileCheck2,
  SlidersHorizontal,
} from "lucide-react";
import { api, label, money, type Product, type Settings } from "@/lib/api";
import { Badge, Field, Notice, ProductImage } from "@/components/ui";
import { ProductWorkspace } from "@/components/product-workspace";

type Catalog = {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  categories: string[];
};
const navigation = [
  { id: "catalog", title: "Product catalog", icon: LayoutGrid },
  { id: "category", title: "Category mapping", icon: Tags },
  { id: "pricing", title: "Pricing review", icon: Calculator },
  { id: "content", title: "Listing content", icon: FileCheck2 },
];

export default function Dashboard() {
  const [data, setData] = useState<Catalog | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [section, setSection] = useState("catalog");
  const [selected, setSelected] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    api<Settings>("settings")
      .then(setSettings)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      const params = new URLSearchParams({
        page: String(page),
        page_size: "12",
        q: query,
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
      });
      api<Catalog>(`products?${params}`)
        .then((d) => {
          if (alive) setData(d);
        })
        .catch((e) => {
          if (alive) setError(e.message);
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    }, 200);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [page, query, filters, refresh]);
  const filter = (key: string, value: string) => {
    setPage(1);
    setFilters((f) => ({ ...f, [key]: value }));
  };
  const title = navigation.find((n) => n.id === section)!.title;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-icon">
            <Boxes size={23} />
          </span>
          <span>
            smart<span className="brand-amp">&</span>cool
            <small>COMMERCE WORKSPACE</small>
          </span>
        </Link>
        <div className="sidebar-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((n) => (
            <button
              key={n.id}
              className={section === n.id ? "nav-item active" : "nav-item"}
              onClick={() => setSection(n.id)}
            >
              <n.icon size={19} />
              {n.title}
              {n.id === "catalog" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={21} />
          <div>
            <strong>Local review workspace</strong>
            <p>
              Publishing is disabled.
              <br />
              Your changes stay in local drafts.
            </p>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            Workspace <span className="crumb">/</span> {title}
          </span>
          <span className="local-pill">
            <span />
            Local environment
          </span>
        </header>
        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">CURATE YOUR NEXT COLLECTION</div>
              <h1>{title}</h1>
              <p>
                {section === "catalog"
                  ? "Discover what’s worth selling. Review every product with confidence."
                  : "Select a product to review its channel requirements and save a decision."}
              </p>
            </div>
            <div className="source-label">
              <span className="source-dot" />
              CJ Dropshipping <small>Imported catalog</small>
            </div>
          </div>
          <div className="review-banner">
            <div className="banner-icon">
              <ShieldCheck size={23} />
            </div>
            <div>
              <strong>Good products start with a careful review.</strong>
              <p>
                Supplier costs are a starting point. Verify shipping, fees and
                product facts before approving.
              </p>
            </div>
            <span className="banner-tag">REVIEW FIRST</span>
          </div>
          {settings?.ai_mode === "mock" && section === "content" && (
            <Notice>
              AI is in development mode. Configure a dedicated server-side API
              key to generate live drafts. Mock drafts are labeled and cannot be
              approved directly.
            </Notice>
          )}
          <div className="catalog-toolbar">
            <div className="catalog-count">
              <h2>Imported products</h2>
              <span>{data?.total ?? "—"}</span>
            </div>
            <span className="muted">One product. All its variants.</span>
          </div>
          <div className="search-row">
            <div className="search-input">
              <Search size={18} />
              <input
                aria-label="Search products"
                placeholder="Search products or CJ ID…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <select
              aria-label="Category filter"
              value={filters.category || ""}
              onChange={(e) => filter("category", e.target.value)}
            >
              <option value="">All categories</option>
              {data?.categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <select
              aria-label="Eligibility filter"
              value={filters.eligibility || ""}
              onChange={(e) => filter("eligibility", e.target.value)}
            >
              <option value="">All review statuses</option>
              <option value="NEEDS_REVIEW">Needs review</option>
              <option value="EXCLUDED">Excluded</option>
              <option value="PASS">Eligible</option>
            </select>
            <button
              className="secondary"
              onClick={() => setFiltersOpen(!filtersOpen)}
              aria-expanded={filtersOpen}
            >
              <SlidersHorizontal size={16} />
              Filters
            </button>
          </div>
          {filtersOpen && (
            <div className="filter-panel form-grid">
              <Field name="Minimum supplier cost (USD)">
                <input
                  type="number"
                  min="0"
                  value={filters.min_cost || ""}
                  onChange={(e) => filter("min_cost", e.target.value)}
                />
              </Field>
              <Field name="Maximum supplier cost (USD)">
                <input
                  type="number"
                  min="0"
                  value={filters.max_cost || ""}
                  onChange={(e) => filter("max_cost", e.target.value)}
                />
              </Field>
              <Field name="Inventory observation">
                <select
                  value={filters.inventory || ""}
                  onChange={(e) => filter("inventory", e.target.value)}
                >
                  <option value="">All inventory</option>
                  <option value="available">Observed available</option>
                  <option value="out">Observed out of stock</option>
                  <option value="unknown">Unknown</option>
                </select>
              </Field>
              <Field name="Shipping origin">
                <select
                  value={filters.origin || ""}
                  onChange={(e) => filter("origin", e.target.value)}
                >
                  <option value="">Any origin</option>
                  <option>US</option>
                  <option>CN</option>
                  <option>CA</option>
                </select>
              </Field>
              <Field name="Missing information">
                <select
                  value={filters.missing || ""}
                  onChange={(e) => filter("missing", e.target.value)}
                >
                  <option value="">Any completeness</option>
                  {["any", "images", "cost", "category", "inventory"].map(
                    (v) => (
                      <option key={v} value={v}>
                        {label(v)}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field name="Saved profitability · Woo US">
                <select
                  value={filters.profitability || ""}
                  onChange={(e) => filter("profitability", e.target.value)}
                >
                  <option value="">Any pricing status</option>
                  {["PASS", "UNPRICEABLE", "NEEDS_REVIEW", "REJECTED"].map(
                    (v) => (
                      <option key={v} value={v}>
                        {label(v)}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <button
                className="text-button"
                onClick={() => {
                  setFilters({});
                  setQuery("");
                  setPage(1);
                }}
              >
                Clear all filters
              </button>
            </div>
          )}
          {error && (
            <div role="alert" className="error-box">
              {error}
              <button
                className="secondary"
                onClick={() => setRefresh((r) => r + 1)}
              >
                Try again
              </button>
            </div>
          )}
          {loading ? (
            <div className="product-grid" aria-label="Loading products">
              {Array.from({ length: 6 }, (_, i) => (
                <div className="skeleton" key={i} />
              ))}
            </div>
          ) : !error && data?.items.length === 0 ? (
            <div className="empty">
              <Search size={30} />
              <h2>No products match these filters</h2>
              <p>Try another search or clear your filters.</p>
              <button
                className="secondary"
                onClick={() => {
                  setFilters({});
                  setQuery("");
                }}
              >
                Clear filters
              </button>
            </div>
          ) : (
            !error && (
              <div className="product-grid">
                {data?.items.map((p) => (
                  <button
                    key={p.cj_id}
                    className="product-card"
                    onClick={() => setSelected(p.cj_id)}
                  >
                    <div className="card-image">
                      <ProductImage src={p.images[0]} alt={p.title} />
                      <div className="card-badge">
                        <Badge value={p.eligibility} />
                      </div>
                      <span className="variant-tag">
                        {p.variant_count} variants
                      </span>
                    </div>
                    <div className="card-body">
                      <div className="category-label">
                        {p.category_name || "Category missing"}
                      </div>
                      <h3>{p.title}</h3>
                      <div className="cj-id">CJ · {p.cj_id}</div>
                      <div className="card-economics">
                        <div>
                          <small>Supplier cost from</small>
                          <strong>
                            {money(p.supplier_cost, p.currency)}{" "}
                            <em>{p.currency}</em>
                          </strong>
                        </div>
                        <span className="card-open">
                          <ArrowUpRight size={20} />
                        </span>
                      </div>
                      <div className="card-footer">
                        <span
                          className={`inventory-dot ${p.inventory === "available" ? "available" : ""}`}
                        />
                        <span>
                          {p.inventory === "available"
                            ? "Stock observed"
                            : label(p.inventory)}
                          {p.origins.length ? ` · ${p.origins.join(", ")}` : ""}
                        </span>
                        <span className="pricing-note">
                          Price review needed
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )
          )}
          <div className="pagination">
            <span>
              {data?.total
                ? `${(page - 1) * 12 + 1}–${Math.min(page * 12, data.total)} of ${data.total} products`
                : "0 products"}{" "}
              · 12 per page
            </span>
            <div>
              <button
                className="secondary"
                aria-label="Previous page"
                disabled={page === 1 || loading}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                Page {page} of {Math.max(1, Math.ceil((data?.total || 0) / 12))}
              </span>
              <button
                className="secondary"
                aria-label="Next page"
                disabled={loading || page * 12 >= (data?.total || 0)}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
          <footer className="page-footer">
            Source images and stock are supplier observations. Commercial use
            and current availability require review.
          </footer>
        </div>
      </main>
      {selected && (
        <ProductWorkspace
          key={selected}
          id={selected}
          initialSection={section === "catalog" ? "overview" : section}
          settings={settings}
          onClose={() => {
            setSelected(null);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </div>
  );
}

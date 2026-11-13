export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method,
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.detail || "The request could not be completed.");
  return data as T;
}
export const label = (s: string) =>
  s
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
export const money = (
  value: string | number | null | undefined,
  currency = "USD",
) =>
  value == null
    ? "Unknown"
    : new Intl.NumberFormat("en-US", { style: "currency", currency }).format(
        Number(value),
      );
export const channels = {
  woo_us: "WooCommerce US",
  amazon_us: "Amazon US",
  amazon_ca: "Amazon Canada",
};
export type Profile = keyof typeof channels;
export type Product = {
  cj_id: string;
  title: string;
  category_name: string;
  images: string[];
  supplier_cost: string | null;
  currency: string;
  variant_count: number;
  eligibility: string;
  exclusion_reasons: string[];
  excluded_variants: string[];
  inventory: string;
  origins: string[];
  inventory_observed_at: string | null;
  missing: string[];
  pricing_readiness: string;
  description?: string;
  attributes?: Record<string, unknown>;
  sku?: string;
  synced_at?: string;
};
export type Inventory = {
  country: string;
  warehouse_id: string | null;
  quantity: number | null;
  cj_quantity: number | null;
  factory_quantity: number | null;
  observed_at: string;
};
export type Variant = {
  shipping: {
    destination: string;
    postal_code: string;
    origin: string;
    warehouse_ids: string[];
    quantity: number;
    expires_at: string;
    quote_id: number;
    method_count: number;
    status: string;
  }[];
  cj_id: string;
  title: string | null;
  sku: string;
  attributes: Record<string, unknown>;
  supplier_price: string | null;
  currency: string;
  active: boolean;
  image_url: string | null;
  weight_g: string | null;
  length_mm: string | null;
  width_mm: string | null;
  height_mm: string | null;
  eligibility: [string, string[]];
  inventory: Inventory[];
};
export type Detail = {
  product: Product;
  variants: Variant[];
  profiles: Profile[];
  facts: Record<string, string>;
  source_digest: string;
};
export type Content = {
  title: string;
  short_description: string;
  description: string;
  headings: string[];
  bullets: string[];
  seo_title: string;
  meta_description: string;
  focus_keywords: string[];
  image_alt: string[];
  slug: string;
  search_terms: string;
  attributes: Record<string, string>;
};
export type Draft = {
  id: number;
  version: number;
  content: Content;
  origin: string;
  created_at: string;
  usage: {
    input_tokens?: number;
    output_tokens?: number;
    estimated_cost_usd?: string | null;
    price_source?: string | null;
  };
};
export type Mapping = {
  category_id?: number | null;
  suggestion?: string;
  status?: string;
  name?: string;
  listing_path?: string;
  asin?: string | null;
  required_attributes?: string[];
  attributes?: Record<string, string>;
  gtin?: string | null;
  gtin_exemption_source?: string | null;
  brand_review_source?: string | null;
  blockers?: string[];
  source?: string;
};
export type Review = {
  state: string;
  category: Mapping | null;
  drafts: Draft[];
  indicators: Record<string, string>;
  blockers: string[];
  audit: {
    id: number;
    kind: string;
    profile: string;
    actor: string;
    created_at: string;
    payload: Record<string, unknown>;
  }[];
};
export type Money = { amount: string; currency: string };
export type Policy = Record<string, string | boolean | Money | null>;
export type Config = {
  variant_id: string;
  policy: Policy;
  fx: null | {
    usd_to_cad: string;
    source: string;
    observed_at: string;
    verified: boolean;
    max_age_hours: number;
  };
  service_reviews: {
    quote_id: number;
    method_id: number;
    method: string;
    destination: string;
    origin: string;
    source: string;
    tracking_verified: boolean;
    eligible: boolean;
    zero_price_verified: boolean;
  }[];
  product_review: null | {
    source: string;
    safety_reviewed: boolean;
    ip_clear: boolean;
    food_contact_documents: boolean;
    regulatory_documents: boolean;
  };
  quote_id: number | null;
  method_id: number | null;
  source: string;
  actor: string;
};
export type PriceRow = Record<
  string,
  string | number | null | boolean | string[]
> & {
  variant_id: string;
  quote_id: number | null;
  method_id: number | null;
  method: string | null;
  status: string;
  pricing_status: string;
  currency: string;
  reasons: string[];
  selling_price: string | null;
  profit: string | null;
  margin: string | null;
  required_price: string | null;
  destination?: string;
  country: string;
  origin: string;
  supplier_cost_original: string | null;
  freight_total_original: string | null;
  postal_code: string;
  warehouse_ids: string[];
};
export type PriceView = {
  config: Config;
  rows: PriceRow[];
  selected: PriceRow | null;
  saved: { decision: string } | null;
};
export type Category = {
  id: number;
  name: string;
  parent: number;
  retrieved_at: string;
};
export type Settings = {
  ai_mode: string;
  model: string;
  woo_read_enabled: boolean;
  publishing_enabled: boolean;
  ai_price_configured: boolean;
};

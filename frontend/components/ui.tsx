import type { ReactNode } from "react";
import { AlertCircle, ImageOff } from "lucide-react";
import { useState } from "react";
import { label } from "@/lib/api";

export function Badge({ value }: { value: string }) {
  const tone = [
    "PASS",
    "APPROVED",
    "VERIFIED",
    "available",
    "CONTENT_APPROVED",
  ].includes(value)
    ? "good"
    : ["EXCLUDED", "REJECTED", "out"].includes(value)
      ? "bad"
      : "neutral";
  return <span className={`badge ${tone}`}>{label(value)}</span>;
}
export function Field({
  name,
  children,
  hint,
}: {
  name: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{name}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="notice">
      <AlertCircle size={17} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
export function ProductImage({
  src,
  alt,
}: {
  src?: string | null;
  alt: string;
}) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  ) : (
    <div className="image-empty">
      <ImageOff size={28} />
      <span>Image unavailable</span>
    </div>
  );
}

import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Product workspace · Smart & Cool",
  description:
    "Review your supplier catalog, pricing and channel content locally.",
  icons: { icon: "/favicon.svg" },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import { Figtree } from "next/font/google";
import "./globals.css";
import type { Metadata } from "next";

const figtree = Figtree({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-figtree",
});

export const metadata: Metadata = {
  title: "DistributorOS Operations Dashboard",
  description: "B2B Operational Operating System for India",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={figtree.className}>
      <body className="antialiased bg-slate-50 text-slate-900 overflow-hidden">
        {children}
      </body>
    </html>
  );
}

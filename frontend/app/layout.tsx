import type { Metadata } from "next";
import "./globals.css";
import { FetchSanitizer } from "@/components/FetchSanitizer";

export const metadata: Metadata = { title: "AI Tools | TotalSoft" };

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ro">
      <body className="min-h-screen bg-white text-slate-800 text-sm">
        <FetchSanitizer />
        {children}
      </body>
    </html>
  );
}

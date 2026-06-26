import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "AI Tools | TotalSoft" };

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ro">
      <body className="min-h-screen bg-white text-slate-800 text-sm">
        {children}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { LangProvider } from "@/lib/i18n";
import { RunProvider } from "@/lib/run-context";

export const metadata: Metadata = {
  title: "Tremor Retail",
  description: "Find hidden profit leakage in a small grocery store, with proof for every finding. English and हिंदी.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+Devanagari:wght@400;500;600;700;800&display=swap"
        />
      </head>
      <body>
        <LangProvider>
          <RunProvider>
            <AppShell>{children}</AppShell>
          </RunProvider>
        </LangProvider>
      </body>
    </html>
  );
}

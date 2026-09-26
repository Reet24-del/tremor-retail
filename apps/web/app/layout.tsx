import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { RunProvider } from "@/lib/run-context";

export const metadata: Metadata = {
  title: "Tremor Retail",
  description: "Find hidden profit leakage in a small grocery store, with proof for every finding.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <RunProvider>
          <AppShell>{children}</AppShell>
        </RunProvider>
      </body>
    </html>
  );
}

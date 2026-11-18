import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import { SessionProvider } from "@/lib/session";

export const metadata: Metadata = {
  title: "ROADGUARD AI — Road Safety Intelligence",
  description:
    "AI-assisted road-safety review and corrective-action tracking prototype. All AI output requires human review.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#070d16] text-slate-200 antialiased">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible, Fraunces, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import "./extra.css";
import { LangProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import { SiteHeader } from "@/components/SiteHeader";

const atkinson = Atkinson_Hyperlegible({ weight: ["400", "700"], subsets: ["latin"], variable: "--font-atkinson", display: "swap" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap", axes: ["opsz"] });
const devanagari = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap" });

export const metadata: Metadata = {
  title: "CareSaathi",
  description: "A voice-first care companion for families. Every instruction, with its source. A care-coordination tool, not medical advice.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f1e6" },
    { media: "(prefers-color-scheme: dark)", color: "#0e1d1c" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} ${fraunces.variable} ${devanagari.variable}`}>
      <body>
        <LangProvider>
          <AuthProvider>
          <a className="skip-link" href="#main">Skip to content</a>
          <SiteHeader />
          <main id="main">{children}</main>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}

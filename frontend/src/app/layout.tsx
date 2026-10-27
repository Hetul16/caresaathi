import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible, Bricolage_Grotesque, JetBrains_Mono, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import "./extra.css";
import "./motion.css";
import { LangProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import { SiteHeader } from "@/components/SiteHeader";
import { Backdrop, ScrollProgress } from "@/components/fx/Backdrop";
import { FxProvider } from "@/components/fx/FxProvider";

const atkinson = Atkinson_Hyperlegible({ weight: ["400", "700"], subsets: ["latin"], variable: "--font-atkinson", display: "swap" });
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", display: "swap", axes: ["opsz", "wdth"] });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
const devanagari = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap" });

export const metadata: Metadata = {
  title: "CareSaathi",
  description: "A voice-first care companion for families. Every instruction, with its source. A care-coordination tool, not medical advice.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0e1a",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} ${bricolage.variable} ${mono.variable} ${devanagari.variable}`}>
      <body>
        <LangProvider>
          <AuthProvider>
            <FxProvider />
            <Backdrop />
            <ScrollProgress />
            <a className="skip-link" href="#main">Skip to content</a>
            <SiteHeader />
            <main id="main">{children}</main>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}

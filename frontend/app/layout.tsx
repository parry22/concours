import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist-sans", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Brief",
  description: "Turn a spreadsheet prediction problem into a protected, Apex-ready competition.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0a0b",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh">
        {/* Shared gradient for icon strokes (.icon-brand). Kept rendered at 0x0: display:none would disable it. */}
        <svg width="0" height="0" className="pointer-events-none absolute" aria-hidden focusable="false">
          <defs>
            <linearGradient id="brand-stroke" gradientUnits="userSpaceOnUse" x1="4" y1="2" x2="20" y2="22">
              <stop offset="0" stopColor="#fbb39c" />
              <stop offset="0.34" stopColor="#f472b6" />
              <stop offset="0.66" stopColor="#c084fc" />
              <stop offset="1" stopColor="#818cf8" />
            </linearGradient>
          </defs>
        </svg>
        {children}
      </body>
    </html>
  );
}

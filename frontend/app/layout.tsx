import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Brief",
  description: "Turn a spreadsheet prediction problem into a protected, Apex-ready competition.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

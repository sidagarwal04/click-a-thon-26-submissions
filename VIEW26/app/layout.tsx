import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://featurelens-atlys-poc.ajayep.chatgpt.site"),
  title: "FeatureLens · Product Intelligence for Atlys",
  description: "Trace every answer and improve every product decision with governed ClickHouse evidence and Langfuse quality feedback.",
  openGraph: {
    title: "FeatureLens · Product Intelligence for Atlys",
    description: "Trace every answer. Improve every decision.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "FeatureLens trace explorer and evaluation workspace" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "FeatureLens · Product Intelligence for Atlys",
    description: "Trace every answer. Improve every decision.",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}

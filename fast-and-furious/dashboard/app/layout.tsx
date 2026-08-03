import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { TokenGate } from "@/components/TokenGate";

/*
  Inter, self-hosted by next/font at build time.

  This reverses an earlier decision in this file, on purpose. The system sans
  stack was the right call while the tool had no identity to carry; it is the
  wrong one now that the surface is meant to be SonyLIV's, because Inter is the
  face sonyliv.com actually renders (measured: Inter-Regular/Medium/Semibold
  across its chrome) and "the closest installed font" is a failure rather than a
  fallback.

  The cost the old comment named is real and bounded: `next build` needs network
  access to fetch the face. That only affects `make web`, which already runs
  `npm ci`; the export is committed, so `make build` still needs no toolchain and
  no network. Three weights, latin subset only.
*/
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "sonyliv-mock",
  description:
    "Session fleet, load simulator and event stepper for the SonyLIV concurrency pipeline.",
};

/*
  The direction contract, emitted into the built markup so it can be audited
  after the fact rather than living only in a source comment the compiler drops.
*/
const CONTRACT = `
IMPECCABLE DIRECTION CONTRACT
THESIS: An operator's console wearing SonyLIV's own cinema-black identity. It
  refuses the SaaS-dashboard default of grey cards on a grey ground.
OWN-WORLD: #000 ground with #141414/#222 surfaces. Inter 400/500/600. ONE signal
  colour, #FFA800, measured off sonyliv.com; white and #AAA carry everything
  else. Radii 4px on controls, 10px on panels. Hierarchy by form, never by
  inventing a second hue.
STORY: An engineer creates a fleet of live sessions, drives them by hand, and
  watches ClickHouse agree or disagree with recorded ground truth.
FIRST VIEWPORT: Black nav rule, a tabular stat row in gold and white, then the
  two-line concurrency chart at full width.
FORM: Brief-pinned to the SonyLIV brand; no concept roll was run.
FINISH: unreviewed and undocumented is unfinished; this build ends with the
  finish review, the verdict, and DESIGN.md
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        {/* React does not render JSX comments into markup, so the contract ships
            inside a hidden node. Greppable in the built output, which is the
            whole point of recording it. */}
        <div
          hidden
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: `<!--${CONTRACT}-->` }}
        />
        <Nav />
        <TokenGate />
        <main className="mx-auto w-full max-w-[80rem] min-w-0 flex-1 px-5 pt-6 pb-16">
          {children}
        </main>
      </body>
    </html>
  );
}

import type {Metadata} from 'next'
import {Archivo, Archivo_Narrow, IBM_Plex_Mono} from 'next/font/google'
import './globals.css'

// Three roles, one pairing strategy, shared by both consoles.
//
//   Archivo Narrow  headlines and KPI figures. Condensed, so a five-digit peak reads as signage
//                   at 38px without pushing the neighbouring tile off the row.
//   Archivo         prose. The same superfamily, so the pairing is a width contrast rather than
//                   two typefaces arguing.
//   IBM Plex Mono   every number, label, timestamp and line of SQL. Tabular figures mean digits
//                   do not shift width on a five-second refresh.
const archivo = Archivo({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-body',
  display: 'swap',
})

const archivoNarrow = Archivo_Narrow({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  variable: '--font-display-face',
  display: 'swap',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'PHOENIX // Foreground Concurrency Console',
  description:
    'Live foreground-only streaming concurrency, session-aware and session-independent, served from ClickHouse.',
  icons: {
    icon: '/click-a-thon.png',
  },
}

export default function RootLayout({children}: { children: React.ReactNode }) {
  return (
    <html lang="en">
    <body className={`${archivo.variable} ${archivoNarrow.variable} ${plexMono.variable}`}>
      {children}
    </body>
    </html>
  )
}

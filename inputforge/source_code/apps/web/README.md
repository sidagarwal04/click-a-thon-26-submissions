This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## HyperDX / ClickStack browser telemetry

The app exports browser traces to HyperDX when both public telemetry variables
are configured. To use the local ClickStack collector started from
`apps/detection-service`, add the following to `apps/web/.env.local` and restart
the development server:

```dotenv
NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
NEXT_PUBLIC_HYPERDX_API_KEY=local
NEXT_PUBLIC_HYPERDX_ENABLE_REPLAY=false
```

`NEXT_PUBLIC_HYPERDX_API_KEY` is an ingestion key and is intentionally visible
to the browser; it must not be an administrative ClickHouse credential. Session
replay is disabled by default and must be explicitly enabled after reviewing
the data-capture policy. Form inputs are masked whenever replay is enabled.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load Inter, a custom Google Font.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

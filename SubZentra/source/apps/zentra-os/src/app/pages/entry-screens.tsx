import type { ReactNode } from 'react';

import { Button } from '@open-zentra/foundation-design-system';

import { PRODUCT_NAME, PRODUCT_TAGLINE } from '../constants/product';
import { ProductMark } from '../shell/product-mark';

/**
 * The full-bleed page used before a workspace exists to show.
 */
const EntryPage = ({
  eyebrow,
  heading,
  children,
  actions,
}: {
  readonly eyebrow: string;
  readonly heading: string;
  readonly children?: ReactNode;
  readonly actions?: ReactNode;
}) => (
  <main className="min-h-screen bg-background px-6 py-8 text-foreground sm:px-12 lg:px-20">
    <div className="flex items-start justify-between gap-4">
      <ProductMark />
      {actions}
    </div>
    <section className="max-w-4xl pt-[clamp(6rem,18vh,13rem)]">
      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
        {eyebrow}
      </p>
      <h1 className="mb-6 mt-4 max-w-3xl font-serif text-[clamp(3rem,8vw,7rem)] font-normal leading-[0.9] tracking-[-0.05em]">
        {heading}
      </h1>
      <div className="max-w-xl text-base leading-relaxed text-foreground-muted sm:text-lg">
        {children}
      </div>
    </section>
  </main>
);

export const SetupRequired = () => (
  <EntryPage eyebrow="Identity setup required" heading="Connect Clerk to enter the observatory.">
    <p>
      Add <code className="font-mono text-primary">VITE_CLERK_PUBLISHABLE_KEY</code>. {PRODUCT_NAME}{' '}
      never assumes a development tenant.
    </p>
  </EntryPage>
);

export const SignedOut = ({ login }: { readonly login: () => Promise<void> }) => (
  <EntryPage eyebrow={PRODUCT_TAGLINE} heading="Trust is the product.">
    <p>Follow every analytical claim from governed metric to human judgment.</p>
    <Button className="mt-8" size="lg" onClick={() => void login()}>
      Enter the observatory
    </Button>
  </EntryPage>
);

export const OrganizationRequired = ({ onSignOut }: { readonly onSignOut: () => void }) => (
  <EntryPage
    eyebrow="Organization required"
    heading="Select a Clerk organization to continue."
    actions={
      <Button intent="ghost" onClick={onSignOut}>
        Sign out
      </Button>
    }
  >
    <p>{PRODUCT_NAME} never falls back to a caller-supplied tenant.</p>
  </EntryPage>
);

export const MembershipUnavailable = ({ detail }: { readonly detail: string | undefined }) => (
  <EntryPage
    eyebrow="Membership unavailable"
    heading={`This organization is not bound to a ${PRODUCT_NAME} tenant.`}
  >
    <p>{detail}</p>
  </EntryPage>
);

/**
 * Held while identity resolves. Announced, because nothing else on the page
 * says what is happening.
 */
export const ResolvingIdentity = ({ message }: { readonly message: string }) => (
  <main
    className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background text-foreground"
    aria-live="polite"
  >
    <ProductMark />
    <span className="h-px w-40 animate-pulse bg-primary" aria-hidden="true" />
    <p className="text-sm text-foreground-muted">{message}</p>
  </main>
);

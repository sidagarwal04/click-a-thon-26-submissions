import { useState, type ReactNode } from 'react';

import { ClerkProvider } from '@clerk/clerk-react';
import { useAuth } from '@open-zentra/foundation-auth';
import { ClerkAuthProvider } from '@open-zentra/foundation-auth/clerk';
import { ClerkAuthzProvider } from '@open-zentra/foundation-authz/clerk';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'motion/react';
import { BrowserRouter } from 'react-router-dom';

interface AppProvidersProps {
  readonly children: ReactNode;
}

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined;

const AuthzBoundary = ({ children }: AppProvidersProps) => {
  const { scope } = useAuth();
  return <ClerkAuthzProvider scope={scope}>{children}</ClerkAuthzProvider>;
};

const ProductProviders = ({ children }: AppProvidersProps) => {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 5_000, retry: 1 } },
      }),
  );
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export const AppProviders = ({ children }: AppProvidersProps) => {
  const product = <ProductProviders>{children}</ProductProviders>;
  if (!clerkPublishableKey) {
    return product;
  }
  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <ClerkAuthProvider>
        <AuthzBoundary>{product}</AuthzBoundary>
      </ClerkAuthProvider>
    </ClerkProvider>
  );
};

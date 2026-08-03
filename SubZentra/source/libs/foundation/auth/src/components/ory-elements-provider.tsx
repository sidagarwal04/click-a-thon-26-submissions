/**
 * Ory Elements Provider
 *
 * Wrapper component for Ory Elements React integration.
 *
 * @module components/ory-elements-provider
 */

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import type { OryConfig } from '../core/types';

// =============================================================================
// Types
// =============================================================================

/**
 * Ory Elements configuration
 */
export interface OryElementsConfig {
  /** Ory project configuration */
  ory: OryConfig;
  /** Custom styling options */
  styling?: {
    /** Primary color */
    primaryColor?: string;
    /** Border radius */
    borderRadius?: string;
    /** Font family */
    fontFamily?: string;
  };
  /** Locale for UI strings */
  locale?: string;
}

/**
 * Ory Elements context value
 */
export interface OryElementsContextValue {
  /** Configuration */
  config: OryElementsConfig;
  /** SDK URL for Ory Elements */
  sdkUrl: string;
}

/**
 * Ory Elements provider props
 */
export interface OryElementsProviderProps {
  /** Ory Elements configuration */
  config: OryElementsConfig;
  /** Children */
  children: ReactNode;
}

// =============================================================================
// Context
// =============================================================================

const OryElementsContext = createContext<OryElementsContextValue | null>(null);

OryElementsContext.displayName = 'OryElementsContext';

// =============================================================================
// Provider
// =============================================================================

/**
 * Ory Elements provider component
 *
 * Provides configuration for Ory Elements React components.
 * This is optional and only needed if using @ory/elements-react.
 *
 * @example
 * ```tsx
 * import { OryElementsProvider } from '@open-zentra/foundation-auth';
 *
 * <OryElementsProvider
 *   config={{
 *     ory: { kratosUrl: 'https://your-project.ory.cloud' },
 *     styling: { primaryColor: '#0066cc' },
 *   }}
 * >
 *   <LoginCard />
 * </OryElementsProvider>
 * ```
 */
export const OryElementsProvider = ({ config, children }: OryElementsProviderProps): ReactNode => {
  const value = useMemo<OryElementsContextValue>(() => {
    // Normalize the SDK URL
    const sdkUrl = config.ory.kratosUrl.replace(/\/+$/, '');

    return {
      config,
      sdkUrl,
    };
  }, [config]);

  return <OryElementsContext.Provider value={value}>{children}</OryElementsContext.Provider>;
};

// =============================================================================
// Hook
// =============================================================================

/**
 * Use Ory Elements context
 *
 * @returns Ory Elements context value
 * @throws {Error} If used outside OryElementsProvider
 */
export const useOryElements = (): OryElementsContextValue => {
  const context = useContext(OryElementsContext);

  if (!context) {
    throw new Error('[useOryElements] Must be used within an OryElementsProvider');
  }

  return context;
};

/**
 * Get Ory Elements configuration for @ory/elements-react
 *
 * This returns the configuration in the format expected by Ory Elements.
 *
 * @returns Ory Elements SDK configuration
 *
 * @example
 * ```tsx
 * import { UserAuthCard } from '@ory/elements-react';
 *
 * const LoginPage = () => {
 *   const oryConfig = useOryElementsConfig();
 *
 *   return (
 *     <UserAuthCard
 *       flow={loginFlow}
 *       flowType="login"
 *       config={oryConfig}
 *     />
 *   );
 * };
 * ```
 */
export const useOryElementsConfig = () => {
  const { config, sdkUrl } = useOryElements();

  return useMemo(
    () => ({
      sdk: {
        url: sdkUrl,
      },
      project: {
        slug: config.ory.projectSlug,
      },
      ...(config.styling && {
        theme: {
          accent: config.styling.primaryColor,
          borderRadius: config.styling.borderRadius,
          fontFamily: config.styling.fontFamily,
        },
      }),
      ...(config.locale && {
        intl: {
          locale: config.locale,
        },
      }),
    }),
    [sdkUrl, config.ory.projectSlug, config.styling, config.locale],
  );
};

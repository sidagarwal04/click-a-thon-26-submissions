import { useCallback } from 'react';

import { useAuth, useAuthSession } from '@open-zentra/foundation-auth';
import { useQuery } from '@tanstack/react-query';
import { Navigate, Route, Routes } from 'react-router-dom';

import { apiUrl, requestJson, type TokenSource } from './api';
import { ChatPage } from './pages/chat/chat-page';
import { ComingSoon } from './pages/coming-soon';
import { ConnectionsPage } from './pages/connections/connections-page';
import { ConnectorConfig } from './pages/connections/connector-config';
import { ConnectorPicker } from './pages/connections/connector-picker';
import { CubeSchemaPage } from './pages/datasets/cube-schema-page';
import { DatasetsPage } from './pages/datasets/datasets-page';
import { RowsPage } from './pages/datasets/rows-page';
import {
  MembershipUnavailable,
  OrganizationRequired,
  ResolvingIdentity,
  SetupRequired,
  SignedOut,
} from './pages/entry-screens';
import { InvestigationWorkspace } from './pages/investigation/investigation-workspace';
import { Launcher } from './pages/launcher';
import { AppShell } from './shell/app-shell';
import type { IdentityContext, ReadinessResponse } from './types';

interface AppProps {
  readonly clerkConfigured?: boolean;
}

const requestReadiness = async (): Promise<ReadinessResponse> => {
  const response = await fetch(`${apiUrl}/health/ready`);
  return (await response.json()) as ReadinessResponse;
};

const AuthenticatedWorkspace = () => {
  const { logout, tenant } = useAuth();
  const { getAccessToken } = useAuthSession();
  // A Clerk session token lives 60 seconds. Holding one in component state and
  // reusing it means the first click on a page left open sends a dead token —
  // the API answers "Invalid bearer token" and it reads like a configuration
  // fault. Minting per request costs nothing: Clerk caches internally and
  // refreshes near expiry, so this is a memory read almost every time.
  const getToken = useCallback<TokenSource>(
    () => getAccessToken({ audience: 'first_party_http' }),
    [getAccessToken],
  );
  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: requestReadiness,
    enabled: Boolean(tenant?.id),
    retry: false,
  });
  const identity = useQuery({
    queryKey: ['identity-context', tenant?.id],
    queryFn: () => requestJson<IdentityContext>('/v1/context', getToken),
    enabled: Boolean(tenant?.id),
    retry: false,
  });

  if (!tenant?.id) {
    return <OrganizationRequired onSignOut={() => void logout()} />;
  }
  if (identity.isPending) {
    return <ResolvingIdentity message="Resolving governed tenant context…" />;
  }
  if (identity.error || !identity.data) {
    return <MembershipUnavailable detail={identity.error?.message} />;
  }

  return (
    <AppShell identity={identity.data} readiness={readiness.data}>
      <Routes>
        <Route path="/" element={<Launcher getToken={getToken} identity={identity.data} />} />
        <Route
          path="/investigations/:id"
          element={<InvestigationWorkspace getToken={getToken} />}
        />
        <Route
          path="/dashboard"
          element={
            <ComingSoon
              title="Dashboard"
              icon="grid"
              description="A tenant-wide view of running investigations, published findings and the approvals waiting on you."
            />
          }
        />
        <Route
          path="/datasets"
          element={<DatasetsPage getToken={getToken} identity={identity.data} />}
        />
        <Route
          path="/datasets/:dataSourceId/tables/:tableName/rows"
          element={<RowsPage getToken={getToken} identity={identity.data} />}
        />
        <Route path="/cube-schema" element={<CubeSchemaPage getToken={getToken} />} />
        <Route
          path="/chat"
          element={<ChatPage getToken={getToken} identity={identity.data} />}
        />
        <Route
          path="/connections"
          element={<ConnectionsPage getToken={getToken} identity={identity.data} />}
        />
        <Route path="/connections/new" element={<ConnectorPicker />} />
        <Route
          path="/connections/new/:connectorId"
          element={<ConnectorConfig getToken={getToken} identity={identity.data} />}
        />
        <Route
          path="/settings"
          element={
            <ComingSoon
              title="Settings"
              icon="settings"
              description="Tenant policy, approval thresholds, theme and notification preferences."
            />
          }
        />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Routes>
    </AppShell>
  );
};

const AuthenticatedEntry = () => {
  const { isAuthenticated, isInitializing, login } = useAuth();

  if (isInitializing) {
    return <ResolvingIdentity message="Resolving your identity…" />;
  }
  if (!isAuthenticated) {
    return <SignedOut login={() => login()} />;
  }
  return <AuthenticatedWorkspace />;
};

export function App({ clerkConfigured = false }: AppProps) {
  return clerkConfigured ? <AuthenticatedEntry /> : <SetupRequired />;
}

export default App;

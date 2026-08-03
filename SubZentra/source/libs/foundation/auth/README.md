# @open-zentra/foundation-auth

Authentication and session management for Open Zentra, centered on Ory and reusable token/session helpers for authenticated HTTP and WebSocket clients.

## Features

- Ory Kratos and Hydra integration
- React auth/session/flow hooks
- Session refresh and token access helpers
- Role and permission mapping
- Ory Elements support for hosted auth UIs

## Installation

```bash
npm install @open-zentra/foundation-auth
npm install @ory/client-fetch @ory/elements-react react
```

## Quick Start

```tsx
import { AuthProvider } from '@open-zentra/foundation-auth';

const App = () => (
  <AuthProvider
    config={{
      ory: {
        kratosUrl: 'https://your-project.ory.cloud',
        hydraUrl: 'https://your-hydra.ory.cloud',
      },
      autoRefreshSession: true,
      sessionRefreshIntervalMs: 300000,
    }}
  >
    <YourApp />
  </AuthProvider>
);
```

## Typical Usage

```tsx
import { useAuth, useAuthSession, useAuthUser } from '@open-zentra/foundation-auth';

const ProfilePage = () => {
  const { isAuthenticated, logout } = useAuth();
  const { user } = useAuthUser();
  const { getAccessToken } = useAuthSession();

  if (!isAuthenticated) {
    return <div>Please log in</div>;
  }

  return (
    <div>
      <h1>{user?.name ?? user?.email}</h1>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
};
```

`getAccessToken()` can be reused by:

- shared `axios` interceptors
- any caller that still uses bearer-token transport
- any other authenticated HTTP client

For enterprise realtime ticket auth, use `createRealtimeTicketFetcher(...)` with your shared `axios` instance and pass the resulting callback to `DataLayerConfig.websocket.auth`. Same-origin cookie/session setups are supported by making the HTTP ticket request with those cookies; the websocket itself no longer has a separate cookie-auth mode.

## Validation

```bash
./node_modules/.bin/tsc -p libs/foundation/auth/tsconfig.lib.json --pretty false --noEmit
```

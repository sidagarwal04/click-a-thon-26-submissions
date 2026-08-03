import { StrictMode } from 'react';

import * as ReactDOM from 'react-dom/client';

import App from './app/app';
import { AppProviders } from './app/providers';

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <StrictMode>
    <AppProviders>
      <App clerkConfigured={Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY)} />
    </AppProviders>
  </StrictMode>,
);

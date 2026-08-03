import { createContext, useContext } from 'react';

import type {
  RealtimeConnectionStateSnapshot,
  RealtimeMessageEnvelope,
  RealtimeSubscriptionStateMap,
} from '../core/types';
import type { RealtimeSocketClient, RealtimeSocketStatus } from './socket-client';

export interface RealtimeSocketContextValue {
  readonly client: RealtimeSocketClient;
  readonly status: RealtimeSocketStatus;
  readonly connection: RealtimeConnectionStateSnapshot;
  readonly subscriptions: RealtimeSubscriptionStateMap;
  readonly lastMessage: RealtimeMessageEnvelope | null;
}

export const RealtimeSocketContext = createContext<RealtimeSocketContextValue | null>(null);

RealtimeSocketContext.displayName = 'RealtimeSocketContext';

export const useRealtimeSocketContext = (): RealtimeSocketContextValue => {
  const context = useContext(RealtimeSocketContext);
  if (!context) {
    throw new Error('useRealtimeSocket must be used within a DataLayerProvider');
  }

  return context;
};

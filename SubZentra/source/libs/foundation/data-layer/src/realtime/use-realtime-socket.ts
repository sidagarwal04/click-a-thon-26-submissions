import { useMemo } from 'react';

import { useRealtimeSocketContext } from './context';

export interface UseRealtimeSocketResult {
  readonly status: ReturnType<typeof useRealtimeSocketContext>['status'];
  readonly connection: ReturnType<typeof useRealtimeSocketContext>['connection'];
  readonly subscriptions: ReturnType<typeof useRealtimeSocketContext>['subscriptions'];
  readonly ownership: ReturnType<typeof useRealtimeSocketContext>['connection']['ownership'];
  readonly lastMessage: ReturnType<typeof useRealtimeSocketContext>['lastMessage'];
  readonly isConnected: boolean;
  readonly send: ReturnType<typeof useRealtimeSocketContext>['client']['send'];
  readonly subscribe: ReturnType<typeof useRealtimeSocketContext>['client']['subscribeMessages'];
}

export const useRealtimeSocket = (): UseRealtimeSocketResult => {
  const { client, status, connection, subscriptions, lastMessage } = useRealtimeSocketContext();

  return useMemo(
    () => ({
      status,
      connection,
      subscriptions,
      ownership: connection.ownership,
      lastMessage,
      isConnected: connection.state === 'ready',
      send: client.send.bind(client),
      subscribe: client.subscribeMessages.bind(client),
    }),
    [client, connection, lastMessage, status, subscriptions],
  );
};

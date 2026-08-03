/**
 * Data Layer Provider
 *
 * @module provider/data-layer-provider
 */

import React, { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { QueryClientProvider, type QueryKey } from '@tanstack/react-query';

import type { AuthScopeSnapshot } from '@open-zentra/foundation-auth';
import type {
  RealtimeDataServerMessage,
  RealtimeTopicDescriptor,
} from '@open-zentra/foundation-data-model';
import {
  REALTIME_CONNECTION_STATE,
  REALTIME_OWNERSHIP_STATE,
  REALTIME_SERVER_MESSAGE_TYPE,
  SYNC_EVENT_TYPE,
  type SyncEvent,
} from '@open-zentra/foundation-data-model';
import { createLogger, hashPayloadSync, type Logger } from '@open-zentra/foundation-utils';

import {
  createContainerConfig,
  getDatasourceEndpointFingerprint,
} from '../core/config-normalization';
import { DataLayerContainer, type DataLayerDependencies } from '../core/container';
import type {
  DataLayerConfig,
  DataLayerContextValue,
  RealtimeConnectionStateSnapshot,
  RealtimeMessageEnvelope,
  RealtimeSubscriptionStateMap,
} from '../core/types';
import { RealtimeSocketContext } from '../realtime';
import { DataLayerContext } from './data-layer-context';
import { DataLayerInternalsContext, type DataLayerInternals } from './data-layer-internals-context';

export interface DataLayerProviderProps {
  readonly config: DataLayerConfig;
  readonly children: ReactNode;
  readonly authScope?: AuthScopeSnapshot | null;
  readonly clearOnAuthScopeChange?: boolean;
  readonly loadingComponent?: ReactNode;
  readonly errorComponent?: (error: Error) => ReactNode;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const createInitialRealtimeConnection = (
  config: DataLayerConfig,
): RealtimeConnectionStateSnapshot => ({
  state: REALTIME_CONNECTION_STATE.IDLE,
  ownership:
    config.websocket.leaderMode === 'standalone'
      ? REALTIME_OWNERSHIP_STATE.STANDALONE
      : REALTIME_OWNERSHIP_STATE.UNKNOWN,
  protocolVersion: config.websocket.protocolVersion ?? '1.0',
  negotiatedProtocolVersion: null,
  connectionId: null,
  leaderTabId: null,
  heartbeatIntervalMs: null,
  lastConnectedAt: null,
  lastReadyAt: null,
  updatedAt: Date.now(),
  lastErrorCode: null,
  lastErrorMessage: null,
});

const getDescriptorFingerprint = (descriptor: unknown): Record<string, unknown> | null => {
  if (!descriptor || typeof descriptor !== 'object') {
    return null;
  }

  const value = descriptor as Record<string, unknown>;
  return {
    method: value['method'] ?? null,
    pathType: typeof value['path'],
  };
};

const getTableFingerprint = (
  tables: DataLayerConfig['tables'],
): ReadonlyArray<Record<string, unknown>> =>
  (tables ?? []).map((table) => ({
    name: table.name,
    staleTime: table.staleTime ?? null,
    gcTime: table.gcTime ?? null,
    conflictStrategy: table.conflictStrategy ?? null,
    analytics: table.analytics?.enabled ?? null,
    api: {
      list: getDescriptorFingerprint(table.api?.list),
      get: getDescriptorFingerprint(table.api?.get),
      create: getDescriptorFingerprint(table.api?.create),
      update: getDescriptorFingerprint(table.api?.update),
      delete: getDescriptorFingerprint(table.api?.delete),
    },
    realtime: table.realtime
      ? {
          topic: table.realtime.topic,
          events: table.realtime.events ?? [],
          applyStrategy: table.realtime.applyStrategy ?? null,
          versionField: table.realtime.versionField ?? null,
        }
      : null,
  }));

const getRealtimeTopics = (deps: DataLayerDependencies): RealtimeTopicDescriptor[] =>
  deps.tableRegistry
    .getAllTables()
    .flatMap((table) =>
      table.realtime
        ? [{ topic: table.realtime.topic, table: table.name } satisfies RealtimeTopicDescriptor]
        : [],
    );

const getRealtimeEntityId = (message: RealtimeDataServerMessage): string | null => {
  if (message.entityId) {
    return message.entityId;
  }

  if (isRecord(message.payload) && typeof message.payload.id === 'string') {
    return message.payload.id;
  }

  return null;
};

const getRealtimeEntityVersion = (
  deps: DataLayerDependencies,
  tableName: string,
  entity: unknown,
  fallbackVersion: number | null | undefined,
): number | null => {
  const table = deps.tableRegistry.getTable(tableName);
  const realtime = table?.realtime;
  if (!realtime) {
    return fallbackVersion ?? null;
  }

  if (realtime.getVersion) {
    const value = realtime.getVersion(entity);
    return typeof value === 'number' ? value : fallbackVersion ?? null;
  }

  if (realtime.versionField && isRecord(entity)) {
    const value = entity[realtime.versionField];
    return typeof value === 'number' ? value : fallbackVersion ?? null;
  }

  return fallbackVersion ?? null;
};

const upsertListItem = <T extends { id?: string }>(
  items: T[],
  payload: T,
  deps: DataLayerDependencies,
  tableName: string,
  messageVersion: number | null | undefined,
): T[] => {
  const payloadId = payload.id;
  if (!payloadId) {
    return items;
  }

  const existingIndex = items.findIndex((item) => item.id === payloadId);
  if (existingIndex === -1) {
    return [...items, payload];
  }

  const existingVersion = getRealtimeEntityVersion(deps, tableName, items[existingIndex], null);
  if (
    typeof existingVersion === 'number' &&
    typeof messageVersion === 'number' &&
    existingVersion > messageVersion
  ) {
    return items;
  }

  const next = [...items];
  next[existingIndex] = payload;
  return next;
};

const removeListItem = <T extends { id?: string }>(items: T[], entityId: string): T[] =>
  items.filter((item) => item.id !== entityId);

const isRealtimeListKey = (queryKey: QueryKey, table: string): boolean =>
  Array.isArray(queryKey) && queryKey.length === 1 && queryKey[0] === table;

const isRealtimeDetailKey = (queryKey: QueryKey, table: string, entityId: string | null): boolean =>
  Array.isArray(queryKey) &&
  entityId !== null &&
  queryKey[0] === table &&
  typeof queryKey[1] === 'string' &&
  queryKey[1] === entityId;

const isAmbiguousTableKey = (queryKey: QueryKey, table: string): boolean =>
  Array.isArray(queryKey) &&
  queryKey[0] === table &&
  !isRealtimeListKey(queryKey, table) &&
  !(typeof queryKey[1] === 'string' && queryKey.length >= 2);

const isTransactionalQueryEngineKey = (queryKey: QueryKey, table: string): boolean =>
  Array.isArray(queryKey) &&
  queryKey[0] === 'query-engine' &&
  queryKey[1] === 'transactional' &&
  queryKey[2] === table;

const invalidateTableQueries = (deps: DataLayerDependencies, tableName: string): void => {
  const { queryClient } = deps;
  const queries = queryClient.getQueryCache().findAll();
  const invalidateKeys: QueryKey[] = [];

  for (const query of queries) {
    const queryKey = query.queryKey;

    if (isTransactionalQueryEngineKey(queryKey, tableName)) {
      invalidateKeys.push(queryKey);
      continue;
    }

    if (!Array.isArray(queryKey) || queryKey[0] !== tableName) {
      continue;
    }

    invalidateKeys.push(queryKey);
  }

  if (invalidateKeys.length > 0) {
    void Promise.all(
      invalidateKeys.map((queryKey) =>
        queryClient.invalidateQueries({
          queryKey,
          refetchType: 'active',
        }),
      ),
    );
  }
};

const validateRealtimeMessage = (
  deps: DataLayerDependencies,
  message: RealtimeMessageEnvelope,
): RealtimeDataServerMessage | null => {
  if (
    message.type !== REALTIME_SERVER_MESSAGE_TYPE.EVENT &&
    message.type !== REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT
  ) {
    return null;
  }

  const table = deps.tableRegistry.getTable(message.table);
  if (!table?.realtime) {
    return null;
  }

  if (message.type === REALTIME_SERVER_MESSAGE_TYPE.EVENT) {
    if (message.payload === undefined) {
      return message;
    }

    const parsed = table.realtime.entitySchema.safeParse(message.payload);
    return parsed.success ? { ...message, payload: parsed.data } : null;
  }

  const parsed = table.realtime.snapshotSchema.safeParse(message.payload);
  return parsed.success ? { ...message, payload: parsed.data } : null;
};

const applyRealtimeMessage = (
  deps: DataLayerDependencies,
  message: RealtimeMessageEnvelope,
): void => {
  if (message.type === REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED) {
    invalidateTableQueries(deps, message.table);
    return;
  }

  if (
    message.type !== REALTIME_SERVER_MESSAGE_TYPE.EVENT &&
    message.type !== REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT
  ) {
    return;
  }

  const tableConfig = deps.tableRegistry.getTable(message.table);
  const applyStrategy = tableConfig?.realtime?.applyStrategy ?? 'patch_list';
  const validatedMessage = validateRealtimeMessage(deps, message);
  if (!validatedMessage) {
    invalidateTableQueries(deps, message.table);
    return;
  }

  if (applyStrategy === 'invalidate') {
    invalidateTableQueries(deps, message.table);
    return;
  }

  const { queryClient } = deps;
  const queries = queryClient.getQueryCache().findAll();
  const invalidateKeys: QueryKey[] = [];
  const entityId = getRealtimeEntityId(validatedMessage);

  for (const query of queries) {
    const queryKey = query.queryKey;

    if (isTransactionalQueryEngineKey(queryKey, validatedMessage.table)) {
      invalidateKeys.push(queryKey);
      continue;
    }

    if (!Array.isArray(queryKey) || queryKey[0] !== validatedMessage.table) {
      continue;
    }

    if (isRealtimeDetailKey(queryKey, validatedMessage.table, entityId)) {
      if (
        validatedMessage.type === REALTIME_SERVER_MESSAGE_TYPE.EVENT &&
        validatedMessage.kind === 'deleted'
      ) {
        queryClient.removeQueries({ queryKey });
      } else if (
        validatedMessage.type === REALTIME_SERVER_MESSAGE_TYPE.EVENT &&
        validatedMessage.payload !== undefined
      ) {
        queryClient.setQueryData(queryKey, (current: unknown) => {
          const currentVersion = getRealtimeEntityVersion(
            deps,
            validatedMessage.table,
            current,
            null,
          );
          if (
            typeof currentVersion === 'number' &&
            typeof validatedMessage.version === 'number' &&
            currentVersion > validatedMessage.version
          ) {
            return current;
          }

          return validatedMessage.payload;
        });
      } else {
        invalidateKeys.push(queryKey);
      }
      continue;
    }

    if (isRealtimeListKey(queryKey, validatedMessage.table)) {
      if (applyStrategy === 'patch_detail') {
        invalidateKeys.push(queryKey);
        continue;
      }

      if (validatedMessage.type === REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT) {
        if (Array.isArray(validatedMessage.payload)) {
          queryClient.setQueryData(queryKey, validatedMessage.payload);
        } else {
          invalidateKeys.push(queryKey);
        }
        continue;
      }

      if (!entityId) {
        invalidateKeys.push(queryKey);
        continue;
      }

      queryClient.setQueryData(queryKey, (current: unknown) => {
        if (!Array.isArray(current)) {
          return current;
        }

        if (validatedMessage.kind === 'deleted') {
          return removeListItem(current as Array<{ id?: string }>, entityId);
        }

        if (validatedMessage.payload === undefined || !isRecord(validatedMessage.payload)) {
          return current;
        }

        return upsertListItem(
          current as Array<{ id?: string }>,
          validatedMessage.payload as { id?: string },
          deps,
          validatedMessage.table,
          validatedMessage.version,
        );
      });
      continue;
    }

    if (isAmbiguousTableKey(queryKey, validatedMessage.table)) {
      invalidateKeys.push(queryKey);
    }
  }

  if (invalidateKeys.length > 0) {
    void Promise.all(
      invalidateKeys.map((queryKey) =>
        queryClient.invalidateQueries({
          queryKey,
          refetchType: 'active',
        }),
      ),
    );
  }
};

export const DataLayerProvider = ({
  config,
  children,
  authScope,
  clearOnAuthScopeChange = true,
  loadingComponent,
  errorComponent,
}: DataLayerProviderProps): React.ReactElement => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingSyncCount, setPendingSyncCount] = useState(0);
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);
  const [isLeader, setIsLeader] = useState(false);
  const [deps, setDeps] = useState<DataLayerDependencies | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [realtimeConnection, setRealtimeConnection] = useState<RealtimeConnectionStateSnapshot>(
    () => createInitialRealtimeConnection(config),
  );
  const [realtimeSubscriptions, setRealtimeSubscriptions] = useState<RealtimeSubscriptionStateMap>(
    {},
  );
  const [lastRealtimeMessage, setLastRealtimeMessage] = useState<RealtimeMessageEnvelope | null>(
    null,
  );

  const containerRef = useRef<DataLayerContainer | null>(null);
  const syncUnsubscribeRef = useRef<(() => void) | null>(null);
  const lastRealtimeErrorCodeRef = useRef<string | null>(null);
  const authScopeKeyRef = useRef<string | null>(null);

  // The logger only varies with config.debug, so it is built when that changes
  // rather than on every render, which is what the render-phase assignment here
  // used to do — a fresh logger per render, immediately discarded.
  const logger = useMemo(
    () => createLogger('DataLayerProvider', { level: config.debug ? 'debug' : 'warn' }),
    [config.debug],
  );

  // Latest-value refs for the effects and callbacks below, which read them long
  // after commit. Written in an effect so nothing is mutated during render;
  // useRef seeds both with the right value for the first commit.
  const loggerRef = useRef<Logger>(logger);
  const configRef = useRef<DataLayerConfig>(config);

  useEffect(() => {
    loggerRef.current = logger;
    configRef.current = config;
  }, [logger, config]);
  const resolvedAuthScope = authScope ?? config.authScope ?? null;
  const authScopeKey = resolvedAuthScope?.scopeKey ?? 'anonymous';

  const configHash = useMemo(() => {
    const hashableConfig = {
      tables: getTableFingerprint(config.tables),
      conflictStrategy: config.conflictStrategy,
      enableCrossTab: config.enableCrossTab,
      enableAnalytics: config.enableAnalytics,
      defaultStaleTime: config.defaultStaleTime,
      defaultGcTime: config.defaultGcTime,
      cache: config.cache,
      axiosBaseUrl: config.axiosInstance.defaults?.baseURL ?? null,
      websocketUrl: config.websocket.url,
      websocketProtocols: config.websocket.protocols ?? [],
      websocketProtocolVersion: config.websocket.protocolVersion ?? null,
      websocketLeaderMode: config.websocket.leaderMode ?? null,
      debug: config.debug,
      datasourceEndpoint: getDatasourceEndpointFingerprint(config.datasourceEndpoint),
    };
    return hashPayloadSync(hashableConfig);
  }, [config]);

  const realtimeStatus = realtimeConnection.state;

  const isDuckDBAvailable = deps?.analyticsEnabled ?? false;
  const shouldOwnSocket =
    deps !== null &&
    (config.websocket.leaderMode === 'standalone' || config.enableCrossTab === false || isLeader);
  const realtimeOwnership =
    config.websocket.leaderMode === 'standalone' || config.enableCrossTab === false
      ? REALTIME_OWNERSHIP_STATE.STANDALONE
      : shouldOwnSocket
      ? REALTIME_OWNERSHIP_STATE.LEADER
      : REALTIME_OWNERSHIP_STATE.FOLLOWER;

  useEffect(() => {
    let mounted = true;
    const currentConfig = configRef.current;
    const container = new DataLayerContainer(createContainerConfig(currentConfig));

    containerRef.current = container;

    const handleSyncEvent = (
      event: SyncEvent,
      dependencies: DataLayerDependencies,
      isMounted: boolean,
      containerInstance: DataLayerContainer,
    ): void => {
      if (!isMounted || containerInstance.isDisposed) return;

      switch (event.type) {
        case SYNC_EVENT_TYPE.ONLINE:
          setIsOnline(true);
          break;
        case SYNC_EVENT_TYPE.OFFLINE:
          setIsOnline(false);
          break;
        case SYNC_EVENT_TYPE.SYNC_START:
          setIsSyncing(true);
          break;
        case SYNC_EVENT_TYPE.SYNC_COMPLETE:
          setIsSyncing(false);
          setLastSyncedAt(event.timestamp);
          break;
        case SYNC_EVENT_TYPE.SYNC_ERROR:
          setIsSyncing(false);
          break;
        case SYNC_EVENT_TYPE.QUEUE_PROCESSED:
          dependencies.syncCoordinator
            .getState()
            .then((state) => {
              if (isMounted && !containerInstance.isDisposed) {
                setPendingSyncCount(state.pendingMutations);
              }
            })
            .catch((err) => {
              loggerRef.current.warn('Failed to get sync state:', err);
            });
          break;
      }
    };

    container
      .initialize()
      .then(async (dependencies) => {
        if (!mounted || container.isDisposed) return;

        const unsubscribe = dependencies.syncCoordinator.subscribe((event: SyncEvent) => {
          if (!mounted || container.isDisposed) return;

          if (event.type === SYNC_EVENT_TYPE.LEADER_CHANGED && event.data?.isLeader !== undefined) {
            setIsLeader(event.data.isLeader);
          }

          handleSyncEvent(event, dependencies, mounted, container);
        });
        syncUnsubscribeRef.current = unsubscribe;

        try {
          const initialState = await dependencies.syncCoordinator.getState();
          if (mounted && !container.isDisposed) {
            setIsOnline(initialState.isOnline);
            setIsSyncing(initialState.isSyncing);
            setPendingSyncCount(initialState.pendingMutations);
            setLastSyncedAt(initialState.lastSyncAt);
            setIsLeader(initialState.isLeader);
          }
        } catch (err) {
          loggerRef.current.warn('Failed to get initial sync state:', err);
        }

        if (mounted && !container.isDisposed) {
          setDeps(dependencies);
          setIsInitialized(true);
        }
      })
      .catch((err) => {
        if (mounted && !container.isDisposed) {
          const initError = err instanceof Error ? err : new Error(String(err));
          loggerRef.current.error('Initialization failed:', initError);
          setError(initError);
        }
      });

    return () => {
      mounted = false;
      if (syncUnsubscribeRef.current) {
        syncUnsubscribeRef.current();
        syncUnsubscribeRef.current = null;
      }
      container.dispose().catch((err) => {
        loggerRef.current.error('Disposal error:', err);
      });
      containerRef.current = null;
    };
  }, [configHash]);

  useEffect(() => {
    if (!deps) {
      return;
    }

    deps.realtimeClient.registerTopics(getRealtimeTopics(deps));

    const unsubscribeConnection = deps.realtimeClient.subscribeConnection((snapshot) => {
      setRealtimeConnection(snapshot);

      if (shouldOwnSocket) {
        deps.syncCoordinator.broadcastRealtimeState(snapshot);

        if (snapshot.lastErrorCode && snapshot.lastErrorCode !== lastRealtimeErrorCodeRef.current) {
          lastRealtimeErrorCodeRef.current = snapshot.lastErrorCode;

          const eventType =
            snapshot.lastErrorCode === 'REALTIME_HEARTBEAT_TIMEOUT'
              ? SYNC_EVENT_TYPE.REALTIME_HEARTBEAT_TIMEOUT
              : snapshot.lastErrorCode === 'REALTIME_AUTH_FAILED'
              ? SYNC_EVENT_TYPE.REALTIME_AUTH_FAILURE
              : snapshot.lastErrorCode === 'REALTIME_RESUME_FAILED'
              ? SYNC_EVENT_TYPE.REALTIME_RESUME_FAILED
              : SYNC_EVENT_TYPE.REALTIME_PROTOCOL_ERROR;

          deps.syncCoordinator.reportRealtimeEvent({
            type: eventType,
            data: {
              realtimeConnection: snapshot,
            },
          });
        }
      }
    });

    const unsubscribeSubscriptions = deps.realtimeClient.subscribeSubscriptions((subscriptions) => {
      setRealtimeSubscriptions(subscriptions);

      if (shouldOwnSocket) {
        Object.values(subscriptions).forEach((subscription) => {
          deps.syncCoordinator.broadcastRealtimeSubscriptionState(subscription);
        });
      }
    });

    const unsubscribeMessages = deps.realtimeClient.subscribeMessages((message) => {
      setLastRealtimeMessage(message);

      if (shouldOwnSocket) {
        deps.syncCoordinator.broadcastRealtimeMessage(message);
      }

      if (message.type === REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED) {
        if (shouldOwnSocket) {
          deps.syncCoordinator.broadcastRealtimeResync(
            message.topic,
            message.table,
            message.reason,
          );
        }
        deps.syncCoordinator.reportRealtimeEvent({
          type: SYNC_EVENT_TYPE.REALTIME_RESYNC_REQUIRED,
          data: {
            topic: message.topic,
            realtimeMessage: message,
          },
        });
      }

      if (message.type === REALTIME_SERVER_MESSAGE_TYPE.ERROR) {
        const eventType =
          message.code === 'REALTIME_AUTH_FAILED'
            ? SYNC_EVENT_TYPE.REALTIME_AUTH_FAILURE
            : message.code === 'REALTIME_SUBSCRIPTION_FAILED'
            ? SYNC_EVENT_TYPE.REALTIME_SUBSCRIPTION_FAILED
            : message.code === 'REALTIME_RESUME_FAILED'
            ? SYNC_EVENT_TYPE.REALTIME_RESUME_FAILED
            : SYNC_EVENT_TYPE.REALTIME_PROTOCOL_ERROR;
        deps.syncCoordinator.reportRealtimeEvent({
          type: eventType,
          data: {
            topic: message.topic,
            realtimeMessage: message,
          },
        });
      }

      applyRealtimeMessage(deps, message);
    });

    const unsubscribeRealtimeState = deps.syncCoordinator.subscribeRealtimeState((snapshot) => {
      if (shouldOwnSocket) {
        return;
      }

      deps.realtimeClient.ingestConnectionSnapshot({
        ...snapshot,
        ownership: REALTIME_OWNERSHIP_STATE.FOLLOWER,
      });
    });

    const unsubscribeRealtimeSubscriptions =
      deps.syncCoordinator.subscribeRealtimeSubscriptionState((subscription) => {
        if (shouldOwnSocket) {
          return;
        }

        deps.realtimeClient.ingestSubscriptionSnapshot(subscription);
      });

    const unsubscribeRealtimeMessages = deps.syncCoordinator.subscribeRealtimeMessages(
      (message) => {
        if (shouldOwnSocket) {
          return;
        }

        deps.realtimeClient.ingestServerMessage(message);
      },
    );

    const unsubscribeRealtimeResync = deps.syncCoordinator.subscribeRealtimeResync((payload) => {
      if (shouldOwnSocket) {
        return;
      }

      invalidateTableQueries(deps, payload.table);
    });

    return () => {
      unsubscribeConnection();
      unsubscribeSubscriptions();
      unsubscribeMessages();
      unsubscribeRealtimeState();
      unsubscribeRealtimeSubscriptions();
      unsubscribeRealtimeMessages();
      unsubscribeRealtimeResync();
    };
  }, [deps, shouldOwnSocket]);

  useEffect(() => {
    if (!deps) {
      return;
    }

    deps.realtimeClient.setOwnership(realtimeOwnership, null);

    if (!shouldOwnSocket) {
      deps.realtimeClient.disconnect();
      return;
    }

    void deps.realtimeClient.connect().catch((err) => {
      const connectError = err instanceof Error ? err : new Error(String(err));
      loggerRef.current.error('Realtime connection failed:', connectError);
      deps.syncCoordinator.reportRealtimeEvent({
        type: SYNC_EVENT_TYPE.REALTIME_PROTOCOL_ERROR,
        data: {
          error: connectError,
          realtimeConnection: deps.realtimeClient.getConnectionSnapshot(),
        },
      });
    });
  }, [deps, realtimeOwnership, shouldOwnSocket]);

  useEffect(() => {
    if (!deps) {
      return;
    }

    if (!clearOnAuthScopeChange) {
      authScopeKeyRef.current = authScopeKey;
      return;
    }

    const previousScopeKey = authScopeKeyRef.current;
    if (previousScopeKey === null) {
      authScopeKeyRef.current = authScopeKey;
      return;
    }

    if (previousScopeKey === authScopeKey) {
      return;
    }

    authScopeKeyRef.current = authScopeKey;
    deps.realtimeClient.disconnect();
    setRealtimeConnection(createInitialRealtimeConnection(configRef.current));
    setRealtimeSubscriptions({});
    setLastRealtimeMessage(null);

    void (async () => {
      try {
        await deps.realtimeClient.clearResumeState();
        await deps.database.clearAll();
        deps.queryClient.clear();

        if (shouldOwnSocket) {
          await deps.realtimeClient.connect();
        }
      } catch (err) {
        const scopeError = err instanceof Error ? err : new Error(String(err));
        loggerRef.current.error('Auth scope rotation failed:', scopeError);
      }
    })();
  }, [authScopeKey, clearOnAuthScopeChange, deps, shouldOwnSocket]);

  // Depends on `deps` rather than `deps?.syncCoordinator`: the optional-chained
  // dependency defeats the compiler, which cannot match it to the access it
  // infers and so skips memoising the callback entirely. `deps` is state, set
  // once per container, so its members only change identity when it does.
  const syncNow = useCallback(async () => {
    if (!deps?.syncCoordinator) return;
    await deps.syncCoordinator.sync();
  }, [deps]);

  const clearCache = useCallback(async () => {
    deps?.realtimeClient.disconnect();
    await deps?.realtimeClient.clearResumeState();
    if (deps?.database) {
      await deps.database.clearAll();
    }
    deps?.queryClient.clear();

    if (deps?.realtimeClient && shouldOwnSocket) {
      await deps.realtimeClient.connect();
    }
  }, [deps, shouldOwnSocket]);

  const syncState = useMemo(() => {
    if (!deps?.syncCoordinator) return null;
    return {
      isOnline,
      isSyncing,
      lastSyncAt: lastSyncedAt,
      pendingMutations: pendingSyncCount,
      failedMutations: 0,
      isLeader,
    };
  }, [deps?.syncCoordinator, isOnline, isSyncing, lastSyncedAt, pendingSyncCount, isLeader]);

  const contextValue = useMemo<DataLayerContextValue>(
    () => ({
      isOnline,
      isInitialized,
      isDuckDBAvailable: isDuckDBAvailable ?? false,
      isSyncing,
      pendingSyncCount,
      lastSyncedAt,
      isLeader,
      syncState,
      syncNow,
      clearCache,
    }),
    [
      isOnline,
      isInitialized,
      isDuckDBAvailable,
      isSyncing,
      pendingSyncCount,
      lastSyncedAt,
      isLeader,
      syncState,
      syncNow,
      clearCache,
    ],
  );

  const internalsValue = useMemo<DataLayerInternals | null>(() => {
    if (!deps) return null;

    return {
      queryClient: deps.queryClient,
      axiosInstance: deps.axiosInstance,
      authScope: resolvedAuthScope,
      authScopeKey,
      realtimeClient: deps.realtimeClient,
      realtimeStatus,
      realtimeConnection,
      realtimeSubscriptions,
      lastRealtimeMessage,
      database: deps.database,
      syncCoordinator: deps.syncCoordinator,
      duckdbRouter: deps.duckdbRouter,
      opfsManager: deps.opfsManager,
      analyticsEnabled: deps.analyticsEnabled,
      initializeAnalytics: deps.initializeAnalytics,
      isOnline,
      cacheConfig: deps.cacheConfig,
      tableRegistry: deps.tableRegistry,
      datasourceEndpoint: deps.datasourceEndpoint,
      getTableSyncService: deps.getTableSyncService,
      getFileDownloadService: deps.getFileDownloadService,
    };
  }, [
    deps,
    authScopeKey,
    isOnline,
    lastRealtimeMessage,
    realtimeConnection,
    realtimeStatus,
    realtimeSubscriptions,
    resolvedAuthScope,
  ]);

  const realtimeValue = useMemo(() => {
    if (!deps) {
      return null;
    }

    return {
      client: deps.realtimeClient,
      status: realtimeStatus,
      connection: realtimeConnection,
      subscriptions: realtimeSubscriptions,
      lastMessage: lastRealtimeMessage,
    };
  }, [deps, lastRealtimeMessage, realtimeConnection, realtimeStatus, realtimeSubscriptions]);

  if (error) {
    if (errorComponent) {
      return <>{errorComponent(error)}</>;
    }
    return <div>Data layer initialization failed: {error.message}</div>;
  }

  if (!isInitialized || !internalsValue || !deps || !realtimeValue) {
    return <React.Fragment>{loadingComponent}</React.Fragment>;
  }

  return (
    <DataLayerContext.Provider value={contextValue}>
      <DataLayerInternalsContext.Provider value={internalsValue}>
        <RealtimeSocketContext.Provider value={realtimeValue}>
          <QueryClientProvider client={deps.queryClient}>{children}</QueryClientProvider>
        </RealtimeSocketContext.Provider>
      </DataLayerInternalsContext.Provider>
    </DataLayerContext.Provider>
  );
};

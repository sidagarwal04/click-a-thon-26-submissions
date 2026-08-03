/**
 * useConflictResolution - Hook for handling sync conflicts
 *
 * Provides access to conflict resolution capabilities from the SyncCoordinator.
 * Uses ConflictResolver from foundation-sync-engine.
 * Persists conflicts to database so they survive page refreshes.
 *
 * @module hooks/use-conflict-resolution
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { useQueryClient } from '@tanstack/react-query';

import {
  CONFLICT_RESOLUTION_TYPE,
  SYNC_EVENT_TYPE,
  SYNC_STATE_KEY,
  toJsonSerializable,
  type ConflictResolutionType,
} from '@open-zentra/foundation-data-model';

import { useDataLayerInternals } from '../provider/data-layer-internals-context';
import { createScopedErrorHandler } from '../utils/error-handler';

// =============================================================================
// Types
// =============================================================================

/**
 * Information about a sync conflict
 */
export interface ConflictInfo {
  /** Unique conflict ID */
  readonly id: string;
  /** Table name where the conflict occurred */
  readonly tableName: string;
  /** Entity ID that has the conflict */
  readonly entityId: string;
  /** Local (optimistic) version of the data */
  readonly localData: unknown;
  /** Remote (server) version of the data */
  readonly remoteData: unknown;
  /** When the conflict was detected */
  readonly detectedAt: number;
}

/**
 * Resolution strategy for a conflict
 */
export type ConflictResolution = {
  readonly type: ConflictResolutionType;
  readonly mergedData?: unknown;
};

// Create scoped error handler for this hook
const handleConflictError = createScopedErrorHandler('useConflictResolution');

/**
 * Type guard for conflict event data
 */
interface ConflictEventData {
  readonly conflictCount?: number;
  readonly tableName?: string;
  readonly entityId?: string;
  readonly localData?: unknown;
  readonly remoteData?: unknown;
}

const isConflictEventData = (data: unknown): data is ConflictEventData =>
  data !== null && typeof data === 'object';

const isConflictInfoArray = (value: unknown): value is ConflictInfo[] => {
  if (!Array.isArray(value)) {
    return false;
  }

  return value.every((item) => {
    if (item === null || typeof item !== 'object') {
      return false;
    }
    const candidate = item as Record<string, unknown>;
    return (
      typeof candidate.id === 'string' &&
      typeof candidate.tableName === 'string' &&
      typeof candidate.entityId === 'string' &&
      typeof candidate.detectedAt === 'number'
    );
  });
};

// =============================================================================
// Conflicts Context (for efficient conflict lookup)
// =============================================================================

/**
 * Context value for conflicts - read-only access to conflicts list
 */
interface ConflictsContextValue {
  conflicts: ConflictInfo[];
}

const ConflictsContext = createContext<ConflictsContextValue | null>(null);

/**
 * Hook to get read-only access to conflicts list
 * This is more efficient than using useConflictResolution when you only need to read conflicts
 *
 * @internal Used by useEntityConflict for efficient lookup
 */
const useConflictsContext = (): ConflictInfo[] => {
  const context = useContext(ConflictsContext);
  if (context === null) {
    // Fall back to empty array if context not available
    // This allows useEntityConflict to work even without the full context
    return [];
  }
  return context.conflicts;
};

/**
 * Hook for conflict resolution
 *
 * Provides list of conflicts and methods to resolve them.
 * Conflicts are persisted to database and survive page refreshes.
 *
 * @example
 * ```tsx
 * const {
 *   conflicts,
 *   hasConflicts,
 *   resolveConflict,
 *   resolveAll,
 * } = useConflictResolution();
 *
 * // Show conflicts UI
 * if (hasConflicts) {
 *   return (
 *     <ConflictModal
 *       conflicts={conflicts}
 *       onResolve={(id, resolution) => resolveConflict(id, resolution)}
 *       onResolveAll={() => resolveAll({ type: 'accept-remote' })}
 *     />
 *   );
 * }
 * ```
 */
export const useConflictResolution = (): {
  /** List of current sync conflicts */
  readonly conflicts: ConflictInfo[];
  /** Whether any conflicts exist */
  readonly hasConflicts: boolean;
  /** Number of current conflicts */
  readonly conflictCount: number;
  /** Resolve a single conflict by ID with the chosen resolution strategy */
  readonly resolveConflict: (conflictId: string, resolution: ConflictResolution) => Promise<void>;
  /** Resolve all conflicts with the same resolution strategy */
  readonly resolveAll: (resolution: ConflictResolution) => Promise<void>;
  /** Dismiss a conflict without resolving (removes from list) */
  readonly dismissConflict: (conflictId: string) => void;
  /** Dismiss all conflicts without resolving */
  readonly dismissAll: () => void;
} => {
  const { syncCoordinator, database } = useDataLayerInternals();
  const queryClient = useQueryClient();
  const [conflicts, setConflicts] = useState<ConflictInfo[]>([]);

  // Use refs for values needed in callbacks to avoid unstable dependencies
  const conflictsRef = useRef<ConflictInfo[]>(conflicts);

  // Synced in a layout effect rather than during render: a ref written
  // mid-render is unsound under concurrent rendering. Nothing here reads
  // it during render, so the effect is equivalent.
  useLayoutEffect(() => {
    conflictsRef.current = conflicts;
  });

  // Track initialization state
  const initializedRef = useRef(false);

  // Load persisted conflicts on mount with proper cleanup
  useEffect(() => {
    let mounted = true;

    const loadConflicts = async () => {
      // Skip if already initialized
      if (initializedRef.current) return;

      try {
        // Use getRaw() for untyped access - conflicts are validated by array check
        const storedConflicts = await database.syncState.getRaw(SYNC_STATE_KEY.CONFLICTS);

        // Only update state if component is still mounted
        if (!mounted) return;

        initializedRef.current = true;

        if (isConflictInfoArray(storedConflicts)) {
          setConflicts(storedConflicts);
        }
      } catch (error) {
        if (!mounted) return;
        initializedRef.current = true;
        handleConflictError(error);
      }
    };

    loadConflicts();

    return () => {
      mounted = false;
    };
  }, [database]);

  // Persist conflicts to database when they change
  useEffect(() => {
    // Don't persist until we've loaded (to avoid overwriting with empty array)
    if (!initializedRef.current) return;

    let mounted = true;

    const persistConflicts = async () => {
      try {
        // syncState.set() takes key and value directly
        await database.syncState.set(SYNC_STATE_KEY.CONFLICTS, conflicts);
      } catch (error) {
        if (!mounted) return;
        handleConflictError(error, { severity: 'error' });
      }
    };

    persistConflicts();

    return () => {
      mounted = false;
    };
  }, [conflicts, database]);

  // Subscribe to conflict events
  useEffect(() => {
    const unsubscribe = syncCoordinator.subscribe((event) => {
      if (event.type === SYNC_EVENT_TYPE.CONFLICT_DETECTED && isConflictEventData(event.data)) {
        const eventData = event.data;
        const conflictCount = eventData.conflictCount;

        if (conflictCount && conflictCount > 0) {
          // Get conflict info from event data if available
          const conflictInfo: ConflictInfo = {
            id: crypto.randomUUID(),
            tableName: eventData.tableName ?? 'unknown',
            entityId: eventData.entityId ?? 'unknown',
            localData: eventData.localData ?? null,
            remoteData: eventData.remoteData ?? null,
            detectedAt: Date.now(),
          };
          setConflicts((prev) => [...prev, conflictInfo]);
        }
      }
    });

    return unsubscribe;
  }, [syncCoordinator]);

  // Resolve a single conflict with the user's chosen resolution
  // Uses ref for conflicts to maintain stable callback reference
  const resolveConflict = useCallback(
    async (conflictId: string, resolution: ConflictResolution): Promise<void> => {
      const conflict = conflictsRef.current.find((c) => c.id === conflictId);
      if (!conflict) return;

      // Determine the resolved data based on user's resolution choice
      let resolvedData: unknown;
      switch (resolution.type) {
        case CONFLICT_RESOLUTION_TYPE.ACCEPT_LOCAL:
          resolvedData = conflict.localData;
          break;
        case CONFLICT_RESOLUTION_TYPE.ACCEPT_REMOTE:
          resolvedData = conflict.remoteData;
          break;
        case CONFLICT_RESOLUTION_TYPE.MERGE:
          resolvedData = resolution.mergedData;
          break;
        default:
          resolvedData = conflict.remoteData;
      }

      // Update the TanStack Query cache with the resolved data
      const queryKey = [conflict.tableName, conflict.entityId];
      queryClient.setQueryData(queryKey, resolvedData);

      // Also update the list query if it exists
      const listQueryKey = [conflict.tableName];
      queryClient.setQueryData<Array<{ id?: string }>>(listQueryKey, (old) => {
        if (!old) return old;
        return old.map((item) => {
          if (item.id === conflict.entityId) {
            if (resolvedData !== null && typeof resolvedData === 'object') {
              return { ...item, ...resolvedData };
            }
            return item;
          }
          return item;
        });
      });

      // If user accepted local data, we need to sync it to server
      // Queue the update via sync coordinator if we accepted local or merged data
      if (resolution.type !== CONFLICT_RESOLUTION_TYPE.ACCEPT_REMOTE) {
        const queueManager = syncCoordinator.getQueueManager();
        const serializedData = toJsonSerializable(resolvedData);
        await queueManager.enqueue({
          type: 'update',
          tableName: conflict.tableName,
          entityId: conflict.entityId,
          payload: serializedData,
          optimisticData: serializedData,
          invalidateKeys: [JSON.stringify(queryKey), JSON.stringify(listQueryKey)],
        });
      }

      // Remove resolved conflict from list (will be persisted via useEffect)
      setConflicts((prev) => prev.filter((c) => c.id !== conflictId));

      // Invalidate related queries to refresh data
      syncCoordinator.invalidateQueries([[conflict.tableName, conflict.entityId]]);
    },
    [syncCoordinator, queryClient], // Stable dependencies only - conflicts accessed via ref
  );

  // Resolve all conflicts with the same resolution
  // Uses ref for conflicts to maintain stable callback reference
  const resolveAll = useCallback(
    async (resolution: ConflictResolution): Promise<void> => {
      // Copy current conflicts to avoid issues with state changes during iteration
      const currentConflicts = [...conflictsRef.current];

      // Process conflicts sequentially to avoid race conditions
      for (const conflict of currentConflicts) {
        await resolveConflict(conflict.id, resolution);
      }
    },
    [resolveConflict], // Now stable since resolveConflict uses refs
  );

  // Dismiss a conflict without resolving (also persisted)
  const dismissConflict = useCallback((conflictId: string) => {
    setConflicts((prev) => prev.filter((c) => c.id !== conflictId));
  }, []);

  // Dismiss all conflicts (also persisted)
  const dismissAll = useCallback(() => {
    setConflicts([]);
  }, []);

  // Memoize derived values
  const hasConflicts = useMemo(() => conflicts.length > 0, [conflicts.length]);
  const conflictCount = conflicts.length;

  return {
    conflicts,
    hasConflicts,
    conflictCount,
    resolveConflict,
    resolveAll,
    dismissConflict,
    dismissAll,
  };
};

/**
 * Provider component for conflicts context.
 *
 * Wraps a subtree with read-only access to the conflicts list,
 * enabling efficient `useEntityConflict` lookups without requiring
 * each component to subscribe to the full `useConflictResolution` hook.
 *
 * @param props.conflicts - The current conflicts array from `useConflictResolution`
 * @param props.children - Child components that can access conflicts via `useEntityConflict`
 * @returns React element wrapping children with ConflictsContext
 *
 * @example
 * ```tsx
 * function ConflictAwareApp() {
 *   const { conflicts } = useConflictResolution();
 *
 *   return (
 *     <ConflictsProvider conflicts={conflicts}>
 *       <YourApp />
 *     </ConflictsProvider>
 *   );
 * }
 * ```
 */
export const ConflictsProvider = ({
  conflicts,
  children,
}: {
  readonly conflicts: ConflictInfo[];
  readonly children: ReactNode;
}): React.ReactElement => (
  <ConflictsContext.Provider value={{ conflicts }}>{children}</ConflictsContext.Provider>
);

/**
 * Hook to get a specific conflict by entity.
 *
 * This hook is optimized to avoid creating a full `useConflictResolution` instance.
 * When used within a `ConflictsProvider`, it reads from context directly.
 * Without the provider, it returns `null` (use `ConflictsProvider` for best results).
 *
 * @param tableName - The table name to check for conflicts
 * @param entityId - The entity ID to check for conflicts
 * @returns The conflict info if one exists for this entity, otherwise `null`
 *
 * @example
 * ```tsx
 * const conflict = useEntityConflict('users', userId);
 *
 * if (conflict) {
 *   return <ConflictBadge conflict={conflict} />;
 * }
 * ```
 */
export const useEntityConflict = (tableName: string, entityId: string): ConflictInfo | null => {
  // Try to get conflicts from context first (more efficient)
  const contextConflicts = useConflictsContext();

  // Memoize the find operation to avoid unnecessary recalculations
  return useMemo(
    () =>
      contextConflicts.find((c) => c.tableName === tableName && c.entityId === entityId) ?? null,
    [contextConflicts, tableName, entityId],
  );
};

/**
 * Hook to get all conflicts (read-only).
 *
 * Lightweight hook that only returns the conflicts list without resolution methods.
 * More efficient than `useConflictResolution` when you only need to display conflicts.
 *
 * Requires `ConflictsProvider` in the component tree. Returns an empty array if
 * no provider is found.
 *
 * @returns Read-only array of current conflicts
 *
 * @example
 * ```tsx
 * const conflicts = useConflicts();
 *
 * return (
 *   <ConflictList conflicts={conflicts} />
 * );
 * ```
 */
export const useConflicts = (): ConflictInfo[] => useConflictsContext();

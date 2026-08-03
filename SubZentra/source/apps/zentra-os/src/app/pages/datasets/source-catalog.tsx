import { useEffect, useState } from 'react';

import {
  Alert,
  Badge,
  Button,
  Card,
  Progress,
  Skeleton,
  Switch,
} from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, type TokenSource } from '../../api';
import { ConnectorLogo } from '../connections/connector-logos';
import type { SourceResponse } from '../connections/types';

import { getHarvest, latestCatalog, setTableAgentAccess, startHarvest } from './api';
import { HARVEST_FAILURE_HELP, PHASE_LABEL, formatBytes, formatRows } from './format';
import type { CatalogResponse, CatalogTable, HarvestResponse } from './types';
import { isTerminal } from './types';

interface SourceCatalogProps {
  readonly source: SourceResponse;
  readonly getToken: TokenSource;
  readonly canWrite: boolean;
  readonly onOpenTable: (table: CatalogTable) => void;
  readonly onBrowseRows: (table: CatalogTable) => void;
}

const TableCard = ({
  table,
  canWrite,
  onOpen,
  onBrowseRows,
  onToggleAgentAccess,
}: {
  readonly table: CatalogTable;
  readonly canWrite: boolean;
  readonly onOpen: () => void;
  readonly onBrowseRows: () => void;
  readonly onToggleAgentAccess: (visible: boolean) => void;
}) => (
  <div className="group flex flex-col items-start rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary">
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-start justify-between gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <span className="truncate font-mono text-sm">{table.name}</span>
      <Icon
        name="chevron_right"
        size="sm"
        className="shrink-0 text-foreground-muted transition-transform group-hover:translate-x-0.5"
      />
    </button>
    <span className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
      <span className="tabular-nums">{formatRows(table.estimated_rows)} rows</span>
      <span className="tabular-nums">{(table.fields ?? []).length} cols</span>
      <span className="tabular-nums">{formatBytes(table.size_bytes)}</span>
    </span>
    <Button
      intent="secondary"
      size="sm"
      className="mt-3 w-full"
      onClick={(event) => {
        event.stopPropagation();
        onBrowseRows();
      }}
    >
      Browse rows
    </Button>
    <label
      className="mt-3 flex w-full items-center justify-between gap-3 border-t border-border/50 pt-3 text-xs"
      onClick={(event) => event.stopPropagation()}
    >
      <span className="text-foreground-muted">Agent access</span>
      <Switch
        size="sm"
        checked={table.agent_visible}
        disabled={!canWrite}
        onCheckedChange={onToggleAgentAccess}
      />
    </label>
  </div>
);

const HarvestProgress = ({ run }: { readonly run: HarvestResponse }) => (
  <div className="mt-4">
    <div className="flex items-center justify-between gap-4 text-sm">
      <span>{PHASE_LABEL[run.phase]}…</span>
      <span className="font-mono text-[10px] uppercase tracking-[0.14em] tabular-nums text-foreground-muted">
        {run.tables_found} tables · {run.fields_described} fields
      </span>
    </div>
    {/* Indeterminate: the total is not known until listing finishes, and a
        percentage of an unknown total would be a fiction. */}
    <Progress className="mt-3" value={undefined} />
  </div>
);

/**
 * One source and whatever discovery has learned about it.
 *
 * Three states, kept distinct because they need different things offered: a
 * catalog to browse, a harvest to watch, or nothing yet and a button to start
 * one. A source that has never been harvested is not an error.
 */
export const SourceCatalog = ({
  source,
  getToken,
  canWrite,
  onOpenTable,
  onBrowseRows,
}: SourceCatalogProps) => {
  const queryClient = useQueryClient();
  const [watching, setWatching] = useState<string | null>(null);

  const catalog = useQuery({
    queryKey: ['catalog', source.data_source_id],
    queryFn: () => latestCatalog(getToken, source.data_source_id),
    // A 404 means "not harvested yet" and is a final answer, not a blip.
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 404) && count < 2,
  });

  const run = useQuery({
    queryKey: ['harvest', watching],
    queryFn: () => getHarvest(getToken, watching as string),
    enabled: watching !== null,
    // Polling is the only way to follow work scheduled after the response.
    refetchInterval: (query) => {
      const phase = query.state.data?.phase;
      return phase && isTerminal(phase) ? false : 1200;
    },
  });

  const begin = useMutation({
    mutationFn: () => startHarvest(getToken, source.data_source_id),
    onSuccess: (started) => setWatching(started.harvest_run_id),
  });

  const catalogQueryKey = ['catalog', source.data_source_id];

  const toggleTableAccess = useMutation({
    mutationFn: (input: { tableName: string; visible: boolean }) =>
      setTableAgentAccess(getToken, source.data_source_id, input.tableName, input.visible),
    // Optimistic: a switch that waits for a round trip before moving reads as
    // broken, and this write cannot fail for a reason the reader could fix.
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: catalogQueryKey });
      const previous = queryClient.getQueryData<CatalogResponse>(catalogQueryKey);
      queryClient.setQueryData<CatalogResponse>(catalogQueryKey, (current) =>
        current
          ? {
              ...current,
              tables: current.tables?.map((table) =>
                table.name === input.tableName
                  ? { ...table, agent_visible: input.visible }
                  : table,
              ),
            }
          : current,
      );
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) queryClient.setQueryData(catalogQueryKey, context.previous);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: catalogQueryKey });
    },
  });

  // A finished run is what makes the catalog worth asking for again. The poll
  // stops itself — `refetchInterval` returns false on a terminal phase — so the
  // only thing left to do here is refetch, and `watching` can stay as it is.
  // Clearing it would be a setState inside an effect for no gain.
  const finished = run.data && isTerminal(run.data.phase) ? run.data : null;
  useEffect(() => {
    if (!finished) return;
    void queryClient.invalidateQueries({ queryKey: ['catalog', source.data_source_id] });
  }, [finished, queryClient, source.data_source_id]);

  const isHarvesting = begin.isPending || (run.data != null && !isTerminal(run.data.phase));
  const notHarvested = catalog.error instanceof ApiError && catalog.error.status === 404;
  const tables = [...(catalog.data?.tables ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  const failure = finished?.failure_code;

  return (
    <section className="mt-12 first:mt-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ConnectorLogo name="clickhouse" className="h-5 w-5" />
        <h2 className="text-lg font-medium">{source.name}</h2>
        <Badge intent={source.health === 'reachable' ? 'success' : 'default'} size="sm">
          {source.health}
        </Badge>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          {source.connection_hint ?? 'ClickHouse'}
        </span>
        <span className="flex-1" />
        {catalog.data ? (
          <Button
            intent="secondary"
            size="sm"
            disabled={!canWrite || isHarvesting}
            loading={isHarvesting}
            onClick={() => begin.mutate()}
          >
            Re-harvest
          </Button>
        ) : null}
      </div>

      {catalog.isPending ? (
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-[92px] w-full" />
          <Skeleton className="h-[92px] w-full" />
          <Skeleton className="h-[92px] w-full" />
        </div>
      ) : null}

      {notHarvested && !isHarvesting ? (
        <Card padding="lg" className="mt-5">
          <p className="text-sm">This source has not been harvested.</p>
          <p className="mt-2 max-w-2xl text-sm text-foreground-muted">
            Discovery lists the tables, describes their columns and profiles a sample of
            each. It runs queries against the source, so it is started deliberately rather
            than on every page load.
          </p>
          <Button
            className="mt-5"
            disabled={!canWrite}
            loading={begin.isPending}
            onClick={() => begin.mutate()}
          >
            <Icon name="refresh_cw" size="sm" /> Harvest tables
          </Button>
        </Card>
      ) : null}

      {isHarvesting ? (
        <Card padding="lg" className="mt-5">
          <HarvestProgress
            run={
              run.data ?? {
                phase: 'pending',
                tables_found: 0,
                fields_described: 0,
              } as HarvestResponse
            }
          />
        </Card>
      ) : null}

      {failure ? (
        <Alert
          intent="error"
          className="mt-5"
          role="alert"
          title="That harvest did not finish"
        >
          {HARVEST_FAILURE_HELP[failure] ?? finished?.failure_message ?? failure}
        </Alert>
      ) : null}

      {begin.error ? (
        <Alert intent="error" className="mt-5" role="alert" title="Harvest could not start">
          {begin.error.message}
        </Alert>
      ) : null}

      {catalog.error && !notHarvested ? (
        <Alert intent="error" className="mt-5" role="alert" title="Catalog could not be read">
          {catalog.error.message}
        </Alert>
      ) : null}

      {tables.length > 0 ? (
        <>
          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tables.map((table) => (
              <TableCard
                key={table.table_id}
                table={table}
                canWrite={canWrite}
                onOpen={() => onOpenTable(table)}
                onBrowseRows={() => onBrowseRows(table)}
                onToggleAgentAccess={(visible) =>
                  toggleTableAccess.mutate({ tableName: table.name, visible })
                }
              />
            ))}
          </div>
          {(catalog.data?.unreadable ?? []).length > 0 ? (
            <p className="mt-4 text-xs text-foreground-muted">
              {catalog.data?.unreadable?.length} table(s) were visible but could not be
              read; they are listed in the harvest rather than here.
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
};

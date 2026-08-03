import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Skeleton,
} from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { ApiError, type TokenSource } from '../../api';
import type { IdentityContext } from '../../types';

import { listSources, testConnection } from './api';
import { CONNECTION_FAILURE_HELP, HEALTH_INTENT, HEALTH_LABEL } from './constants';
import { ConnectorLogo } from './connector-logos';
import type { SourceResponse } from './types';

interface ConnectionsPageProps {
  readonly getToken: TokenSource;
  readonly identity: IdentityContext;
}

const formatVerified = (value: string | null | undefined): string => {
  if (!value) return 'never verified';
  const at = new Date(value);
  return Number.isNaN(at.getTime())
    ? 'never verified'
    : `verified ${at.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`;
};

interface SourceRowProps {
  readonly source: SourceResponse;
  readonly onTest: (source: SourceResponse) => void;
  readonly testing: boolean;
  readonly canWrite: boolean;
}

const SourceRow = ({ source, onTest, testing, canWrite }: SourceRowProps) => (
  // `flex-row` is explicit: Card's own base is `flex flex-col`, and since
  // direction and wrapping are different properties, `flex-wrap` alone leaves
  // the column intact — the row silently stacks.
  <Card padding="md" className="flex flex-row flex-wrap items-center gap-x-5 gap-y-3">
    <ConnectorLogo
      name={source.kind === 'uploaded' ? 'sftp' : 'clickhouse'}
      className="h-6 w-6 shrink-0"
    />
    <div className="min-w-0 flex-1">
      <p className="truncate text-sm font-medium">{source.name}</p>
      <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        {source.connection_hint ?? (source.kind === 'uploaded' ? 'Uploaded snapshot' : 'ClickHouse')}
        {' · '}
        {formatVerified(source.last_verified_at)}
      </p>
    </div>
    <Badge intent={HEALTH_INTENT[source.health]} size="sm">
      {HEALTH_LABEL[source.health]}
    </Badge>
    {source.kind === 'connected' ? (
      <Button
        intent="secondary"
        size="sm"
        loading={testing}
        disabled={!canWrite || testing}
        onClick={() => onTest(source)}
      >
        Re-test
      </Button>
    ) : null}
  </Card>
);

/**
 * The sources this tenant has registered.
 *
 * Health is shown per row rather than assumed: a source that was reachable when
 * it was registered is not necessarily reachable now, and a rotated password is
 * the most ordinary way for an investigation to start failing.
 */
export const ConnectionsPage = ({ getToken, identity }: ConnectionsPageProps) => {
  const queryClient = useQueryClient();
  const canWrite = identity.role !== 'viewer';

  const sources = useQuery({
    queryKey: ['connector-sources'],
    queryFn: () => listSources(getToken),
  });

  const retest = useMutation({
    mutationFn: (source: SourceResponse) => testConnection(getToken, source.data_source_id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['connector-sources'] }),
  });

  const failureCode =
    retest.error instanceof ApiError && retest.error.status === 502
      ? retest.error.message
      : undefined;

  return (
    <section className="px-8 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
            Sources
          </p>
          <h1 className="mt-3 font-serif text-[clamp(2rem,4vw,3rem)] font-normal tracking-[-0.035em]">
            Connections
          </h1>
        </div>
        <Button component={Link} to="/connections/new" size="lg" disabled={!canWrite}>
          <Icon name="plus" size="sm" /> Create connection
        </Button>
      </div>

      {sources.isPending ? (
        <div className="mt-10 flex flex-col gap-3">
          <Skeleton className="h-[74px] w-full" />
          <Skeleton className="h-[74px] w-full" />
        </div>
      ) : null}

      {sources.error ? (
        <Alert intent="error" className="mt-10" role="alert" title="Sources could not be listed">
          {sources.error.message}
        </Alert>
      ) : null}

      {retest.error ? (
        <Alert intent="error" className="mt-10" role="alert" title="That source did not answer">
          {failureCode ? (CONNECTION_FAILURE_HELP[failureCode] ?? retest.error.message) : retest.error.message}
        </Alert>
      ) : null}

      {sources.data && sources.data.length > 0 ? (
        <div className="mt-10 flex flex-col gap-3">
          {sources.data.map((source) => (
            <SourceRow
              key={source.data_source_id}
              source={source}
              canWrite={canWrite}
              testing={retest.isPending && retest.variables?.data_source_id === source.data_source_id}
              onTest={(target) => retest.mutate(target)}
            />
          ))}
        </div>
      ) : null}

      {sources.data && sources.data.length === 0 ? (
        <EmptyState
          className="mt-12 border border-border bg-card"
          size="lg"
          icon={<Icon name="network" size="xl" />}
        >
          <EmptyState.Title>No sources connected</EmptyState.Title>
          <EmptyState.Description>
            An investigation can only cite data it can reach. Connect a ClickHouse service to
            give this tenant something to harvest.
          </EmptyState.Description>
          <EmptyState.Actions>
            <Button component={Link} to="/connections/new" disabled={!canWrite}>
              Create connection
            </Button>
          </EmptyState.Actions>
        </EmptyState>
      ) : null}
    </section>
  );
};

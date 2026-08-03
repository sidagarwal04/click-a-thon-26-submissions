import { Alert, Skeleton } from '@open-zentra/foundation-design-system';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { ApiError, type TokenSource } from '../../api';
import type { IdentityContext } from '../../types';
import { listSources } from '../connections/api';

import { getTableRows } from './api';
import { RowsPager } from './rows-pager';
import { RowsTable } from './rows-table';

interface RowsPageProps {
  readonly getToken: TokenSource;
  readonly identity: IdentityContext;
}

/**
 * A paginated, read-only view of one Source Table's raw rows, queried
 * straight through Cube. See ADR-0023 for why this bypasses Cube's usual
 * governed-metrics gate, and why that is safe here.
 */
export const RowsPage = ({ getToken }: RowsPageProps) => {
  const { dataSourceId = '', tableName = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get('page') ?? '1') || 1;

  const sources = useQuery({
    queryKey: ['connector-sources'],
    queryFn: () => listSources(getToken),
  });
  const source = sources.data?.find((s) => s.data_source_id === dataSourceId);

  const rows = useQuery({
    queryKey: ['table-rows', dataSourceId, tableName, page],
    queryFn: () => getTableRows(getToken, dataSourceId, tableName, page),
    // 404/503 both mean "not ready yet" here, not a blip worth retrying.
    retry: (count, error) =>
      !(error instanceof ApiError && (error.status === 404 || error.status === 503)) &&
      count < 2,
  });

  const notReady =
    rows.error instanceof ApiError && (rows.error.status === 404 || rows.error.status === 503);
  const fqn = [source?.name, tableName].filter(Boolean).join('.');

  return (
    <section className="px-8 py-10">
      <Link
        to="/datasets"
        className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary"
      >
        ← Datasets
      </Link>
      <h1 className="mt-3 truncate font-mono text-[clamp(1.5rem,3vw,2.25rem)] font-normal tracking-[-0.02em]">
        {fqn || tableName}
      </h1>

      {rows.isPending ? (
        <div className="mt-8 flex flex-col gap-3">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : null}

      {notReady ? (
        <Alert intent="default" className="mt-8" role="status" title="Still syncing">
          This dataset isn't ready to browse yet. It may still be syncing — try again in a
          few minutes.
        </Alert>
      ) : null}

      {rows.error && !notReady ? (
        <Alert intent="error" className="mt-8" role="alert" title="Rows could not be read">
          {rows.error.message}
        </Alert>
      ) : null}

      {rows.data ? (
        <>
          <div className="mt-8 overflow-x-auto">
            <RowsTable columns={rows.data.columns} rows={rows.data.rows} />
          </div>
          <RowsPager
            page={rows.data.page}
            pageSize={rows.data.page_size}
            total={rows.data.total}
            disabled={rows.isFetching}
            onPageChange={(next) => setSearchParams({ page: String(next) })}
          />
        </>
      ) : null}
    </section>
  );
};

import { useQuery } from '@tanstack/react-query';

import { requestJson, type TokenSource } from '../../api';

interface CubeSchemaPageProps {
  readonly getToken: TokenSource;
}

/**
 * Dump of whatever `/v1/catalog` returns, unrendered. A quick way to see every
 * table, dimension, and measure Cube currently has compiled, with no styling
 * or shaping — replace with something real once the shape that's actually
 * useful here is known.
 */
export const CubeSchemaPage = ({ getToken }: CubeSchemaPageProps) => {
  const catalog = useQuery({
    queryKey: ['cube-schema-dump'],
    queryFn: () => requestJson<unknown>('/v1/catalog', getToken),
  });

  if (catalog.isPending) return <p>Loading…</p>;
  if (catalog.error) return <p>{catalog.error.message}</p>;

  return <pre>{JSON.stringify(catalog.data, null, 2)}</pre>;
};

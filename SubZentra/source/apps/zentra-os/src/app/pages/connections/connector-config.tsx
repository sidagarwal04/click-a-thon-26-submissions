import { Navigate, useParams } from 'react-router-dom';

import type { TokenSource } from '../../api';
import type { IdentityContext } from '../../types';

import { ClickHouseConfig } from './clickhouse-config';
import { CLICKHOUSE_ID, findConnector } from './constants';
import { PlaceholderConfig } from './placeholder-config';

interface ConnectorConfigProps {
  readonly getToken: TokenSource;
  readonly identity: IdentityContext;
}

/**
 * Routes `/connections/new/:connectorId` to the page that connector deserves.
 *
 * An id nobody offers goes back to the picker rather than to a placeholder —
 * a typed URL is not a connector that is merely unbuilt.
 */
export const ConnectorConfig = ({ getToken, identity }: ConnectorConfigProps) => {
  const { connectorId } = useParams<{ connectorId: string }>();
  const connector = findConnector(connectorId);

  if (!connector) return <Navigate replace to="/connections/new" />;
  if (connector.id === CLICKHOUSE_ID) {
    return <ClickHouseConfig getToken={getToken} canWrite={identity.role !== 'viewer'} />;
  }
  return <PlaceholderConfig connector={connector} />;
};

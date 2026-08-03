import type { Connector, ConnectorCategory, SourceHealth } from './types';

/** The connector the picker actually connects. */
export const CLICKHOUSE_ID = 'clickhouse';

/**
 * The source connectors the picker offers.
 *
 * Exactly one is `available`. The connector API accepts a single credential
 * shape — host, port, database, username, password — so ClickHouse is the only
 * entry that can reach anything. The others are listed because the shape of the
 * product is the point, and marked unbuilt so nobody types a Snowflake password
 * into a form that discards it.
 */
export const CONNECTORS: readonly Connector[] = [
  {
    id: CLICKHOUSE_ID,
    name: 'ClickHouse',
    category: 'Data warehouses',
    logo: 'clickhouse',
    icon: 'database',
    available: true,
    blurb: 'Connect a ClickHouse Cloud service or self-managed cluster.',
  },
  {
    id: 'snowflake',
    name: 'Snowflake',
    category: 'Data warehouses',
    logo: 'snowflake',
    icon: 'database',
    available: false,
    blurb: 'Warehouse, role and account credentials for a Snowflake instance.',
  },
  {
    id: 'bigquery',
    name: 'BigQuery',
    category: 'Data warehouses',
    logo: 'bigquery',
    icon: 'database',
    available: false,
    blurb: 'A GCP project and service account with dataset read access.',
  },
  {
    id: 'databricks',
    name: 'Databricks',
    category: 'Data warehouses',
    logo: 'databricks',
    icon: 'database',
    available: false,
    blurb: 'A SQL warehouse endpoint and personal access token.',
  },
  {
    id: 'postgresql',
    name: 'PostgreSQL',
    category: 'Databases',
    logo: 'postgresql',
    icon: 'database',
    available: false,
    blurb: 'A Postgres instance reachable over TCP, with a read-only role.',
  },
  {
    id: 'mysql',
    name: 'MySQL',
    category: 'Databases',
    logo: 'mysql',
    icon: 'database',
    available: false,
    blurb: 'A MySQL or MariaDB instance with a replication-safe reader.',
  },
  {
    id: 'mssql',
    name: 'MS SQL Server',
    category: 'Databases',
    logo: 'mssql',
    icon: 'database',
    available: false,
    blurb: 'SQL Server over TDS, with an instance and database name.',
  },
  {
    id: 'oracle',
    name: 'Oracle',
    category: 'Databases',
    logo: 'oracle',
    icon: 'database',
    available: false,
    blurb: 'An Oracle service name or SID, reachable over SQL*Net.',
  },
  {
    id: 's3',
    name: 'AWS S3',
    category: 'Cloud storage',
    logo: 's3',
    icon: 'archive',
    available: false,
    blurb: 'A bucket and prefix of Parquet or CSV objects.',
  },
  {
    id: 'azure-blob',
    name: 'Azure Blob',
    category: 'Cloud storage',
    logo: 'azure-blob',
    icon: 'archive',
    available: false,
    blurb: 'A storage account container, read with a SAS token.',
  },
  {
    id: 'gcs',
    name: 'Google Cloud Storage',
    category: 'Cloud storage',
    logo: 'gcs',
    icon: 'archive',
    available: false,
    blurb: 'A GCS bucket read through a service account key.',
  },
  {
    id: 'sftp',
    name: 'SFTP',
    category: 'File systems',
    logo: 'sftp',
    icon: 'folder',
    available: false,
    blurb: 'A remote directory polled for dropped files.',
  },
];

/** Picker layout order. */
export const CONNECTOR_CATEGORIES: readonly ConnectorCategory[] = [
  'Data warehouses',
  'Databases',
  'Cloud storage',
  'File systems',
];

export const findConnector = (id: string | undefined): Connector | undefined =>
  CONNECTORS.find((connector) => connector.id === id);

/** ClickHouse Cloud terminates TLS on 8443; a plain HTTP port is 8123. */
export const CLICKHOUSE_SECURE_PORT = 8443;
export const CLICKHOUSE_PLAIN_PORT = 8123;

export const HEALTH_LABEL: Record<SourceHealth, string> = {
  unverified: 'Unverified',
  reachable: 'Reachable',
  unreachable: 'Unreachable',
};

export const HEALTH_INTENT: Record<SourceHealth, 'default' | 'success' | 'danger'> = {
  unverified: 'default',
  reachable: 'success',
  unreachable: 'danger',
};

/**
 * The API answers a failed connection with a coarse code and nothing else —
 * a source's own error text carries hostnames and topology. Coarse is still
 * enough to say which field to look at, which is what these do.
 */
export const CONNECTION_FAILURE_HELP: Record<string, string> = {
  unreachable: 'Nothing answered at that host and port. Check the address, the port and whether the service allows this network.',
  authentication_failed: 'The host answered but rejected those credentials. Check the username and password.',
  database_not_found: 'The credentials worked, but that database does not exist on the service. Check the database name.',
};

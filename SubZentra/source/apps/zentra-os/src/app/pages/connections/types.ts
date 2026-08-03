import type { IconName } from '@open-zentra/foundation-icons';

import type { ConnectorLogoName } from './connector-logos';

/** How a Data Source came to exist. Mirrors the connector API's `SourceKind`. */
export type SourceKind = 'connected' | 'uploaded';

/** Mirrors the connector API's `SourceHealth`. */
export type SourceHealth = 'unverified' | 'reachable' | 'unreachable';

/** A registered Data Source, as `GET /v1/connector/sources` returns it. */
export interface SourceResponse {
  readonly data_source_id: string;
  readonly name: string;
  readonly kind: SourceKind;
  readonly health: SourceHealth;
  readonly description?: string | null;
  readonly connection_hint?: string | null;
  readonly created_at?: string | null;
  readonly last_verified_at?: string | null;
  readonly last_harvested_at?: string | null;
  readonly store_sample_values?: boolean;
}

/** Credentials on the way in. Write-only — nothing reads this shape back. */
export interface SourceCredentials {
  readonly host: string;
  readonly port: number;
  readonly database: string;
  readonly username: string;
  readonly password: string;
  readonly secure: boolean;
}

export interface RegisterSourceRequest {
  readonly name: string;
  readonly description?: string | null;
  readonly credentials: SourceCredentials;
  readonly store_sample_values: boolean;
}

/** The groups the picker lays connectors out in. */
export type ConnectorCategory =
  | 'Data warehouses'
  | 'Databases'
  | 'Cloud storage'
  | 'File systems';

/**
 * A connector the picker offers.
 *
 * `available` is the whole distinction that matters: the connector API accepts
 * one credential shape (host/port/database/user/password), so ClickHouse is the
 * only connector that can reach a real source. The rest are named honestly as
 * unbuilt rather than given forms that would post nowhere.
 */
export interface Connector {
  readonly id: string;
  readonly name: string;
  readonly category: ConnectorCategory;
  readonly logo: ConnectorLogoName;
  /** Icon shown on the placeholder config page. */
  readonly icon: IconName;
  readonly available: boolean;
  readonly blurb: string;
}

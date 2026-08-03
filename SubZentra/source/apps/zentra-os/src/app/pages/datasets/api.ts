import { requestJson, type TokenSource } from '../../api';

import type {
  AgentAccessResponse,
  CatalogResponse,
  HarvestResponse,
  TableRowsResponse,
} from './types';

/**
 * The latest catalog for a source.
 *
 * 404 until a harvest has completed, which is a meaningful answer rather than
 * an error: it is how the page tells "nothing discovered yet" from "discovery
 * failed", and the two want different things offered to the reader.
 */
export const latestCatalog = (getToken: TokenSource, dataSourceId: string) =>
  requestJson<CatalogResponse>(
    `/v1/connector/sources/${dataSourceId}/catalog`,
    getToken,
  );

/**
 * Begin discovery. Answers 202 with something to watch.
 *
 * The work is scheduled after the response rather than awaited — relation
 * inference issues a query per candidate pair against someone else's warehouse
 * and will not finish inside a request.
 */
export const startHarvest = (getToken: TokenSource, dataSourceId: string) =>
  requestJson<HarvestResponse>(
    `/v1/connector/sources/${dataSourceId}/harvests`,
    getToken,
    { method: 'POST', body: JSON.stringify({}) },
  );

export const getHarvest = (getToken: TokenSource, harvestRunId: string) =>
  requestJson<HarvestResponse>(`/v1/connector/harvests/${harvestRunId}`, getToken);

/** The most recent runs for a source, newest first. */
export const listHarvests = (getToken: TokenSource, dataSourceId: string) =>
  requestJson<HarvestResponse[]>(
    `/v1/connector/sources/${dataSourceId}/harvests`,
    getToken,
  );

/** Hide or reveal an entire table from the agent system. */
export const setTableAgentAccess = (
  getToken: TokenSource,
  dataSourceId: string,
  tableName: string,
  agentVisible: boolean,
) =>
  requestJson<AgentAccessResponse>(
    `/v1/connector/sources/${dataSourceId}/tables/${encodeURIComponent(tableName)}/agent-access`,
    getToken,
    { method: 'PATCH', body: JSON.stringify({ agent_visible: agentVisible }) },
  );

/**
 * One page of a Source Table's raw rows.
 *
 * 404/503 both mean "not ready yet" here — a table can 404 (not harvested, or
 * renamed since) or 503 (Cube hasn't generated/can't reach its cube yet), and
 * the reader is told the same thing either way; see `rows-page.tsx`.
 */
export const getTableRows = (
  getToken: TokenSource,
  dataSourceId: string,
  tableName: string,
  page: number,
) =>
  requestJson<TableRowsResponse>(
    `/v1/connector/sources/${dataSourceId}/tables/${encodeURIComponent(tableName)}` +
      `/rows?page=${page}`,
    getToken,
  );

/** Hide or reveal one field from the agent system. */
export const setFieldAgentAccess = (
  getToken: TokenSource,
  dataSourceId: string,
  tableName: string,
  fieldName: string,
  agentVisible: boolean,
) =>
  requestJson<AgentAccessResponse>(
    `/v1/connector/sources/${dataSourceId}/tables/${encodeURIComponent(tableName)}` +
      `/fields/${encodeURIComponent(fieldName)}/agent-access`,
    getToken,
    { method: 'PATCH', body: JSON.stringify({ agent_visible: agentVisible }) },
  );

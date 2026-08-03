/**
 * Typed adapters for bridging query-engine hooks with data-layer registry APIs.
 *
 * @module hooks/internal/data-layer-adapters
 */

import {
  isMutationOperation,
  WRITE_OPERATIONS,
  type ApiMutationDescriptor,
  type ApiQueryDescriptor,
  type Operation,
  type WriteOperation,
} from '@open-zentra/foundation-data-model';

type QueryDescriptor = ApiQueryDescriptor;
type MutationDescriptor = ApiMutationDescriptor;

interface ApiDescriptorMap {
  readonly list?: QueryDescriptor;
  readonly get?: QueryDescriptor;
  readonly create?: MutationDescriptor;
  readonly update?: MutationDescriptor;
  readonly delete?: MutationDescriptor;
}

interface TableRegistryLike {
  getTable: (tableName: string) => { readonly api?: ApiDescriptorMap } | undefined;
  getTableNames?: () => ReadonlyArray<string>;
}

/**
 * Resolve list query reference for a table.
 */
export const getListQueryReference = (
  tableRegistry: TableRegistryLike,
  tableName: string,
): QueryDescriptor | undefined => tableRegistry.getTable(tableName)?.api?.list;

/**
 * Resolve get query descriptor for a table.
 */
export const getGetQueryReference = (
  tableRegistry: TableRegistryLike,
  tableName: string,
): QueryDescriptor | undefined => tableRegistry.getTable(tableName)?.api?.get;

/**
 * Return the first available query reference in the registry.
 */
export const getAnyQueryReference = (
  tableRegistry: TableRegistryLike,
): QueryDescriptor | undefined => {
  const tableNames = tableRegistry.getTableNames?.() ?? [];

  for (const tableName of tableNames) {
    const apiDescriptors = tableRegistry.getTable(tableName)?.api;
    if (!apiDescriptors) {
      continue;
    }

    if (apiDescriptors.list) {
      return apiDescriptors.list;
    }

    if (apiDescriptors.get) {
      return apiDescriptors.get;
    }
  }

  return undefined;
};

/**
 * Resolve mutation reference for the given operation.
 */
export const getMutationReference = (
  tableRegistry: TableRegistryLike,
  tableName: string,
  operation: WriteOperation,
): MutationDescriptor | undefined => {
  const apiDescriptors = tableRegistry.getTable(tableName)?.api;
  if (!apiDescriptors) {
    return undefined;
  }

  switch (operation) {
    case WRITE_OPERATIONS.CREATE:
      return apiDescriptors.create;
    case WRITE_OPERATIONS.UPDATE:
      return apiDescriptors.update;
    case WRITE_OPERATIONS.DELETE:
      return apiDescriptors.delete;
    default:
      return undefined;
  }
};

/**
 * Return the first available mutation reference for a table.
 */
export const getAnyMutationReference = (
  tableRegistry: TableRegistryLike,
  tableName: string,
): MutationDescriptor | undefined => {
  const apiDescriptors = tableRegistry.getTable(tableName)?.api;
  if (!apiDescriptors) {
    return undefined;
  }

  return apiDescriptors.create ?? apiDescriptors.update ?? apiDescriptors.delete;
};

/**
 * Return the first available mutation reference in the registry.
 */
export const getAnyMutationReferenceFromRegistry = (
  tableRegistry: TableRegistryLike,
): MutationDescriptor | undefined => {
  const tableNames = tableRegistry.getTableNames?.() ?? [];

  for (const tableName of tableNames) {
    const reference = getAnyMutationReference(tableRegistry, tableName);
    if (reference) {
      return reference;
    }
  }

  return undefined;
};

/**
 * Normalize operation to a concrete mutation operation.
 */
export const resolveMutationOperation = (operation: Operation | undefined): WriteOperation =>
  operation !== undefined && isMutationOperation(operation) ? operation : WRITE_OPERATIONS.CREATE;

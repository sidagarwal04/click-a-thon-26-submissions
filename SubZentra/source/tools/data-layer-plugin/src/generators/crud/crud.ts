import * as path from 'path';

import type { Tree } from '@nx/devkit';
import { formatFiles, generateFiles, names } from '@nx/devkit';

import type { CrudGeneratorSchema } from './schema';

/**
 * Normalized options with computed values
 */
interface NormalizedOptions {
  name: string;
  className: string;
  propertyName: string;
  constantName: string;
  fileName: string;
  directory: string;
  dataModel: string;
  endpoint: string;
  idField: string;
  pagination: boolean;
  skipList: boolean;
  skipDetail: boolean;
  skipCreate: boolean;
  skipUpdate: boolean;
  skipDelete: boolean;
}

/**
 * Normalize generator options
 */
function normalizeOptions(options: CrudGeneratorSchema): NormalizedOptions {
  const entityNames = names(options.name);

  return {
    name: options.name,
    className: entityNames.className,
    propertyName: entityNames.propertyName,
    constantName: entityNames.constantName,
    fileName: entityNames.fileName,
    directory: options.directory,
    dataModel: options.dataModel,
    endpoint: options.endpoint.endsWith('/') ? options.endpoint.slice(0, -1) : options.endpoint,
    idField: options.idField ?? 'id',
    pagination: options.pagination ?? false,
    skipList: options.skipList ?? false,
    skipDetail: options.skipDetail ?? false,
    skipCreate: options.skipCreate ?? false,
    skipUpdate: options.skipUpdate ?? false,
    skipDelete: options.skipDelete ?? false,
  };
}

/**
 * CRUD Data Layer Generator
 *
 * Generates type-safe CRUD hooks for a data entity.
 *
 * @example
 * ```bash
 * nx g @open-zentra/data-layer-plugin:crud product \
 *   --directory=libs/products/data-layer/src \
 *   --dataModel=@open-zentra/products-data-model \
 *   --endpoint=/api/products \
 *   --pagination=true
 * ```
 */
export async function crudGenerator(tree: Tree, options: CrudGeneratorSchema) {
  const normalizedOptions = normalizeOptions(options);

  // Generate files from templates
  generateFiles(tree, path.join(__dirname, 'files'), normalizedOptions.directory, {
    ...normalizedOptions,
    template: '',
  });

  // Remove files based on skip flags
  if (normalizedOptions.skipList) {
    const listPath = `${normalizedOptions.directory}/use-dl-${normalizedOptions.fileName}-list.ts`;
    if (tree.exists(listPath)) {
      tree.delete(listPath);
    }
  }

  if (normalizedOptions.skipDetail) {
    const detailPath = `${normalizedOptions.directory}/use-dl-${normalizedOptions.fileName}.ts`;
    if (tree.exists(detailPath)) {
      tree.delete(detailPath);
    }
  }

  if (normalizedOptions.skipCreate) {
    const createPath = `${normalizedOptions.directory}/use-dl-create-${normalizedOptions.fileName}.ts`;
    if (tree.exists(createPath)) {
      tree.delete(createPath);
    }
  }

  if (normalizedOptions.skipUpdate) {
    const updatePath = `${normalizedOptions.directory}/use-dl-update-${normalizedOptions.fileName}.ts`;
    if (tree.exists(updatePath)) {
      tree.delete(updatePath);
    }
  }

  if (normalizedOptions.skipDelete) {
    const deletePath = `${normalizedOptions.directory}/use-dl-delete-${normalizedOptions.fileName}.ts`;
    if (tree.exists(deletePath)) {
      tree.delete(deletePath);
    }
  }

  // Update index.ts exports based on what was generated
  updateIndexFile(tree, normalizedOptions);

  await formatFiles(tree);
}

/**
 * Update the index.ts file with correct exports
 */
function updateIndexFile(tree: Tree, options: NormalizedOptions): void {
  const indexPath = `${options.directory}/index.ts`;

  const exports: string[] = [
    `export { ${options.propertyName}Keys } from './${options.fileName}-keys';`,
  ];

  if (!options.skipDetail) {
    exports.push(
      `export { useDLGet${options.className}Query } from './use-dl-${options.fileName}';`,
    );
  }

  if (!options.skipList) {
    exports.push(
      `export { useDLGet${options.className}ListQuery } from './use-dl-${options.fileName}-list';`,
    );
  }

  if (!options.skipCreate) {
    exports.push(
      `export { useDLCreate${options.className} } from './use-dl-create-${options.fileName}';`,
    );
  }

  if (!options.skipUpdate) {
    exports.push(
      `export { useDLUpdate${options.className} } from './use-dl-update-${options.fileName}';`,
    );
  }

  if (!options.skipDelete) {
    exports.push(
      `export { useDLDelete${options.className} } from './use-dl-delete-${options.fileName}';`,
    );
  }

  const content = `/**
 * ${options.className} Data Layer Hooks
 *
 * Auto-generated CRUD hooks for ${options.name} entity.
 */

${exports.join('\n')}
`;

  tree.write(indexPath, content);
}

export default crudGenerator;

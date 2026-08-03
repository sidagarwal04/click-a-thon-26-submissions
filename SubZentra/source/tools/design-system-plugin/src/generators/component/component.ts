import * as path from 'path';

import type { Tree } from '@nx/devkit';
import { formatFiles, generateFiles, names } from '@nx/devkit';

import type { ComponentGeneratorSchema } from './schema';

const DESIGN_SYSTEM_ROOT = 'libs/foundation/design-system/src';

interface ParsedVariant {
  name: string;
  values: string[];
}

interface NormalizedOptions {
  name: string;
  className: string;
  propertyName: string;
  constantName: string;
  fileName: string;
  variants: ParsedVariant[];
  modifiers: string[];
  slots: string[];
  rootElement: string;
  useBaseUI: boolean;
  baseUIPrimitive: string | undefined;
  isCompound: boolean;
  isPublic: boolean;
  supportsPolymorphism: boolean;
  directory: string | undefined;
  skipTests: boolean;
  skipStory: boolean;
  rootInstanceOf: string;
  hasVariants: boolean;
  hasModifiers: boolean;
  hasSlots: boolean;
}

/**
 * Parse variants string like "intent:primary,secondary size:sm,md,lg"
 */
function parseVariants(variantsStr: string | undefined): ParsedVariant[] {
  if (!variantsStr) return [];

  return variantsStr
    .split(/\s+/)
    .filter(Boolean)
    .map((variantDef) => {
      const [name, valuesStr] = variantDef.split(':');
      const values = valuesStr ? valuesStr.split(',').filter(Boolean) : [];
      return { name: name.trim(), values };
    });
}

/**
 * Parse comma-separated list
 */
function parseList(str: string | undefined): string[] {
  if (!str) return [];
  return str
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Get root element instance type
 */
function getRootInstanceOf(rootElement: string): string {
  const elementMap: Record<string, string> = {
    div: 'HTMLDivElement',
    span: 'HTMLSpanElement',
    button: 'HTMLButtonElement',
    input: 'HTMLInputElement',
    label: 'HTMLLabelElement',
    a: 'HTMLAnchorElement',
    section: 'HTMLElement',
    article: 'HTMLElement',
    header: 'HTMLElement',
    footer: 'HTMLElement',
    nav: 'HTMLElement',
    aside: 'HTMLElement',
    main: 'HTMLElement',
  };
  return elementMap[rootElement] || 'HTMLElement';
}

/**
 * Normalize generator options
 */
function normalizeOptions(options: ComponentGeneratorSchema): NormalizedOptions {
  const componentNames = names(options.name);
  const variants = parseVariants(options.variants);
  const modifiers = parseList(options.modifiers);
  const slots = parseList(options.slots);
  const rootElement = options.rootElement || 'div';

  return {
    name: options.name,
    className: componentNames.className,
    propertyName: componentNames.propertyName,
    constantName: componentNames.constantName,
    fileName: componentNames.fileName,
    variants,
    modifiers,
    slots,
    rootElement,
    useBaseUI: options.useBaseUI ?? false,
    baseUIPrimitive: options.baseUIPrimitive,
    isCompound: options.isCompound ?? false,
    isPublic: options.isPublic ?? true,
    supportsPolymorphism: options.supportsPolymorphism ?? true,
    directory: options.directory,
    skipTests: options.skipTests ?? false,
    skipStory: options.skipStory ?? false,
    rootInstanceOf: getRootInstanceOf(rootElement),
    hasVariants: variants.length > 0,
    hasModifiers: modifiers.length > 0,
    hasSlots: slots.length > 0,
  };
}

/**
 * Update the components index.ts to export the new component
 */
function updateComponentsIndex(tree: Tree, normalizedOptions: NormalizedOptions): void {
  const indexPath = `${DESIGN_SYSTEM_ROOT}/components/index.ts`;
  const { fileName, isPublic } = normalizedOptions;

  if (!isPublic) return;

  let content = tree.read(indexPath)?.toString() || '';
  const exportStatement = `export * from './${
    normalizedOptions.directory ? `${normalizedOptions.directory}/` : ''
  }${fileName}';\n`;

  if (!content.includes(exportStatement)) {
    content += exportStatement;
    tree.write(indexPath, content);
  }
}

export async function componentGenerator(tree: Tree, options: ComponentGeneratorSchema) {
  const normalizedOptions = normalizeOptions(options);
  const componentDir = normalizedOptions.directory
    ? `${DESIGN_SYSTEM_ROOT}/components/${normalizedOptions.directory}/${normalizedOptions.fileName}`
    : `${DESIGN_SYSTEM_ROOT}/components/${normalizedOptions.fileName}`;

  // Generate template variables - pass the raw data to templates
  const templateOptions = {
    ...normalizedOptions,
    template: '',
  };

  // Generate files from templates
  generateFiles(tree, path.join(__dirname, 'files'), componentDir, templateOptions);

  // Remove test file if skipTests
  if (normalizedOptions.skipTests) {
    const testPath = `${componentDir}/${normalizedOptions.fileName}.spec.tsx`;
    if (tree.exists(testPath)) {
      tree.delete(testPath);
    }
  }

  // Remove story file if skipStory
  if (normalizedOptions.skipStory) {
    const storyPath = `${componentDir}/${normalizedOptions.fileName}.stories.tsx`;
    if (tree.exists(storyPath)) {
      tree.delete(storyPath);
    }
  }

  // Update components index
  updateComponentsIndex(tree, normalizedOptions);

  await formatFiles(tree);
}

export default componentGenerator;

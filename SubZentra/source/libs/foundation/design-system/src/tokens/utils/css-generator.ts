/**
 * CSS Variable Generator
 * Transforms TypeScript tokens to CSS custom properties
 * @module tokens/utils/css-generator
 */

import type { DesignToken } from '../types';
import { isDesignToken } from '../types';

/**
 * Options for CSS generation
 */
export interface CSSGeneratorOptions {
  /** Prefix for CSS variable names (e.g., 'oi' -> '--oi-color-primary') */
  prefix?: string;
  /** Indentation string (default: '  ') */
  indent?: string;
  /** Whether to include comments from $description (default: true) */
  includeComments?: boolean;
  /** Whether to include deprecated tokens (default: true) */
  includeDeprecated?: boolean;
}

/**
 * Generates CSS custom properties from a token object
 *
 * @param tokens - Token object (can be nested)
 * @param prefix - Current prefix for nesting
 * @param options - Generation options
 * @returns Array of CSS variable declarations
 *
 * @example
 * const vars = generateCSSVariables(colorPrimitives.neutral, 'color-neutral');
 * // ['--color-neutral-100: hsl(228 6% 90%);', ...]
 */
export function generateCSSVariables(
  tokens: Record<string, unknown>,
  prefix = '',
  options: CSSGeneratorOptions = {},
): string[] {
  const { indent = '  ', includeComments = true, includeDeprecated = true } = options;

  const lines: string[] = [];

  for (const [key, value] of Object.entries(tokens)) {
    // Skip internal properties
    if (key.startsWith('$')) continue;

    const varName = prefix ? `--${prefix}-${key}` : `--${key}`;

    if (isDesignToken(value)) {
      // Skip deprecated if configured
      if (value.$deprecated && !includeDeprecated) continue;

      // Add comment if available and enabled
      if (includeComments && value.$description) {
        lines.push(`${indent}/* ${value.$description} */`);
      }

      // Add deprecation warning
      if (value.$deprecated) {
        const msg =
          typeof value.$deprecated === 'string' ? value.$deprecated : 'This token is deprecated';
        lines.push(`${indent}/* @deprecated ${msg} */`);
      }

      lines.push(`${indent}${varName}: ${value.$value};`);
    } else if (typeof value === 'object' && value !== null) {
      // Recurse into nested objects
      const nestedVars = generateCSSVariables(
        value as Record<string, unknown>,
        prefix ? `${prefix}-${key}` : key,
        { ...options, indent },
      );
      lines.push(...nestedVars);
    }
  }

  return lines;
}

/**
 * Generates a complete CSS file content from theme tokens
 *
 * @param theme - Theme token object
 * @param selector - CSS selector for the variables (default: ':root')
 * @param options - Generation options
 * @returns Complete CSS string
 *
 * @example
 * const css = generateThemeCSS(darkTheme.colors, ':root', { prefix: 'oi' });
 */
export function generateThemeCSS(
  theme: Record<string, unknown>,
  selector = ':root',
  options: CSSGeneratorOptions = {},
): string {
  const { prefix } = options;
  const variables = generateCSSVariables(theme, prefix, options);

  return `${selector} {\n${variables.join('\n')}\n}`;
}

/**
 * Generates CSS for multiple themes/selectors
 *
 * @param themes - Array of theme configurations
 * @returns Complete CSS string with all themes
 *
 * @example
 * const css = generateMultiThemeCSS([
 *   { selector: ':root', tokens: darkTheme, prefix: 'oi' },
 *   { selector: '.light, [data-theme="light"]', tokens: lightTheme, prefix: 'oi' },
 * ]);
 */
export function generateMultiThemeCSS(
  themes: Array<{
    selector: string;
    tokens: Record<string, unknown>;
    prefix?: string;
    options?: CSSGeneratorOptions;
  }>,
): string {
  const blocks = themes.map(({ selector, tokens, prefix, options = {} }) =>
    generateThemeCSS(tokens, selector, { ...options, prefix }),
  );

  return blocks.join('\n\n');
}

/**
 * Generates CSS variable reference string
 * Useful for building values that reference other tokens
 *
 * @param tokenPath - Dot-notated path to token
 * @param prefix - Optional prefix
 * @returns CSS var() reference
 *
 * @example
 * const ref = cssVar('colors.background.layer01', 'oi');
 * // 'var(--oi-colors-background-layer01)'
 */
export function cssVar(tokenPath: string, prefix?: string): string {
  const varName = tokenPath.replace(/\./g, '-');
  const fullName = prefix ? `${prefix}-${varName}` : varName;
  return `var(--${fullName})`;
}

/**
 * Generates CSS variable reference with fallback
 *
 * @param tokenPath - Dot-notated path to token
 * @param fallback - Fallback value
 * @param prefix - Optional prefix
 * @returns CSS var() reference with fallback
 */
export function cssVarWithFallback(tokenPath: string, fallback: string, prefix?: string): string {
  const varName = tokenPath.replace(/\./g, '-');
  const fullName = prefix ? `${prefix}-${varName}` : varName;
  return `var(--${fullName}, ${fallback})`;
}

/**
 * Generates Tailwind CSS @theme directive content
 * Compatible with Tailwind CSS v4
 *
 * @param tokens - Token object
 * @param options - Generation options
 * @returns CSS content for @theme directive
 */
export function generateTailwindTheme(
  tokens: Record<string, unknown>,
  options: CSSGeneratorOptions = {},
): string {
  const variables = generateCSSVariables(tokens, options.prefix, {
    ...options,
    indent: '  ',
  });

  return `@theme {\n${variables.join('\n')}\n}`;
}

/**
 * Generates media query wrapper for reduced motion
 *
 * @param durationTokens - Duration token object
 * @param prefix - Optional prefix
 * @returns CSS media query block
 */
export function generateReducedMotionCSS(
  durationTokens: Record<string, DesignToken<string>>,
  prefix?: string,
): string {
  const lines: string[] = [];

  for (const [key, token] of Object.entries(durationTokens)) {
    if (token.$type === 'duration') {
      const varName = prefix ? `--${prefix}-${key}` : `--${key}`;
      lines.push(`  ${varName}: 0ms;`);
    }
  }

  return `@media (prefers-reduced-motion: reduce) {\n  :root {\n${lines.join('\n')}\n  }\n}`;
}

/**
 * Generates CSS comment header for generated files
 *
 * @param options - Header options
 * @returns CSS comment string
 */
export function generateFileHeader(options?: {
  title?: string;
  description?: string;
  generated?: boolean;
}): string {
  const {
    title = 'Design Tokens',
    description = 'Auto-generated from TypeScript token definitions',
    generated = true,
  } = options ?? {};

  const lines = ['/**', ` * ${title}`, ` * ${description}`];

  if (generated) {
    lines.push(' * @generated - DO NOT EDIT DIRECTLY');
    lines.push(` * Generated at: ${new Date().toISOString()}`);
  }

  lines.push(' */');

  return lines.join('\n');
}

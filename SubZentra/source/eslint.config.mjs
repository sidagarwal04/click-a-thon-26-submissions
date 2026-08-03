// eslint.config.mjs
// Open Zentra Monorepo — Enterprise ESLint Governance
//
// Architecture: 5 orthogonal tag dimensions (layer, foundation, platform, scope, visibility).
// All constraints use AND semantics — a project must satisfy ALL matching rules.
// Adding a non-foundation project requires ZERO changes to this file.
// Adding a foundation project requires ONE new FOUNDATION_DAG entry.

import nx from '@nx/eslint-plugin';
import unusedImports from 'eslint-plugin-unused-imports';

// ==================================================================
// COMPOSABLE CONSTRAINT DEFINITIONS
// Each dimension defined once, shared between production and test.
// ==================================================================

/**
 * DIMENSION 1: Layer Hierarchy
 * Controls vertical dependency direction between architectural layers.
 */
const LAYER_CONSTRAINTS = [
  // Frontend apps: compose products, features, shared, and foundation.
  // Cannot import other apps (compose via routing, not imports).
  {
    sourceTag: 'layer:app',
    onlyDependOnLibsWithTags: [
      'layer:product',
      'layer:feature',
      'layer:shared',
      'layer:foundation',
      'layer:domain',
      'layer:application',
      'layer:adapter',
    ],
  },
  // Backend services + gateway: depend on shared contracts and foundation only.
  // Cannot import other services (communicate via network, not imports).
  // Cannot import product/feature (those are frontend composition layers).
  {
    sourceTag: 'layer:service',
    onlyDependOnLibsWithTags: [
      'layer:shared',
      'layer:foundation',
      'layer:domain',
      'layer:application',
      'layer:adapter',
    ],
  },
  {
    sourceTag: 'layer:domain',
    onlyDependOnLibsWithTags: ['layer:domain'],
  },
  {
    sourceTag: 'layer:application',
    onlyDependOnLibsWithTags: ['layer:domain', 'layer:application'],
  },
  {
    sourceTag: 'layer:adapter',
    onlyDependOnLibsWithTags: ['layer:domain', 'layer:adapter'],
  },
  {
    sourceTag: 'layer:product',
    onlyDependOnLibsWithTags: ['layer:feature', 'layer:shared', 'layer:foundation'],
  },
  {
    sourceTag: 'layer:feature',
    onlyDependOnLibsWithTags: ['layer:shared', 'layer:foundation'],
  },
  {
    sourceTag: 'layer:shared',
    onlyDependOnLibsWithTags: ['layer:shared', 'layer:foundation'],
  },
  {
    sourceTag: 'layer:foundation',
    onlyDependOnLibsWithTags: ['layer:foundation'],
  },
  {
    sourceTag: 'layer:tool',
    onlyDependOnLibsWithTags: ['layer:tool'],
  },
];

/**
 * DIMENSION 2: Foundation DAG
 * Intra-layer dependency graph for foundation libraries.
 * ONLY section that changes when adding a new foundation lib.
 *
 * Tiers:
 *   T0: data-model (leaf — zero deps)
 *   T1: utils, trackers
 *   T2: adapters, database, hooks, icons, auth, http
 *   T3: sync-engine
 *   T4: bridge
 *   T5: data-layer, design-system, metrics
 *   T6: query-engine
 *   Special: mocks (depends on all foundation:*)
 */
const FOUNDATION_DAG_CONSTRAINTS = [
  // T0
  {
    sourceTag: 'foundation:data-model',
    onlyDependOnLibsWithTags: ['foundation:data-model'],
  },
  // T1
  {
    sourceTag: 'foundation:utils',
    onlyDependOnLibsWithTags: ['foundation:utils', 'foundation:data-model'],
  },
  {
    sourceTag: 'foundation:trackers',
    onlyDependOnLibsWithTags: ['foundation:trackers', 'foundation:data-model'],
  },
  // T2
  {
    sourceTag: 'foundation:adapters',
    onlyDependOnLibsWithTags: [
      'foundation:adapters',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
    ],
  },
  {
    sourceTag: 'foundation:database',
    onlyDependOnLibsWithTags: [
      'foundation:database',
      'foundation:data-model',
      'foundation:utils',
      'foundation:trackers',
    ],
  },
  {
    sourceTag: 'foundation:hooks',
    onlyDependOnLibsWithTags: [
      'foundation:hooks',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
    ],
  },
  {
    sourceTag: 'foundation:icons',
    onlyDependOnLibsWithTags: [
      'foundation:icons',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
    ],
  },
  {
    sourceTag: 'foundation:auth',
    onlyDependOnLibsWithTags: ['foundation:auth', 'foundation:utils', 'foundation:data-model'],
  },
  {
    sourceTag: 'foundation:http',
    onlyDependOnLibsWithTags: [
      'foundation:http',
      'foundation:auth',
      'foundation:utils',
      'foundation:data-model',
    ],
  },
  // T3
  {
    sourceTag: 'foundation:sync-engine',
    onlyDependOnLibsWithTags: [
      'foundation:sync-engine',
      'foundation:database',
      'foundation:data-model',
      'foundation:utils',
      'foundation:trackers',
    ],
  },
  // T4
  {
    sourceTag: 'foundation:bridge',
    onlyDependOnLibsWithTags: [
      'foundation:bridge',
      'foundation:sync-engine',
      'foundation:database',
      'foundation:data-model',
      'foundation:utils',
      'foundation:trackers',
    ],
  },
  // T5
  {
    sourceTag: 'foundation:data-layer',
    onlyDependOnLibsWithTags: [
      'foundation:data-layer',
      'foundation:sync-engine',
      'foundation:bridge',
      'foundation:database',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
      'foundation:hooks',
      'foundation:auth',
    ],
  },
  {
    sourceTag: 'foundation:design-system',
    onlyDependOnLibsWithTags: [
      'foundation:design-system',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
      'foundation:icons',
    ],
  },
  {
    sourceTag: 'foundation:metrics',
    onlyDependOnLibsWithTags: [
      'foundation:metrics',
      'foundation:utils',
      'foundation:data-model',
      'foundation:trackers',
      'foundation:http',
    ],
  },
  // T6
  {
    sourceTag: 'foundation:query-engine',
    onlyDependOnLibsWithTags: [
      'foundation:query-engine',
      'foundation:data-layer',
      'foundation:bridge',
      'foundation:data-model',
      'foundation:utils',
    ],
  },
  // Special: mocks can depend on any foundation lib (glob pattern)
  {
    sourceTag: 'foundation:mocks',
    onlyDependOnLibsWithTags: ['foundation:*'],
  },
];

/**
 * DIMENSION 3: Platform Compatibility
 * Prevents importing runtime-incompatible code.
 * Hierarchy: universal < browser < react (superset chain)
 * Node is a separate branch from browser/react.
 * platform:any has no sourceTag rule = unconstrained.
 */
const PLATFORM_CONSTRAINTS = [
  {
    sourceTag: 'platform:universal',
    onlyDependOnLibsWithTags: ['platform:universal', 'platform:any'],
  },
  {
    sourceTag: 'platform:browser',
    onlyDependOnLibsWithTags: ['platform:universal', 'platform:browser', 'platform:any'],
  },
  {
    sourceTag: 'platform:react',
    onlyDependOnLibsWithTags: [
      'platform:universal',
      'platform:browser',
      'platform:react',
      'platform:any',
    ],
  },
  {
    sourceTag: 'platform:node',
    onlyDependOnLibsWithTags: ['platform:universal', 'platform:node', 'platform:any'],
  },
  {
    sourceTag: 'platform:python',
    onlyDependOnLibsWithTags: ['platform:python'],
  },
];

/**
 * DIMENSION 5: Visibility (production only)
 * Prevents production code from importing internal-only libs (mocks, tools).
 * Uses notDependOnLibsWithTags which also checks transitive deps.
 * OMITTED from test context so tests can import mocks.
 */
const VISIBILITY_CONSTRAINTS = [
  {
    sourceTag: 'layer:foundation',
    notDependOnLibsWithTags: ['visibility:internal'],
  },
  {
    sourceTag: 'layer:shared',
    notDependOnLibsWithTags: ['visibility:internal'],
  },
  {
    sourceTag: 'layer:feature',
    notDependOnLibsWithTags: ['visibility:internal'],
  },
  {
    sourceTag: 'layer:product',
    notDependOnLibsWithTags: ['visibility:internal'],
  },
  {
    sourceTag: 'layer:service',
    notDependOnLibsWithTags: ['visibility:internal'],
  },
];

// ==================================================================
// ESLINT FLAT CONFIG
// ==================================================================

export default [
  // ================================================================
  // JSON FILE SUPPORT
  // ================================================================
  {
    files: ['**/*.json'],
    rules: {},
    languageOptions: {
      parser: await import('jsonc-eslint-parser'),
    },
  },

  // ================================================================
  // NX BASE CONFIGS
  // ================================================================
  ...nx.configs['flat/base'],
  ...nx.configs['flat/typescript'],
  ...nx.configs['flat/javascript'],

  // ================================================================
  // GLOBAL IGNORES
  // ================================================================
  {
    ignores: [
      '**/dist',
      // The e2e bundle. Linting minified output reports hundreds of
      // no-var/prefer-const errors about code nobody wrote.
      '**/dist-e2e',
      '**/storybook-static',
      '**/coverage',
      '**/.nx',
      '**/.turbo',
      '**/.next',
      '**/tmp',
      '**/vite.config.*.timestamp*',
      '**/vitest.config.*.timestamp*',
      '**/test-output',
      '**/out-tsc',
    ],
  },

  // ================================================================
  // PRODUCTION CODE: Module boundaries + type imports
  // ================================================================
  {
    files: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx'],
    rules: {
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {
          prefer: 'type-imports',
          disallowTypeAnnotations: true,
          fixStyle: 'separate-type-imports',
        },
      ],
      '@nx/enforce-module-boundaries': [
        'error',
        {
          allow: ['^.*/eslint(\\.base)?\\.config\\.[cm]?[jt]s$', '^@open-zentra/foundation-auth$'],
          depConstraints: [
            ...LAYER_CONSTRAINTS,
            ...FOUNDATION_DAG_CONSTRAINTS,
            ...PLATFORM_CONSTRAINTS,
            ...VISIBILITY_CONSTRAINTS,
          ],
        },
      ],
    },
  },

  // ================================================================
  // TEST FILES: Relaxed visibility (can import mocks),
  //             all other dimensions still enforced.
  // Note: In flat config, this block REPLACES the production
  // enforce-module-boundaries rule for test files (last-match-wins).
  // Therefore we must re-declare all dimensions except visibility.
  // ================================================================
  {
    files: [
      '**/*.spec.ts',
      '**/*.spec.tsx',
      '**/*.test.ts',
      '**/*.test.tsx',
      '**/test/**/*.ts',
      '**/test/**/*.tsx',
      '**/__tests__/**/*.ts',
      '**/__tests__/**/*.tsx',
      '**/testing/**/*.ts',
      '**/testing/**/*.tsx',
    ],
    rules: {
      'no-undef': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@nx/enforce-module-boundaries': [
        'error',
        {
          enforceBuildableLibDependency: false,
          allow: ['^.*/eslint(\\.base)?\\.config\\.[cm]?[jt]s$', '^@open-zentra/foundation-auth$'],
          depConstraints: [
            ...LAYER_CONSTRAINTS,
            ...FOUNDATION_DAG_CONSTRAINTS,
            ...PLATFORM_CONSTRAINTS,
            // VISIBILITY_CONSTRAINTS intentionally omitted:
            // test files may import visibility:internal libs (mocks)
          ],
        },
      ],
    },
  },

  // ================================================================
  // UNUSED IMPORTS
  // ================================================================
  {
    files: [
      '**/*.ts',
      '**/*.tsx',
      '**/*.cts',
      '**/*.mts',
      '**/*.js',
      '**/*.jsx',
      '**/*.cjs',
      '**/*.mjs',
    ],
    plugins: {
      'unused-imports': unusedImports,
    },
    rules: {
      'no-unused-vars': 'off',
      'unused-imports/no-unused-imports': 'error',
      'unused-imports/no-unused-vars': [
        'warn',
        {
          vars: 'all',
          varsIgnorePattern: '^_',
          args: 'after-used',
          argsIgnorePattern: '^_',
        },
      ],
    },
  },
];

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { DATA_FRESHNESS, OPERATIONS } from '@open-zentra/foundation-data-model';

import type { DecisionContext, DecisionTableConfig } from '../types/decision';
import { DECISION_REASONS } from '../types/decision';
import type { Query } from '../types/query';
import type { DecisionEngine } from './decision-engine';
import { createDecisionEngine, getDecisionEngine, resetDecisionEngine } from './decision-engine';

// =============================================================================
// HELPERS
// =============================================================================

const makeContext = (overrides: Partial<DecisionContext> = {}): DecisionContext => ({
  tables: ['users'],
  operation: OPERATIONS.LIST,
  tableConfigs: new Map<string, DecisionTableConfig>([
    [
      'users',
      {
        source: 'api',
        api: {
          list: {} as unknown,
          get: {} as unknown,
          create: {} as unknown,
          update: {} as unknown,
          delete: {} as unknown,
        },
      },
    ],
  ]),
  isOnline: true,
  ...overrides,
});

const simpleQuery: Query = {
  dimensions: [{ member: 'users.name' }],
};

// =============================================================================
// DecisionEngine
// =============================================================================

describe('DecisionEngine', () => {
  let engine: DecisionEngine;

  beforeEach(() => {
    engine = createDecisionEngine();
  });

  afterEach(() => {
    engine.dispose();
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 1: Mutations → API
  // ───────────────────────────────────────────────────────────────────────────

  it('routes mutations to API', () => {
    const ctx = makeContext({ operation: OPERATIONS.CREATE });
    const result = engine.decide(simpleQuery, ctx);

    expect(result.path).toBe('api');
    expect(result.reason).toBe(DECISION_REASONS.MUTATION_USES_API);
    expect(result.confidence).toBe(100);
    expect(result.apiFunction).toBe(OPERATIONS.CREATE);
  });

  it('warns when mutation API is not defined', () => {
    const ctx = makeContext({
      operation: OPERATIONS.DELETE,
      tableConfigs: new Map([['users', { source: 'api', api: { list: {} as unknown } }]]),
    });

    const result = engine.decide(simpleQuery, ctx);
    expect(result.path).toBe('api');
    expect(result.reason).toBe(DECISION_REASONS.NO_MUTATION_API);
    expect(result.confidence).toBe(0);
    expect(result.warnings).toBeDefined();
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 2: Has joins → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('routes queries with joins to DuckDB', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
    };
    const ctx = makeContext({ tables: ['users', 'orders'] });
    const result = engine.decide(query, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.HAS_JOINS);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 3: Has measures → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('routes queries with measures to DuckDB', () => {
    const query: Query = {
      measures: [{ member: 'users.id', aggregation: 'count' }],
    };
    const ctx = makeContext();
    const result = engine.decide(query, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.HAS_MEASURES);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 4: Multiple tables → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('routes multi-table queries to DuckDB', () => {
    const ctx = makeContext({
      tables: ['users', 'orders'],
      tableConfigs: new Map([
        ['users', { source: 'api', api: { list: {} as unknown } }],
        ['orders', { source: 'api', api: { list: {} as unknown } }],
      ]),
    });
    const result = engine.decide(simpleQuery, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.MULTIPLE_TABLES);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 5: Local-only table → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('routes local-only tables to DuckDB', () => {
    const ctx = makeContext({
      tableConfigs: new Map([['users', { source: 'local' }]]),
    });
    const result = engine.decide(simpleQuery, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.LOCAL_TABLE);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 6: No list API → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('routes to DuckDB when no list API is defined', () => {
    const ctx = makeContext({
      tableConfigs: new Map([['users', { source: 'api' }]]),
    });
    const result = engine.decide(simpleQuery, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.NO_LIST_API);
  });

  it('routes GET to DuckDB when no get or list API exists', () => {
    const query: Query = { dimensions: [{ member: 'users.name' }], entityId: '123' };
    const ctx = makeContext({
      operation: OPERATIONS.GET,
      tableConfigs: new Map([['users', { source: 'api' }]]),
    });
    const result = engine.decide(query, ctx);

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.NO_API_AVAILABLE);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Rule 7: Analytics preference → DuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('prefers analytics path when option set and freshness is eventual', () => {
    const ctx = makeContext({
      // Typed like the map at the top of this file, so the literal is checked
      // against DecisionTableConfig rather than widened to its own shape.
      tableConfigs: new Map<string, DecisionTableConfig>([
        [
          'users',
          {
            source: 'api',
            api: { list: {} as unknown },
            analytics: { freshness: DATA_FRESHNESS.EVENTUAL },
          },
        ],
      ]),
    });
    const result = engine.decide(simpleQuery, ctx, { preferAnalytics: true });

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.ANALYTICS_PREFERRED);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Default: Simple query → API
  // ───────────────────────────────────────────────────────────────────────────

  it('defaults to API for simple single-table queries', () => {
    const ctx = makeContext();
    const result = engine.decide(simpleQuery, ctx);

    expect(result.path).toBe('api');
    expect(result.reason).toBe(DECISION_REASONS.SIMPLE_QUERY_WITH_API);
    expect(result.apiFunction).toBe(OPERATIONS.LIST);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // forcePath
  // ───────────────────────────────────────────────────────────────────────────

  it('honours forcePath option', () => {
    const ctx = makeContext();
    const result = engine.decide(simpleQuery, ctx, { forcePath: 'duckdb' });

    expect(result.path).toBe('duckdb');
    expect(result.reason).toBe(DECISION_REASONS.FORCED_PATH);
    expect(result.confidence).toBe(100);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // includeFactors
  // ───────────────────────────────────────────────────────────────────────────

  it('includes factors when requested', () => {
    const ctx = makeContext();
    const result = engine.decide(simpleQuery, ctx, { includeFactors: true });

    expect(result.factors).toBeDefined();
    expect(result.factors?.isMutation).toBe(false);
    expect(result.factors?.hasJoins).toBe(false);
    expect(result.factors?.tableCount).toBe(1);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // canUseApi
  // ───────────────────────────────────────────────────────────────────────────

  it('canUseApi returns true for simple query', () => {
    const ctx = makeContext();
    expect(engine.canUseApi(simpleQuery, ctx)).toBe(true);
  });

  it('canUseApi returns false for query with joins', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
    };
    expect(engine.canUseApi(query, makeContext())).toBe(false);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // requiresDuckDB
  // ───────────────────────────────────────────────────────────────────────────

  it('requiresDuckDB returns true when measures present', () => {
    const query: Query = {
      measures: [{ member: 'users.id', aggregation: 'count' }],
    };
    expect(engine.requiresDuckDB(query)).toBe(true);
  });

  it('requiresDuckDB returns false for simple query', () => {
    expect(engine.requiresDuckDB(simpleQuery)).toBe(false);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Disposed state
  // ───────────────────────────────────────────────────────────────────────────

  it('throws after disposal', () => {
    engine.dispose();
    expect(engine.isDisposed).toBe(true);
    expect(() => engine.decide(simpleQuery, makeContext())).toThrow();
  });
});

// =============================================================================
// Singleton factory
// =============================================================================

describe('getDecisionEngine / resetDecisionEngine', () => {
  afterEach(async () => {
    await resetDecisionEngine();
  });

  it('returns the same instance on repeated calls', () => {
    const a = getDecisionEngine();
    const b = getDecisionEngine();
    expect(a).toBe(b);
  });

  it('returns a new instance after reset', async () => {
    const a = getDecisionEngine();
    await resetDecisionEngine();
    const b = getDecisionEngine();
    expect(a).not.toBe(b);
  });
});

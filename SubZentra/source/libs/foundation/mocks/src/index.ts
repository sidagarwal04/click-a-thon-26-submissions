/**
 * Foundation Mocks
 *
 * Test utilities, builders, and mock data generators for foundation libraries.
 *
 * @module foundation-mocks
 *
 * @example
 * ```typescript
 * import {
 *   QueryBuilder,
 *   MutationBuilder,
 *   TestData,
 *   quickQuery,
 *   quickMutation,
 * } from '@open-zentra/foundation-mocks';
 *
 * // Build a test query
 * const query = QueryBuilder.create()
 *   .withTable('events')
 *   .withMeasure('count', 'count')
 *   .withDimension('browser')
 *   .withFilter('country', 'equals', 'US')
 *   .build();
 *
 * // Build a test mutation
 * const mutation = MutationBuilder.create()
 *   .ofType('create')
 *   .forTable('users')
 *   .withData({ name: 'John' })
 *   .build();
 *
 * // Generate test data
 * const user = TestData.user({ role: 'admin' });
 * const events = TestData.events(10, { userId: user.id });
 * ```
 */

export * from './builders';

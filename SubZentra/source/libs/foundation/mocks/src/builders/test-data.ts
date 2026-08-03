/**
 * Test Data Factory
 *
 * Provides utilities for generating test data with realistic values.
 *
 * @module builders/test-data
 */

import {
  EntityId,
  Milliseconds,
  ProvisionalId,
  Timestamp,
  type UserRole,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// Random Value Generators
// =============================================================================

/**
 * Generate a random string of specified length
 */
export function randomString(length = 8): string {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Generate a random integer between min and max (inclusive)
 */
export function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Generate a random float between min and max
 */
export function randomFloat(min: number, max: number, decimals = 2): number {
  const value = Math.random() * (max - min) + min;
  return parseFloat(value.toFixed(decimals));
}

/**
 * Generate a random boolean
 */
export function randomBoolean(): boolean {
  return Math.random() > 0.5;
}

/**
 * Pick a random element from an array
 */
export function randomElement<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Pick multiple random elements from an array
 */
export function randomElements<T>(arr: readonly T[], count: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, Math.min(count, arr.length));
}

/**
 * Generate a random email address
 */
export function randomEmail(domain = 'test.com'): string {
  return `user_${randomString(6)}@${domain}`;
}

/**
 * Generate a random URL
 */
export function randomUrl(base = 'https://example.com'): string {
  return `${base}/${randomString(8)}`;
}

/**
 * Generate a random timestamp within a range
 */
export function randomTimestamp(
  start = Date.now() - 30 * 24 * 60 * 60 * 1000, // 30 days ago
  end = Date.now(),
): Timestamp {
  return Timestamp.from(randomInt(start, end));
}

/**
 * Generate a random duration in milliseconds
 */
export function randomDuration(min = 100, max = 10000): Milliseconds {
  return Milliseconds.from(randomInt(min, max));
}

// =============================================================================
// Test Entity Generators
// =============================================================================

/**
 * User test data
 */
export interface TestUser {
  readonly id: EntityId;
  readonly email: string;
  readonly name: string;
  readonly role: UserRole;
  readonly status: 'active' | 'inactive' | 'pending';
  readonly createdAt: Timestamp;
  readonly updatedAt: Timestamp;
}

/**
 * Generate a test user
 */
export function generateUser(overrides: Partial<TestUser> = {}): TestUser {
  const now = Timestamp.now();
  return {
    id: overrides.id ?? EntityId.from(`user_${randomString(8)}`),
    email: overrides.email ?? randomEmail(),
    name: overrides.name ?? `User ${randomString(4)}`,
    role: overrides.role ?? randomElement(['owner', 'admin', 'member', 'viewer', 'guest'] as const),
    status: overrides.status ?? randomElement(['active', 'inactive', 'pending'] as const),
    createdAt: overrides.createdAt ?? now,
    updatedAt: overrides.updatedAt ?? now,
  };
}

/**
 * Event test data
 */
export interface TestEvent {
  readonly id: EntityId;
  readonly type: string;
  readonly userId: EntityId;
  readonly sessionId: EntityId;
  readonly properties: Record<string, unknown>;
  readonly timestamp: Timestamp;
}

/**
 * Event types for test data
 */
export const TEST_EVENT_TYPES = [
  'page_view',
  'click',
  'form_submit',
  'purchase',
  'sign_up',
  'sign_in',
  'sign_out',
  'error',
] as const;

/**
 * Generate a test event
 */
export function generateEvent(overrides: Partial<TestEvent> = {}): TestEvent {
  return {
    id: overrides.id ?? EntityId.from(`event_${randomString(8)}`),
    type: overrides.type ?? randomElement(TEST_EVENT_TYPES),
    userId: overrides.userId ?? EntityId.from(`user_${randomString(8)}`),
    sessionId: overrides.sessionId ?? EntityId.from(`session_${randomString(8)}`),
    properties: overrides.properties ?? {
      url: randomUrl(),
      referrer: randomBoolean() ? randomUrl() : null,
      device: randomElement(['desktop', 'mobile', 'tablet']),
      browser: randomElement(['Chrome', 'Firefox', 'Safari', 'Edge']),
    },
    timestamp: overrides.timestamp ?? randomTimestamp(),
  };
}

/**
 * Session test data
 */
export interface TestSession {
  readonly id: EntityId;
  readonly userId: EntityId;
  readonly startedAt: Timestamp;
  readonly endedAt?: Timestamp;
  readonly duration?: Milliseconds;
  readonly pageViews: number;
  readonly events: number;
  readonly device: 'desktop' | 'mobile' | 'tablet';
  readonly browser: string;
  readonly country?: string;
}

/**
 * Generate a test session
 */
export function generateSession(overrides: Partial<TestSession> = {}): TestSession {
  const startedAt = overrides.startedAt ?? randomTimestamp();
  const hasEnded = randomBoolean();
  const endedAt = hasEnded ? Timestamp.from(startedAt + randomInt(60000, 3600000)) : undefined;
  const duration = endedAt ? Milliseconds.from(endedAt - startedAt) : undefined;

  return {
    id: overrides.id ?? EntityId.from(`session_${randomString(8)}`),
    userId: overrides.userId ?? EntityId.from(`user_${randomString(8)}`),
    startedAt,
    endedAt: overrides.endedAt ?? endedAt,
    duration: overrides.duration ?? duration,
    pageViews: overrides.pageViews ?? randomInt(1, 20),
    events: overrides.events ?? randomInt(1, 50),
    device: overrides.device ?? randomElement(['desktop', 'mobile', 'tablet'] as const),
    browser: overrides.browser ?? randomElement(['Chrome', 'Firefox', 'Safari', 'Edge']),
    country: overrides.country ?? randomElement(['US', 'UK', 'DE', 'FR', 'JP', undefined]),
  };
}

// =============================================================================
// Batch Generators
// =============================================================================

/**
 * Generate multiple test users
 */
export function generateUsers(count: number, overrides: Partial<TestUser> = {}): TestUser[] {
  return Array.from({ length: count }, () => generateUser(overrides));
}

/**
 * Generate multiple test events
 */
export function generateEvents(count: number, overrides: Partial<TestEvent> = {}): TestEvent[] {
  return Array.from({ length: count }, () => generateEvent(overrides));
}

/**
 * Generate multiple test sessions
 */
export function generateSessions(
  count: number,
  overrides: Partial<TestSession> = {},
): TestSession[] {
  return Array.from({ length: count }, () => generateSession(overrides));
}

// =============================================================================
// TestData Factory
// =============================================================================

/**
 * Test data factory providing access to all builders and generators
 *
 * @example
 * ```typescript
 * // Generate a single user
 * const user = TestData.user({ role: 'admin' });
 *
 * // Generate multiple events
 * const events = TestData.events(10, { userId: user.id });
 *
 * // Use builders
 * const query = TestData.query()
 *   .withTable('events')
 *   .withMeasure('count', 'count')
 *   .build();
 * ```
 */
export const TestData = {
  // Random generators
  string: randomString,
  int: randomInt,
  float: randomFloat,
  boolean: randomBoolean,
  element: randomElement,
  elements: randomElements,
  email: randomEmail,
  url: randomUrl,
  timestamp: randomTimestamp,
  duration: randomDuration,

  // Entity generators
  user: generateUser,
  users: generateUsers,
  event: generateEvent,
  events: generateEvents,
  session: generateSession,
  sessions: generateSessions,

  // ID generators
  entityId: (prefix = 'entity') => EntityId.from(`${prefix}_${randomString(8)}`),
  provisionalId: () => ProvisionalId.generate(),
} as const;

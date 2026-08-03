/**
 * Session type definitions derived from Zod schemas
 * @module types/session
 */

import type { z } from 'zod';

import type {
  CreateSessionSchema,
  ExitPageSchema,
  LandingPageSchema,
  SessionFiltersSchema,
  SessionMetricsSchema,
  SessionSchema,
  SessionStatusSchema,
  SessionSummarySchema,
  UpdateSessionSchema,
} from '../schemas/session.schema';
import type { Event } from './event';

/**
 * Session status type
 */
export type SessionStatus = z.infer<typeof SessionStatusSchema>;

/**
 * Landing page type
 */
export type LandingPage = z.infer<typeof LandingPageSchema>;

/**
 * Exit page type
 */
export type ExitPage = z.infer<typeof ExitPageSchema>;

/**
 * Session metrics type
 */
export type SessionMetrics = z.infer<typeof SessionMetricsSchema>;

/**
 * Core session type
 */
export type Session = z.infer<typeof SessionSchema>;

/**
 * Session creation input type
 */
export type CreateSession = z.infer<typeof CreateSessionSchema>;

/**
 * Session update input type
 */
export type UpdateSession = z.infer<typeof UpdateSessionSchema>;

/**
 * Session query filters type
 */
export type SessionFilters = z.infer<typeof SessionFiltersSchema>;

/**
 * Session summary type
 */
export type SessionSummary = z.infer<typeof SessionSummarySchema>;

/**
 * Session with related events
 */
export interface SessionWithEvents extends Session {
  events: Event[];
  eventCount: number;
}

/**
 * Session replay data
 */
export interface SessionReplay {
  sessionId: string;
  events: Event[];
  startTime: string;
  endTime: string;
  duration: number;
  pageViews: string[];
}

/**
 * Session funnel step
 */
export interface SessionFunnelStep {
  step: number;
  name: string;
  count: number;
  conversionRate: number;
  dropoffRate: number;
}

/**
 * Session cohort
 */
export interface SessionCohort {
  cohortDate: string;
  totalSessions: number;
  retentionByDay: number[];
}

/**
 * Active session info (for real-time dashboard)
 */
export interface ActiveSession {
  id: string;
  userId: string | null;
  currentPage: string;
  startedAt: string;
  lastActivityAt: string;
  pageViews: number;
  country?: string;
  device?: string;
}

/**
 * Session timeout configuration
 */
export interface SessionTimeoutConfig {
  idleTimeoutMs: number;
  maxDurationMs: number;
}

/**
 * Default session timeout values
 */
export const DEFAULT_SESSION_TIMEOUT: SessionTimeoutConfig = {
  idleTimeoutMs: 30 * 60 * 1000, // 30 minutes
  maxDurationMs: 24 * 60 * 60 * 1000, // 24 hours
};

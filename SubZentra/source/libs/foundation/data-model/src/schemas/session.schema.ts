/**
 * Session schema definitions
 * @module schemas/session
 */

import { z } from 'zod';

import { DateRangeSchema, TenantScopedSchema } from './base.schema';
import {
  BrowserInfoSchema,
  DeviceInfoSchema,
  GeoLocationSchema,
  UtmParamsSchema,
} from './event.schema';

/**
 * Session status enum
 */
export const SessionStatusSchema = z.enum(['active', 'ended', 'expired']);

/**
 * Landing page schema
 */
export const LandingPageSchema = z.object({
  url: z.string().url(),
  path: z.string(),
  title: z.string().optional(),
  referrer: z.string().optional(),
});

/**
 * Exit page schema
 */
export const ExitPageSchema = z.object({
  url: z.string().url(),
  path: z.string(),
  title: z.string().optional(),
});

/**
 * Session metrics schema
 */
export const SessionMetricsSchema = z.object({
  pageViews: z.number().int().default(0),
  events: z.number().int().default(0),
  duration: z.number().int().default(0), // Duration in seconds
  bounced: z.boolean().default(false),
  engaged: z.boolean().default(false),
});

/**
 * Core session schema
 *
 * Extends TenantScopedSchema which provides: id, tenantId, createdAt, updatedAt
 */
export const SessionSchema = TenantScopedSchema.extend({
  // tenantId is inherited from TenantScopedSchema
  userId: z.string().uuid().nullable().optional(),
  anonymousId: z.string().uuid(),

  // Session state
  status: SessionStatusSchema,
  startedAt: z.string().datetime(),
  endedAt: z.string().datetime().nullable().optional(),
  lastActivityAt: z.string().datetime(),

  // Session attribution
  landing: LandingPageSchema.optional(),
  exit: ExitPageSchema.optional(),
  utm: UtmParamsSchema.optional(),

  // Device & Browser
  browser: BrowserInfoSchema.optional(),
  device: DeviceInfoSchema.optional(),

  // Location
  geo: GeoLocationSchema.optional(),
  ip: z.union([z.ipv4(), z.ipv6()]).optional(),

  // Aggregated metrics
  metrics: SessionMetricsSchema.prefault({}),
});

/**
 * Session creation input
 */
export const CreateSessionSchema = SessionSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  endedAt: true,
  exit: true,
  metrics: true,
}).extend({
  metrics: SessionMetricsSchema.optional(),
});

/**
 * Session update input
 */
export const UpdateSessionSchema = SessionSchema.partial().omit({
  id: true,
  tenantId: true,
  anonymousId: true,
  createdAt: true,
  startedAt: true,
});

/**
 * Session query filters
 */
export const SessionFiltersSchema = z.object({
  tenantId: z.string().uuid(),
  userId: z.string().uuid().optional(),
  status: SessionStatusSchema.optional(),
  bounced: z.boolean().optional(),
  engaged: z.boolean().optional(),
  ...DateRangeSchema.shape,
});

/**
 * Session summary for analytics
 */
export const SessionSummarySchema = z.object({
  totalSessions: z.number().int(),
  uniqueUsers: z.number().int(),
  avgDuration: z.number(),
  bounceRate: z.number(),
  engagementRate: z.number(),
  avgPageViews: z.number(),
});

/**
 * Analytics event schema definitions
 * @module schemas/event
 */

import { z } from 'zod';

import { DateRangeSchema, TenantScopedSchema } from './base.schema';

/**
 * Event type enum - common analytics events
 */
export const EventTypeSchema = z.enum([
  'page_view',
  'session_start',
  'session_end',
  'click',
  'form_submit',
  'error',
  'custom',
  'identify',
  'track',
]);

/**
 * Device type enum
 */
export const DeviceTypeSchema = z.enum(['desktop', 'mobile', 'tablet', 'unknown']);

/**
 * Browser info schema
 */
export const BrowserInfoSchema = z.object({
  name: z.string().optional(),
  version: z.string().optional(),
  engine: z.string().optional(),
});

/**
 * Device info schema
 */
export const DeviceInfoSchema = z.object({
  type: DeviceTypeSchema,
  os: z.string().optional(),
  osVersion: z.string().optional(),
  screen: z
    .object({
      width: z.number().int().optional(),
      height: z.number().int().optional(),
    })
    .optional(),
});

/**
 * Geo location schema
 */
export const GeoLocationSchema = z.object({
  country: z.string().optional(),
  region: z.string().optional(),
  city: z.string().optional(),
  latitude: z.number().optional(),
  longitude: z.number().optional(),
  timezone: z.string().optional(),
});

/**
 * Page context schema
 */
export const PageContextSchema = z.object({
  url: z.string().url().optional(),
  path: z.string().optional(),
  title: z.string().optional(),
  referrer: z.string().optional(),
  search: z.string().optional(),
  hash: z.string().optional(),
});

/**
 * UTM parameters schema
 */
export const UtmParamsSchema = z.object({
  source: z.string().optional(),
  medium: z.string().optional(),
  campaign: z.string().optional(),
  term: z.string().optional(),
  content: z.string().optional(),
});

/**
 * Core analytics event schema
 *
 * Extends TenantScopedSchema which provides: id, tenantId, createdAt, updatedAt
 */
export const EventSchema = TenantScopedSchema.extend({
  // tenantId is inherited from TenantScopedSchema
  sessionId: z.string().uuid(),
  userId: z.string().uuid().nullable().optional(),
  anonymousId: z.string().uuid(),

  // Event classification
  type: EventTypeSchema,
  name: z.string().max(255),
  category: z.string().max(100).optional(),

  // Event data
  properties: z.record(z.string(), z.unknown()).default({}),

  // Context
  timestamp: z.string().datetime(),
  receivedAt: z.string().datetime(),
  sentAt: z.string().datetime().optional(),

  // Device & Browser
  browser: BrowserInfoSchema.optional(),
  device: DeviceInfoSchema.optional(),

  // Location
  geo: GeoLocationSchema.optional(),
  ip: z.union([z.ipv4(), z.ipv6()]).optional(),

  // Page context
  page: PageContextSchema.optional(),

  // Marketing attribution
  utm: UtmParamsSchema.optional(),

  // SDK info
  sdkName: z.string().optional(),
  sdkVersion: z.string().optional(),
});

/**
 * Event creation input (from SDK)
 */
export const CreateEventSchema = EventSchema.omit({
  id: true,
  receivedAt: true,
  createdAt: true,
  updatedAt: true,
});

/**
 * Event query filters
 */
export const EventFiltersSchema = z.object({
  tenantId: z.string().uuid(),
  sessionId: z.string().uuid().optional(),
  userId: z.string().uuid().optional(),
  type: EventTypeSchema.optional(),
  name: z.string().optional(),
  ...DateRangeSchema.shape,
});

/**
 * Event aggregation schema
 */
export const EventAggregationSchema = z.object({
  count: z.number().int(),
  uniqueUsers: z.number().int(),
  uniqueSessions: z.number().int(),
  groupBy: z.record(z.string(), z.number().int()).optional(),
});

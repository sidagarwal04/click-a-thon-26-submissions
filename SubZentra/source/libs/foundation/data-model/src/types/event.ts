/**
 * Event type definitions derived from Zod schemas
 * @module types/event
 */

import type { z } from 'zod';

import type {
  BrowserInfoSchema,
  CreateEventSchema,
  DeviceInfoSchema,
  DeviceTypeSchema,
  EventAggregationSchema,
  EventFiltersSchema,
  EventSchema,
  EventTypeSchema,
  GeoLocationSchema,
  PageContextSchema,
  UtmParamsSchema,
} from '../schemas/event.schema';

/**
 * Event type enum
 */
export type EventType = z.infer<typeof EventTypeSchema>;

/**
 * Device type enum
 */
export type DeviceType = z.infer<typeof DeviceTypeSchema>;

/**
 * Browser info type
 */
export type BrowserInfo = z.infer<typeof BrowserInfoSchema>;

/**
 * Device info type
 */
export type DeviceInfo = z.infer<typeof DeviceInfoSchema>;

/**
 * Geo location type
 */
export type GeoLocation = z.infer<typeof GeoLocationSchema>;

/**
 * Page context type
 */
export type PageContext = z.infer<typeof PageContextSchema>;

/**
 * UTM parameters type
 */
export type UtmParams = z.infer<typeof UtmParamsSchema>;

/**
 * Core analytics event type
 */
export type Event = z.infer<typeof EventSchema>;

/**
 * Event creation input type
 */
export type CreateEvent = z.infer<typeof CreateEventSchema>;

/**
 * Event query filters type
 */
export type EventFilters = z.infer<typeof EventFiltersSchema>;

/**
 * Event aggregation type
 */
export type EventAggregation = z.infer<typeof EventAggregationSchema>;

/**
 * Event with derived computed fields
 */
export interface EventWithComputed extends Event {
  isFirstInSession?: boolean;
  isLastInSession?: boolean;
  timeSinceLastEvent?: number;
}

/**
 * Event batch for bulk operations
 */
export interface EventBatch {
  events: CreateEvent[];
  batchId: string;
  sentAt: string;
}

/**
 * Event count by type
 */
export type EventCountByType = Record<EventType, number>;

/**
 * Event timeline entry
 */
export interface EventTimelineEntry {
  timestamp: string;
  count: number;
  uniqueUsers: number;
  uniqueSessions: number;
}

/**
 * Common event property keys
 */
export const COMMON_EVENT_PROPERTIES = [
  'button_text',
  'link_url',
  'form_id',
  'error_message',
  'error_stack',
  'value',
  'currency',
  'product_id',
  'category',
  'label',
] as const;

export type CommonEventProperty = (typeof COMMON_EVENT_PROPERTIES)[number];

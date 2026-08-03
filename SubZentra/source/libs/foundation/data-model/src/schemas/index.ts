/**
 * Schema exports
 * @module schemas
 */

// Base schemas
export {
  BaseEntitySchema,
  TimestampsSchema,
  SoftDeleteSchema,
  TenantScopedSchema,
  PaginationParamsSchema,
  SortDirectionSchema,
  DateRangeSchema,
  PROVISIONAL_ID_PREFIX,
  isProvisionalId,
  generateProvisionalId,
} from './base.schema';

// User schemas
export {
  UserSchema,
  UserRoleSchema,
  UserStatusSchema,
  UserPreferencesSchema,
  CreateUserSchema,
  UpdateUserSchema,
  UserFiltersSchema,
} from './user.schema';

// Event schemas
export {
  EventSchema,
  EventTypeSchema,
  DeviceTypeSchema,
  BrowserInfoSchema,
  DeviceInfoSchema,
  GeoLocationSchema,
  PageContextSchema,
  UtmParamsSchema,
  CreateEventSchema,
  EventFiltersSchema,
  EventAggregationSchema,
} from './event.schema';

// Session schemas
export {
  SessionSchema,
  SessionStatusSchema,
  LandingPageSchema,
  ExitPageSchema,
  SessionMetricsSchema,
  CreateSessionSchema,
  UpdateSessionSchema,
  SessionFiltersSchema,
  SessionSummarySchema,
} from './session.schema';

/**
 * Utility Types for Foundation Libraries
 *
 * Provides common TypeScript utility types used across foundation libraries.
 * These are general-purpose type transformations.
 *
 * @module types/utility
 */

// =============================================================================
// Deep Type Transformations
// =============================================================================

/**
 * Deep readonly utility type - makes all nested properties readonly
 *
 * Recursively applies readonly to all properties of an object type,
 * including nested objects and arrays.
 *
 * @template T - The type to make deeply readonly
 *
 * @example
 * ```typescript
 * type Config = { settings: { debug: boolean; timeout: number } };
 * type ReadonlyConfig = DeepReadonly<Config>;
 * // Result: { readonly settings: { readonly debug: boolean; readonly timeout: number } }
 * ```
 */
export type DeepReadonly<T> = T extends (infer U)[]
  ? ReadonlyArray<DeepReadonly<U>>
  : T extends object
  ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
  : T;

/**
 * Deep partial utility type - makes all nested properties optional
 *
 * Recursively applies Partial to all properties of an object type,
 * including nested objects.
 *
 * @template T - The type to make deeply partial
 *
 * @example
 * ```typescript
 * type Config = { settings: { debug: boolean; timeout: number } };
 * type PartialConfig = DeepPartial<Config>;
 * // Result: { settings?: { debug?: boolean; timeout?: number } }
 * ```
 */
export type DeepPartial<T> = T extends object ? { [K in keyof T]?: DeepPartial<T[K]> } : T;

// =============================================================================
// Property Modifiers
// =============================================================================

/**
 * Make specific properties required while keeping others unchanged
 *
 * Useful when you have an optional property that must be present
 * in certain contexts.
 *
 * @template T - The base type
 * @template K - Keys to make required
 *
 * @example
 * ```typescript
 * type User = { id?: string; name?: string; email?: string };
 * type UserWithId = RequireFields<User, 'id'>;
 * // Result: { id: string; name?: string; email?: string }
 * ```
 */
export type RequireFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

/**
 * Make specific properties optional while keeping others unchanged
 *
 * Useful when you want to make certain required properties optional,
 * like when creating update DTOs.
 *
 * @template T - The base type
 * @template K - Keys to make optional
 *
 * @example
 * ```typescript
 * type User = { id: string; name: string; email: string };
 * type UserUpdate = OptionalFields<User, 'id'>;
 * // Result: { id?: string; name: string; email: string }
 * ```
 */
export type OptionalFields<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

// =============================================================================
// Key Extraction
// =============================================================================

/**
 * Extract keys of type T that have value type V
 *
 * Useful for filtering object keys by their value types.
 *
 * @template T - The object type to extract keys from
 * @template V - The value type to filter by
 *
 * @example
 * ```typescript
 * type User = { id: string; age: number; name: string; score: number };
 * type NumberKeys = KeysOfType<User, number>;
 * // Result: 'age' | 'score'
 * ```
 */
export type KeysOfType<T, V> = {
  [K in keyof T]: T[K] extends V ? K : never;
}[keyof T];

// =============================================================================
// Mutability Modifiers
// =============================================================================

/**
 * Mutable utility type - removes readonly from all properties
 *
 * Useful when you need to create a mutable copy of a readonly type.
 *
 * @template T - The type to make mutable
 *
 * @example
 * ```typescript
 * type ReadonlyUser = { readonly id: string; readonly name: string };
 * type MutableUser = Mutable<ReadonlyUser>;
 * // Result: { id: string; name: string }
 * ```
 */
export type Mutable<T> = { -readonly [P in keyof T]: T[P] };

/**
 * Deep mutable utility type - removes readonly from all nested properties
 *
 * Recursively removes readonly from all properties of an object type,
 * including nested objects and arrays.
 *
 * @template T - The type to make deeply mutable
 *
 * @example
 * ```typescript
 * type ReadonlyConfig = { readonly settings: { readonly debug: boolean } };
 * type MutableConfig = DeepMutable<ReadonlyConfig>;
 * // Result: { settings: { debug: boolean } }
 * ```
 */
export type DeepMutable<T> = T extends ReadonlyArray<infer U>
  ? Array<DeepMutable<U>>
  : T extends object
  ? { -readonly [K in keyof T]: DeepMutable<T[K]> }
  : T;

// =============================================================================
// Nullability Utilities
// =============================================================================

/**
 * Make all properties non-nullable
 *
 * Removes null and undefined from all property types.
 *
 * @template T - The type to make non-nullable
 *
 * @example
 * ```typescript
 * type User = { id: string | null; name: string | undefined };
 * type RequiredUser = NonNullableFields<User>;
 * // Result: { id: string; name: string }
 * ```
 */
export type NonNullableFields<T> = {
  [K in keyof T]: NonNullable<T[K]>;
};

/**
 * Make specific properties nullable
 *
 * @template T - The base type
 * @template K - Keys to make nullable
 *
 * @example
 * ```typescript
 * type User = { id: string; name: string };
 * type UserWithNullableName = NullableFields<User, 'name'>;
 * // Result: { id: string; name: string | null }
 * ```
 */
export type NullableFields<T, K extends keyof T> = Omit<T, K> & {
  [P in K]: T[P] | null;
};

// =============================================================================
// Object Utilities
// =============================================================================

/**
 * Pick properties from T where the value extends V
 *
 * @template T - The object type to pick from
 * @template V - The value type to filter by
 *
 * @example
 * ```typescript
 * type User = { id: string; age: number; name: string };
 * type StringFields = PickByType<User, string>;
 * // Result: { id: string; name: string }
 * ```
 */
export type PickByType<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

/**
 * Omit properties from T where the value extends V
 *
 * @template T - The object type to omit from
 * @template V - The value type to filter by
 *
 * @example
 * ```typescript
 * type User = { id: string; age: number; name: string };
 * type NonStringFields = OmitByType<User, string>;
 * // Result: { age: number }
 * ```
 */
export type OmitByType<T, V> = {
  [K in keyof T as T[K] extends V ? never : K]: T[K];
};

// =============================================================================
// Union Utilities
// =============================================================================

/**
 * Extract the value type from a union of literal types
 *
 * @template T - Union type to extract values from
 *
 * @example
 * ```typescript
 * const statuses = ['pending', 'active', 'completed'] as const;
 * type Status = ValueOf<typeof statuses>;
 * // Result: 'pending' | 'active' | 'completed'
 * ```
 */
export type ValueOf<T> = T[keyof T];

/**
 * Create a union type from an array type
 *
 * @template T - Array type
 *
 * @example
 * ```typescript
 * const colors = ['red', 'green', 'blue'] as const;
 * type Color = ArrayElement<typeof colors>;
 * // Result: 'red' | 'green' | 'blue'
 * ```
 */
export type ArrayElement<T extends readonly unknown[]> = T[number];

// =============================================================================
// Entity ID Utilities
// =============================================================================

/**
 * Entity with ID - base interface for entities that have an identifier
 *
 * Uses a standard `id` field across the workspace.
 *
 * @example
 * ```typescript
 * // Standard document (has id)
 * const standardDoc: WithId = { id: 'abc123', name: 'John' };
 * ```
 */
export interface WithId {
  /** Standard ID field */
  id?: string;
}

/**
 * Entity with a guaranteed ID.
 */
export interface WithRequiredId {
  id: string;
}

/**
 * Extract ID from entity - returns string if entity has any ID field
 *
 * @template T - The entity type
 *
 * @example
 * ```typescript
 * type UserWithId = { id: string; name: string };
 * type UserId = ExtractId<UserWithId>; // string
 *
 * type UserMaybeId = { id?: string; name: string };
 * type MaybeUserId = ExtractId<UserMaybeId>; // string | undefined
 * ```
 */
export type ExtractId<T> = T extends WithRequiredId
  ? string
  : T extends WithId
  ? string | undefined
  : never;

/**
 * Make specific fields optional (alias for OptionalFields)
 *
 * Commonly used to make ID fields optional for create operations.
 *
 * @template T - The base type
 * @template K - Keys to make optional
 *
 * @example
 * ```typescript
 * type User = { id: string; name: string; email: string };
 * type CreateUser = PartialBy<User, 'id'>;
 * // Result: { id?: string; name: string; email: string }
 * ```
 */
export type PartialBy<T, K extends keyof T> = OptionalFields<T, K>;

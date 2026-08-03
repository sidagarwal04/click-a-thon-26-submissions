/**
 * Utility types for the OpenZentra Design System
 * @module types/utils
 */

/** Recursively create all properties optional */
export type FullPartial<T> = T extends Record<string, unknown>
  ? {
      [K in keyof T]?: FullPartial<T[K]>;
    }
  : Partial<T>;

/** Removes properties from the interface that have value of never */
export type OmitNever<T> = { [K in keyof T as T[K] extends never ? never : K]: T[K] };

/**
 * Resolves the type so that is easier to display it
 * Ref: https://effectivetypescript.com/2022/02/25/gentips-4-display/
 */
// eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
export type Resolve<T> = T extends Function ? T : { [K in keyof T]: T[K] };

/** Returns props of React element type (ex: div, span, a, ... ) or React Components */
export type PropsOf<T extends React.ElementType> = React.ComponentPropsWithRef<T>;

/** Deep merge two types */
export type DeepMerge<T, U> = {
  [K in keyof T | keyof U]: K extends keyof U
    ? K extends keyof T
      ? T[K] extends Record<string, unknown>
        ? U[K] extends Record<string, unknown>
          ? DeepMerge<T[K], U[K]>
          : U[K]
        : U[K]
      : U[K]
    : K extends keyof T
    ? T[K]
    : never;
};

/** Extract keys from object type */
export type KeysOf<T> = T extends Record<string, unknown> ? keyof T : never;

/** Make specific keys required */
export type RequireKeys<T, K extends keyof T> = T & Required<Pick<T, K>>;

/** Make specific keys optional */
export type OptionalKeys<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

/** Strict omit that ensures key exists */
export type StrictOmit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;

/** Extract string literal union from array */
export type ArrayElement<T> = T extends readonly (infer U)[] ? U : never;

/** Convert union to intersection */
export type UnionToIntersection<U> = (U extends unknown ? (k: U) => void : never) extends (
  k: infer I,
) => void
  ? I
  : never;

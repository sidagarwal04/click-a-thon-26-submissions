/**
 * Sampling Module Exports
 * @module sampling
 */

export { createHeadSampler, createPrioritySampler, createConsistentSampler } from './head-sampler';
export type { SamplerResult } from './head-sampler';

export {
  createRateLimiter,
  createTokenBucketLimiter,
  createKeyedRateLimiter,
} from './rate-limiter';
export type { RateLimiterConfig, RateLimitResult } from './rate-limiter';

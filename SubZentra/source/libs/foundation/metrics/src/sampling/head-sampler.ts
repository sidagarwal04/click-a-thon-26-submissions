/**
 * Head-Based Sampler
 * @module sampling/head-sampler
 */

import type { SamplerSignalType, SamplingConfig, SamplingDecision } from '../types';
import { SAMPLER_SIGNAL_TYPE, SAMPLING_DECISION } from '../types/constants';

/**
 * Sampler result
 */
export interface SamplerResult {
  decision: SamplingDecision;
  reason: string;
}

/**
 * Create a head-based sampler
 */
export const createHeadSampler = (config: SamplingConfig) => {
  /**
   * Make a sampling decision for a general signal
   */
  const shouldSample = (): SamplerResult => {
    const random = Math.random();

    if (random <= config.defaultRate) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'default_rate' };
    }

    return { decision: SAMPLING_DECISION.DROP, reason: 'default_rate_exceeded' };
  };

  /**
   * Make a sampling decision for an error
   */
  const shouldSampleError = (): SamplerResult => {
    const random = Math.random();

    if (random <= config.errorRate) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'error_rate' };
    }

    return { decision: SAMPLING_DECISION.DROP, reason: 'error_rate_exceeded' };
  };

  /**
   * Make a sampling decision for a trace
   */
  const shouldSampleTrace = (): SamplerResult => {
    const random = Math.random();

    if (random <= config.traceRate) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'trace_rate' };
    }

    return { decision: SAMPLING_DECISION.DROP, reason: 'trace_rate_exceeded' };
  };

  /**
   * Make a sampling decision for user behavior
   */
  const shouldSampleUserBehavior = (): SamplerResult => {
    const random = Math.random();

    if (random <= config.userBehaviorRate) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'user_behavior_rate' };
    }

    return { decision: SAMPLING_DECISION.DROP, reason: 'user_behavior_rate_exceeded' };
  };

  /**
   * Make a sampling decision based on signal type
   */
  const shouldSampleSignal = (signalType: SamplerSignalType): SamplerResult => {
    switch (signalType) {
      case SAMPLER_SIGNAL_TYPE.ERROR:
        return shouldSampleError();
      case SAMPLER_SIGNAL_TYPE.TRACE:
        return shouldSampleTrace();
      case SAMPLER_SIGNAL_TYPE.USER_BEHAVIOR:
        return shouldSampleUserBehavior();
      case SAMPLER_SIGNAL_TYPE.METRIC:
      default:
        return shouldSample();
    }
  };

  return {
    shouldSample,
    shouldSampleError,
    shouldSampleTrace,
    shouldSampleUserBehavior,
    shouldSampleSignal,
  };
};

/**
 * Priority sampler - always sample high-priority signals
 */
export const createPrioritySampler = (config: SamplingConfig) => {
  const baseSampler = createHeadSampler(config);

  /**
   * Determine if signal is high priority
   */
  const isHighPriority = (context: {
    isError?: boolean;
    statusCode?: number;
    duration?: number;
    userId?: string;
  }): boolean => {
    // Always sample errors
    if (context.isError) {
      return true;
    }

    // Sample slow requests (> 5 seconds)
    if (context.duration && context.duration > 5000) {
      return true;
    }

    // Sample server errors
    if (context.statusCode && context.statusCode >= 500) {
      return true;
    }

    return false;
  };

  /**
   * Make a priority-aware sampling decision
   */
  const shouldSampleWithPriority = (context: {
    isError?: boolean;
    statusCode?: number;
    duration?: number;
    userId?: string;
  }): SamplerResult => {
    if (isHighPriority(context)) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'high_priority' };
    }

    return baseSampler.shouldSample();
  };

  return {
    ...baseSampler,
    isHighPriority,
    shouldSampleWithPriority,
  };
};

/**
 * Create a consistent sampler (same user always gets same decision)
 */
export const createConsistentSampler = (config: SamplingConfig, salt = '') => {
  const baseSampler = createHeadSampler(config);

  /**
   * Hash a string to a number between 0 and 1
   */
  const hashToRate = (value: string): number => {
    let hash = 0;
    const combined = salt + value;

    for (let i = 0; i < combined.length; i++) {
      const char = combined.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // Convert to 32-bit integer
    }

    // Normalize to 0-1 range
    return Math.abs(hash) / 2147483647;
  };

  /**
   * Make a consistent sampling decision
   */
  const shouldSampleConsistent = (identifier: string, rate?: number): SamplerResult => {
    const effectiveRate = rate ?? config.defaultRate;
    const hash = hashToRate(identifier);

    if (hash <= effectiveRate) {
      return { decision: SAMPLING_DECISION.SAMPLE, reason: 'consistent_sample' };
    }

    return { decision: SAMPLING_DECISION.DROP, reason: 'consistent_drop' };
  };

  return {
    ...baseSampler,
    shouldSampleConsistent,
    hashToRate,
  };
};

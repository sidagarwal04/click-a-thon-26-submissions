/**
 * Head Sampler Tests
 * @module sampling/head-sampler.spec
 */

import { describe, expect, it } from 'vitest';

import { createConsistentSampler, createHeadSampler, createPrioritySampler } from './head-sampler';

describe('Head Sampler', () => {
  describe('createHeadSampler', () => {
    it('should always sample when rate is 1.0', () => {
      const sampler = createHeadSampler({
        defaultRate: 1.0,
        errorRate: 1.0,
        traceRate: 1.0,
        userBehaviorRate: 1.0,
      });

      // Run multiple times to ensure consistency
      for (let i = 0; i < 100; i++) {
        const result = sampler.shouldSample();
        expect(result.decision).toBe('sample');
      }
    });

    it('should never sample when rate is 0.0', () => {
      const sampler = createHeadSampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      for (let i = 0; i < 100; i++) {
        const result = sampler.shouldSample();
        expect(result.decision).toBe('drop');
      }
    });

    it('should sample errors at errorRate', () => {
      const sampler = createHeadSampler({
        defaultRate: 0.0,
        errorRate: 1.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleError();
      expect(result.decision).toBe('sample');
      expect(result.reason).toBe('error_rate');
    });

    it('should sample traces at traceRate', () => {
      const sampler = createHeadSampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 1.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleTrace();
      expect(result.decision).toBe('sample');
    });

    it('should sample user behavior at userBehaviorRate', () => {
      const sampler = createHeadSampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 1.0,
      });

      const result = sampler.shouldSampleUserBehavior();
      expect(result.decision).toBe('sample');
    });

    it('should route to correct sampler by signal type', () => {
      const sampler = createHeadSampler({
        defaultRate: 0.0,
        errorRate: 1.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      expect(sampler.shouldSampleSignal('error').decision).toBe('sample');
      expect(sampler.shouldSampleSignal('trace').decision).toBe('drop');
      expect(sampler.shouldSampleSignal('userBehavior').decision).toBe('drop');
    });
  });

  describe('createPrioritySampler', () => {
    it('should always sample errors regardless of rate', () => {
      const sampler = createPrioritySampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleWithPriority({ isError: true });
      expect(result.decision).toBe('sample');
      expect(result.reason).toBe('high_priority');
    });

    it('should always sample slow requests', () => {
      const sampler = createPrioritySampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleWithPriority({ duration: 6000 });
      expect(result.decision).toBe('sample');
      expect(result.reason).toBe('high_priority');
    });

    it('should always sample server errors', () => {
      const sampler = createPrioritySampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleWithPriority({ statusCode: 500 });
      expect(result.decision).toBe('sample');
      expect(result.reason).toBe('high_priority');
    });

    it('should use default rate for non-priority items', () => {
      const sampler = createPrioritySampler({
        defaultRate: 0.0,
        errorRate: 0.0,
        traceRate: 0.0,
        userBehaviorRate: 0.0,
      });

      const result = sampler.shouldSampleWithPriority({ statusCode: 200 });
      expect(result.decision).toBe('drop');
    });

    it('should identify high priority correctly', () => {
      const sampler = createPrioritySampler({
        defaultRate: 1.0,
        errorRate: 1.0,
        traceRate: 1.0,
        userBehaviorRate: 1.0,
      });

      expect(sampler.isHighPriority({ isError: true })).toBe(true);
      expect(sampler.isHighPriority({ duration: 10000 })).toBe(true);
      expect(sampler.isHighPriority({ statusCode: 503 })).toBe(true);
      expect(sampler.isHighPriority({ statusCode: 200 })).toBe(false);
      expect(sampler.isHighPriority({})).toBe(false);
    });
  });

  describe('createConsistentSampler', () => {
    it('should give consistent results for same identifier', () => {
      const sampler = createConsistentSampler(
        {
          defaultRate: 0.5,
          errorRate: 1.0,
          traceRate: 0.5,
          userBehaviorRate: 0.5,
        },
        'test-salt',
      );

      const id = 'user-123';
      const results = [];

      for (let i = 0; i < 100; i++) {
        results.push(sampler.shouldSampleConsistent(id));
      }

      // All results should be the same
      const firstDecision = results[0].decision;
      expect(results.every((r) => r.decision === firstDecision)).toBe(true);
    });

    it('should give different results for different identifiers', () => {
      const sampler = createConsistentSampler(
        {
          defaultRate: 0.5,
          errorRate: 1.0,
          traceRate: 0.5,
          userBehaviorRate: 0.5,
        },
        'test-salt',
      );

      const decisions = new Set<string>();

      // Generate many different IDs
      for (let i = 0; i < 1000; i++) {
        const result = sampler.shouldSampleConsistent(`user-${i}`);
        decisions.add(result.decision);
      }

      // Should have both sample and drop decisions
      expect(decisions.has('sample')).toBe(true);
      expect(decisions.has('drop')).toBe(true);
    });

    it('should hash to value between 0 and 1', () => {
      const sampler = createConsistentSampler(
        {
          defaultRate: 0.5,
          errorRate: 1.0,
          traceRate: 0.5,
          userBehaviorRate: 0.5,
        },
        'test-salt',
      );

      for (let i = 0; i < 100; i++) {
        const hash = sampler.hashToRate(`test-${i}`);
        expect(hash).toBeGreaterThanOrEqual(0);
        expect(hash).toBeLessThanOrEqual(1);
      }
    });
  });
});

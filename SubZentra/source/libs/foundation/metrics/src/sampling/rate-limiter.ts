/**
 * Rate Limiter
 * @module sampling/rate-limiter
 */

/**
 * Rate limiter configuration
 */
export interface RateLimiterConfig {
  /** Maximum number of items per window */
  maxPerWindow: number;
  /** Window size in milliseconds */
  windowSize: number;
}

/**
 * Rate limit result
 */
export interface RateLimitResult {
  allowed: boolean;
  currentCount: number;
  remainingQuota: number;
  resetTime: number;
}

/**
 * Create a sliding window rate limiter
 */
export const createRateLimiter = (config: RateLimiterConfig) => {
  const timestamps: number[] = [];

  /**
   * Check if an item should be allowed
   */
  const tryAcquire = (): RateLimitResult => {
    const now = Date.now();
    const windowStart = now - config.windowSize;

    // Remove old timestamps
    while (timestamps.length > 0 && timestamps[0] < windowStart) {
      timestamps.shift();
    }

    const currentCount = timestamps.length;
    const remainingQuota = Math.max(0, config.maxPerWindow - currentCount);
    const resetTime = timestamps.length > 0 ? timestamps[0] + config.windowSize : now;

    if (currentCount < config.maxPerWindow) {
      timestamps.push(now);
      return {
        allowed: true,
        currentCount: currentCount + 1,
        remainingQuota: remainingQuota - 1,
        resetTime,
      };
    }

    return {
      allowed: false,
      currentCount,
      remainingQuota: 0,
      resetTime,
    };
  };

  /**
   * Get current state without acquiring
   */
  const getState = (): Omit<RateLimitResult, 'allowed'> => {
    const now = Date.now();
    const windowStart = now - config.windowSize;

    // Count valid timestamps without modifying
    const validCount = timestamps.filter((t) => t >= windowStart).length;

    return {
      currentCount: validCount,
      remainingQuota: Math.max(0, config.maxPerWindow - validCount),
      resetTime: timestamps.length > 0 ? timestamps[0] + config.windowSize : now,
    };
  };

  /**
   * Reset the rate limiter
   */
  const reset = (): void => {
    timestamps.length = 0;
  };

  return {
    tryAcquire,
    getState,
    reset,
  };
};

/**
 * Create a token bucket rate limiter
 */
export const createTokenBucketLimiter = (config: {
  /** Maximum number of tokens */
  capacity: number;
  /** Tokens added per second */
  refillRate: number;
}) => {
  let tokens = config.capacity;
  let lastRefill = Date.now();

  /**
   * Refill tokens based on time elapsed
   */
  const refill = (): void => {
    const now = Date.now();
    const elapsed = (now - lastRefill) / 1000;
    const tokensToAdd = elapsed * config.refillRate;

    tokens = Math.min(config.capacity, tokens + tokensToAdd);
    lastRefill = now;
  };

  /**
   * Try to acquire a token
   */
  const tryAcquire = (count = 1): boolean => {
    refill();

    if (tokens >= count) {
      tokens -= count;
      return true;
    }

    return false;
  };

  /**
   * Get current token count
   */
  const getTokens = (): number => {
    refill();
    return tokens;
  };

  /**
   * Reset the bucket
   */
  const reset = (): void => {
    tokens = config.capacity;
    lastRefill = Date.now();
  };

  return {
    tryAcquire,
    getTokens,
    reset,
  };
};

/**
 * Create a keyed rate limiter (rate limit per key)
 */
export const createKeyedRateLimiter = (config: RateLimiterConfig) => {
  const limiters = new Map<string, ReturnType<typeof createRateLimiter>>();

  /**
   * Get or create a limiter for a key
   */
  const getLimiter = (key: string): ReturnType<typeof createRateLimiter> => {
    let limiter = limiters.get(key);

    if (!limiter) {
      limiter = createRateLimiter(config);
      limiters.set(key, limiter);
    }

    return limiter;
  };

  /**
   * Try to acquire for a specific key
   */
  const tryAcquire = (key: string): RateLimitResult => {
    return getLimiter(key).tryAcquire();
  };

  /**
   * Get state for a specific key
   */
  const getState = (key: string): Omit<RateLimitResult, 'allowed'> => {
    return getLimiter(key).getState();
  };

  /**
   * Reset a specific key
   */
  const resetKey = (key: string): void => {
    limiters.delete(key);
  };

  /**
   * Reset all keys
   */
  const resetAll = (): void => {
    limiters.clear();
  };

  /**
   * Cleanup old limiters
   */
  const cleanup = (): void => {
    const now = Date.now();

    for (const [key, limiter] of limiters.entries()) {
      const state = limiter.getState();
      // Remove limiters that haven't been used in 2x window size
      if (state.resetTime < now - config.windowSize) {
        limiters.delete(key);
      }
    }
  };

  return {
    tryAcquire,
    getState,
    resetKey,
    resetAll,
    cleanup,
  };
};

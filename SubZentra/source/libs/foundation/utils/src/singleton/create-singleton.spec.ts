/**
 * Tests for singleton factory utilities
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAsyncSingletonFactory,
  createDeepEqualComparison,
  createSingletonFactory,
} from './create-singleton';

describe('createSingletonFactory', () => {
  interface TestConfig {
    value: number;
  }

  class TestService {
    constructor(public config: TestConfig) {}
    dispose() {
      return undefined;
    }
  }

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('should create instance on first call', () => {
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
    });

    const instance = factory.getInstance({ value: 42 });

    expect(instance).toBeInstanceOf(TestService);
    expect(instance.config.value).toBe(42);
  });

  it('should return same instance on subsequent calls', () => {
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
    });

    const instance1 = factory.getInstance({ value: 1 });
    const instance2 = factory.getInstance({ value: 2 });

    expect(instance1).toBe(instance2);
    expect(instance1.config.value).toBe(1);
  });

  it('should warn when config is passed to existing instance', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
    });

    factory.getInstance({ value: 1 });
    factory.getInstance({ value: 2 });

    expect(mockLogger).toHaveBeenCalledTimes(1);
    expect(mockLogger).toHaveBeenCalledWith(
      expect.stringContaining('[TestService] Instance already exists'),
    );
  });

  it('should not warn when warnOnConfigOverride is false', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      warnOnConfigOverride: false,
    });

    factory.getInstance({ value: 1 });
    factory.getInstance({ value: 2 });

    expect(mockLogger).not.toHaveBeenCalled();
  });

  it('should not warn when no config is passed to existing instance', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
    });

    factory.getInstance({ value: 1 });
    factory.getInstance();

    expect(mockLogger).not.toHaveBeenCalled();
  });

  it('should reset instance and call onDispose', async () => {
    const disposeFn = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      onDispose: disposeFn,
    });

    const instance1 = factory.getInstance({ value: 1 });
    await factory.reset();
    const instance2 = factory.getInstance({ value: 2 });

    expect(disposeFn).toHaveBeenCalledWith(instance1);
    expect(instance1).not.toBe(instance2);
    expect(instance2.config.value).toBe(2);
  });

  it('should handle async onDispose', async () => {
    const disposeFn = vi.fn().mockResolvedValue(undefined);
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      onDispose: disposeFn,
    });

    factory.getInstance({ value: 1 });
    await factory.reset();

    expect(disposeFn).toHaveBeenCalled();
  });

  it('should return correct hasInstance value', () => {
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
    });

    expect(factory.hasInstance()).toBe(false);

    factory.getInstance({ value: 1 });
    expect(factory.hasInstance()).toBe(true);
  });

  it('should use default config when none provided', () => {
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      defaultConfig: { value: 100 },
    });

    const instance = factory.getInstance();

    expect(instance.config.value).toBe(100);
  });
});

describe('createAsyncSingletonFactory', () => {
  interface TestConfig {
    value: number;
  }

  class TestAsyncService {
    constructor(public config: TestConfig) {}
    async disconnect() {
      return undefined;
    }
  }

  async function createTestService(config: TestConfig): Promise<TestAsyncService> {
    await new Promise((resolve) => setTimeout(resolve, 10));
    return new TestAsyncService(config);
  }

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('should create instance on first call', async () => {
    const factory = createAsyncSingletonFactory(createTestService, {
      name: 'TestAsyncService',
    });

    const instance = await factory.getInstance({ value: 42 });

    expect(instance).toBeInstanceOf(TestAsyncService);
    expect(instance.config.value).toBe(42);
  });

  it('should return same instance on subsequent calls', async () => {
    const factory = createAsyncSingletonFactory(createTestService, {
      name: 'TestAsyncService',
    });

    const instance1 = await factory.getInstance({ value: 1 });
    const instance2 = await factory.getInstance({ value: 2 });

    expect(instance1).toBe(instance2);
    expect(instance1.config.value).toBe(1);
  });

  it('should handle concurrent initialization', async () => {
    let callCount = 0;
    const factory = createAsyncSingletonFactory(
      async (config: TestConfig) => {
        callCount++;
        await new Promise((resolve) => setTimeout(resolve, 50));
        return new TestAsyncService(config);
      },
      { name: 'TestAsyncService' },
    );

    const [instance1, instance2] = await Promise.all([
      factory.getInstance({ value: 1 }),
      factory.getInstance({ value: 2 }),
    ]);

    expect(instance1).toBe(instance2);
    expect(callCount).toBe(1);
  });

  it('should warn when config is passed to existing instance', async () => {
    const mockLogger = vi.fn();
    const factory = createAsyncSingletonFactory(createTestService, {
      name: 'TestAsyncService',
      logger: mockLogger,
    });

    await factory.getInstance({ value: 1 });
    await factory.getInstance({ value: 2 });

    expect(mockLogger).toHaveBeenCalledTimes(1);
    expect(mockLogger).toHaveBeenCalledWith(
      expect.stringContaining('[TestAsyncService] Instance already exists'),
    );
  });

  it('should reset instance and call async onDispose', async () => {
    const disposeFn = vi.fn().mockResolvedValue(undefined);
    const factory = createAsyncSingletonFactory(createTestService, {
      name: 'TestAsyncService',
      onDispose: disposeFn,
    });

    const instance1 = await factory.getInstance({ value: 1 });
    await factory.reset();
    const instance2 = await factory.getInstance({ value: 2 });

    expect(disposeFn).toHaveBeenCalledWith(instance1);
    expect(instance1).not.toBe(instance2);
    expect(instance2.config.value).toBe(2);
  });

  it('should wait for pending initialization during reset', async () => {
    const factory = createAsyncSingletonFactory(
      async (config: TestConfig) => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return new TestAsyncService(config);
      },
      { name: 'TestAsyncService' },
    );

    // Start initialization
    const initPromise = factory.getInstance({ value: 1 });

    // Reset immediately
    await factory.reset();

    // Should be able to get result or instance should be null
    expect(factory.hasInstance()).toBe(false);

    // Complete original promise
    await initPromise;
  });

  it('should use default config when none provided', async () => {
    const factory = createAsyncSingletonFactory(createTestService, {
      name: 'TestAsyncService',
      defaultConfig: { value: 100 },
    });

    const instance = await factory.getInstance();

    expect(instance.config.value).toBe(100);
  });
});

describe('compareConfig option', () => {
  interface TestConfig {
    value: number;
    debug?: boolean;
  }

  class TestService {
    constructor(public config: TestConfig) {}
  }

  it('should use custom compareConfig to determine warnings', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      compareConfig: (existing, provided) => {
        // Only warn if value changed
        if (existing && existing.value !== provided.value) {
          return { shouldWarn: true, message: 'Value changed!' };
        }
        return { shouldWarn: false };
      },
    });

    factory.getInstance({ value: 1, debug: false });

    // Same value, different debug - should not warn
    factory.getInstance({ value: 1, debug: true });
    expect(mockLogger).not.toHaveBeenCalled();

    // Different value - should warn
    factory.getInstance({ value: 2 });
    expect(mockLogger).toHaveBeenCalledWith('Value changed!');
  });

  it('should throw when shouldThrow is true', () => {
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      compareConfig: (existing, provided) => {
        if (existing && existing.value !== provided.value) {
          return { shouldWarn: false, shouldThrow: true, message: 'Config mismatch!' };
        }
        return { shouldWarn: false };
      },
    });

    factory.getInstance({ value: 1 });

    expect(() => factory.getInstance({ value: 2 })).toThrow('Config mismatch!');
  });

  it('should use default message when compareConfig returns no message', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      compareConfig: () => ({ shouldWarn: true }),
    });

    factory.getInstance({ value: 1 });
    factory.getInstance({ value: 2 });

    expect(mockLogger).toHaveBeenCalledWith(
      expect.stringContaining('[TestService] Instance already exists'),
    );
  });
});

describe('createDeepEqualComparison', () => {
  interface TestConfig {
    value: number;
    nested?: { foo: string };
  }

  class TestService {
    constructor(public config: TestConfig) {}
  }

  // Simple deep equal for testing
  const simpleIsEqual = (a: unknown, b: unknown): boolean =>
    JSON.stringify(a) === JSON.stringify(b);

  it('should not warn when config is equal', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      compareConfig: createDeepEqualComparison(simpleIsEqual, 'TestService'),
    });

    factory.getInstance({ value: 1, nested: { foo: 'bar' } });
    factory.getInstance({ value: 1, nested: { foo: 'bar' } });

    expect(mockLogger).not.toHaveBeenCalled();
  });

  it('should warn when config differs', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      compareConfig: createDeepEqualComparison(simpleIsEqual, 'TestService'),
    });

    factory.getInstance({ value: 1 });
    factory.getInstance({ value: 2 });

    expect(mockLogger).toHaveBeenCalledWith(
      expect.stringContaining('[TestService] Config ignored'),
    );
  });

  it('should not warn on first call', () => {
    const mockLogger = vi.fn();
    const factory = createSingletonFactory((config: TestConfig) => new TestService(config), {
      name: 'TestService',
      logger: mockLogger,
      compareConfig: createDeepEqualComparison(simpleIsEqual, 'TestService'),
    });

    factory.getInstance({ value: 1 });

    expect(mockLogger).not.toHaveBeenCalled();
  });
});

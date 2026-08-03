/**
 * Transport Layer for Telemetry Data
 * @module core/transport
 */

import type { TransportConfig } from '../types';

/**
 * Default transport configuration
 */
export const DEFAULT_TRANSPORT_CONFIG: TransportConfig = {
  batchSize: 512,
  flushInterval: 5000,
  maxQueueSize: 2048,
  timeout: 10000,
  retryAttempts: 3,
  compression: true,
};

/**
 * Merge transport config with defaults
 */
export function resolveTransportConfig(config?: Partial<TransportConfig>): TransportConfig {
  return {
    ...DEFAULT_TRANSPORT_CONFIG,
    ...config,
  };
}

/**
 * Transport state for managing queues and batching
 */
interface TransportState {
  queue: unknown[];
  isFlushPending: boolean;
  flushTimer: ReturnType<typeof setTimeout> | null;
  retryCount: number;
}

/**
 * Create a transport instance
 */
export function createTransport(config: TransportConfig) {
  const state: TransportState = {
    queue: [],
    isFlushPending: false,
    flushTimer: null,
    retryCount: 0,
  };

  /**
   * Add item to queue
   */
  function enqueue(item: unknown): void {
    if (state.queue.length >= config.maxQueueSize) {
      // Drop oldest items when queue is full
      state.queue.shift();
      console.warn('[FoundationMetrics] Queue full, dropping oldest item');
    }

    state.queue.push(item);

    // Schedule flush if not already pending
    if (!state.isFlushPending) {
      scheduleFlush();
    }

    // Flush immediately if batch size reached
    if (state.queue.length >= config.batchSize) {
      flush();
    }
  }

  /**
   * Schedule a flush
   */
  function scheduleFlush(): void {
    if (state.flushTimer) {
      return;
    }

    state.isFlushPending = true;
    state.flushTimer = setTimeout(() => {
      flush();
    }, config.flushInterval);
  }

  /**
   * Flush the queue
   */
  async function flush(): Promise<void> {
    if (state.flushTimer) {
      clearTimeout(state.flushTimer);
      state.flushTimer = null;
    }

    state.isFlushPending = false;

    if (state.queue.length === 0) {
      return;
    }

    // Take items from queue
    const items = state.queue.splice(0, config.batchSize);

    try {
      await sendBatch(items);
      state.retryCount = 0;
    } catch (error) {
      // Re-queue items on failure
      if (state.retryCount < config.retryAttempts) {
        state.retryCount++;
        state.queue.unshift(...items);
        console.warn(
          `[FoundationMetrics] Send failed, retry ${state.retryCount}/${config.retryAttempts}`,
        );
        scheduleFlush();
      } else {
        console.error('[FoundationMetrics] Max retries reached, dropping batch');
        state.retryCount = 0;
      }
    }

    // Continue flushing if more items in queue
    if (state.queue.length > 0) {
      scheduleFlush();
    }
  }

  /**
   * Send a batch of items
   */
  async function sendBatch(_items: unknown[]): Promise<void> {
    // This is handled by OpenTelemetry exporters
    // This function is kept for custom transport scenarios
  }

  /**
   * Get queue size
   */
  function getQueueSize(): number {
    return state.queue.length;
  }

  /**
   * Clear the queue
   */
  function clear(): void {
    state.queue = [];
    if (state.flushTimer) {
      clearTimeout(state.flushTimer);
      state.flushTimer = null;
    }
    state.isFlushPending = false;
    state.retryCount = 0;
  }

  return {
    enqueue,
    flush,
    getQueueSize,
    clear,
  };
}

/**
 * Beacon transport for sending data on page unload
 */
export function sendBeacon(url: string, data: unknown): boolean {
  if (typeof navigator === 'undefined' || !navigator.sendBeacon) {
    return false;
  }

  try {
    const blob = new Blob([JSON.stringify(data)], {
      type: 'application/json',
    });
    return navigator.sendBeacon(url, blob);
  } catch {
    return false;
  }
}

/**
 * Check if we should use beacon API
 */
export function shouldUseBeacon(): boolean {
  if (typeof document === 'undefined') {
    return false;
  }

  return document.visibilityState === 'hidden';
}

/**
 * Compression utilities
 */
export async function compressData(data: string): Promise<Uint8Array | null> {
  if (typeof CompressionStream === 'undefined') {
    return null;
  }

  try {
    const encoder = new TextEncoder();
    const stream = new Blob([encoder.encode(data)])
      .stream()
      .pipeThrough(new CompressionStream('gzip'));

    const compressedBlob = await new Response(stream).blob();
    return new Uint8Array(await compressedBlob.arrayBuffer());
  } catch {
    return null;
  }
}

/**
 * Check if compression is supported
 */
export function isCompressionSupported(): boolean {
  return typeof CompressionStream !== 'undefined';
}

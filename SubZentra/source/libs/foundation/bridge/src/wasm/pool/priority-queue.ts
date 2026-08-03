/**
 * Priority Queue Implementation
 *
 * A generic priority queue that supports high/normal/low priorities
 * with FIFO ordering within each priority level.
 *
 * Performance characteristics:
 * - enqueue: O(1)
 * - dequeue: O(1)
 * - removeById: O(1) using Map index
 * - remove (predicate): O(n) - requires scanning
 * - find (predicate): O(n) - requires scanning
 *
 * @module wasm/pool/priority-queue
 */

import { PRIORITY } from '../../constants';
import type { PriorityLevel } from '../../constants';

/**
 * Item stored in the queue with priority metadata
 */
interface QueueItem<T> {
  readonly item: T;
  readonly priority: PriorityLevel;
  readonly timestamp: number;
  readonly id: string;
}

/**
 * Priority order for iteration (high > normal > low)
 */
const PRIORITY_ORDER: readonly PriorityLevel[] = [
  PRIORITY.HIGH,
  PRIORITY.NORMAL,
  PRIORITY.LOW,
] as const;

/**
 * Priority Queue with support for high/normal/low priorities
 *
 * Items are dequeued in priority order (high > normal > low).
 * Within the same priority, items are dequeued in FIFO order.
 *
 * Uses a Map index for O(1) ID-based lookups and removals.
 */
export class PriorityQueue<T> {
  /** Priority-based queues for FIFO ordering within each level */
  private readonly queues: Map<PriorityLevel, QueueItem<T>[]> = new Map([
    [PRIORITY.HIGH, []],
    [PRIORITY.NORMAL, []],
    [PRIORITY.LOW, []],
  ]);

  /** Map index for O(1) lookups by ID */
  private readonly idIndex: Map<string, { priority: PriorityLevel; item: QueueItem<T> }> =
    new Map();

  /** Counter for generating unique IDs */
  private idCounter = 0;

  /**
   * Add an item to the queue with the specified priority
   *
   * @param item - The item to enqueue
   * @param priority - Priority level (default: NORMAL)
   * @returns The generated queue item ID
   *
   * Time complexity: O(1)
   */
  enqueue(item: T, priority: PriorityLevel = PRIORITY.NORMAL): string {
    const id = `q_${++this.idCounter}_${Date.now()}`;
    const queueItem: QueueItem<T> = {
      item,
      priority,
      timestamp: Date.now(),
      id,
    };

    // Add to priority queue
    const queue = this.queues.get(priority);
    if (queue) {
      queue.push(queueItem);
    }

    // Add to ID index for O(1) lookup
    this.idIndex.set(id, { priority, item: queueItem });

    return id;
  }

  /**
   * Remove and return the highest priority item
   *
   * @returns The dequeued item or undefined if empty
   *
   * Time complexity: O(1)
   */
  dequeue(): T | undefined {
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (queue && queue.length > 0) {
        const queueItem = queue.shift();
        if (queueItem) {
          // Remove from ID index
          this.idIndex.delete(queueItem.id);
          return queueItem.item;
        }
      }
    }
    return undefined;
  }

  /**
   * Peek at the highest priority item without removing it
   *
   * @returns The next item or undefined if empty
   *
   * Time complexity: O(1)
   */
  peek(): T | undefined {
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (queue && queue.length > 0) {
        return queue[0].item;
      }
    }
    return undefined;
  }

  /**
   * Remove an item matching the predicate
   *
   * @param predicate - Function to match the item to remove
   * @returns The removed item or undefined if not found
   *
   * Time complexity: O(n) - requires scanning all queues
   */
  remove(predicate: (item: T) => boolean): T | undefined {
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (!queue) continue;

      const index = queue.findIndex((q) => predicate(q.item));
      if (index !== -1) {
        const removed = queue.splice(index, 1)[0];
        // Remove from ID index
        this.idIndex.delete(removed.id);
        return removed.item;
      }
    }
    return undefined;
  }

  /**
   * Remove an item by its queue ID
   *
   * @param id - The queue item ID returned from enqueue
   * @returns The removed item or undefined if not found
   *
   * Time complexity: O(1) for lookup, O(n) worst case for array removal
   * Note: Uses Map index for O(1) lookup, but array splice is still O(n)
   */
  removeById(id: string): T | undefined {
    const indexed = this.idIndex.get(id);
    if (!indexed) {
      return undefined;
    }

    const { priority, item: queueItem } = indexed;
    const queue = this.queues.get(priority);
    if (!queue) {
      return undefined;
    }

    // Find and remove from queue array
    const index = queue.findIndex((q) => q.id === id);
    if (index !== -1) {
      queue.splice(index, 1);
    }

    // Remove from ID index
    this.idIndex.delete(id);

    return queueItem.item;
  }

  /**
   * Get an item by its queue ID without removing it
   *
   * @param id - The queue item ID returned from enqueue
   * @returns The item or undefined if not found
   *
   * Time complexity: O(1)
   */
  getById(id: string): T | undefined {
    const indexed = this.idIndex.get(id);
    return indexed?.item.item;
  }

  /**
   * Check if an item with the given ID exists
   *
   * @param id - The queue item ID to check
   * @returns True if the item exists
   *
   * Time complexity: O(1)
   */
  hasId(id: string): boolean {
    return this.idIndex.has(id);
  }

  /**
   * Find an item matching the predicate without removing it
   *
   * @param predicate - Function to match the item
   * @returns The found item or undefined
   *
   * Time complexity: O(n) - requires scanning all queues
   */
  find(predicate: (item: T) => boolean): T | undefined {
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (!queue) continue;

      const found = queue.find((q) => predicate(q.item));
      if (found) {
        return found.item;
      }
    }
    return undefined;
  }

  /**
   * Check if an item matching the predicate exists
   *
   * @param predicate - Function to match the item
   * @returns True if found
   *
   * Time complexity: O(n) - requires scanning all queues
   */
  has(predicate: (item: T) => boolean): boolean {
    return this.find(predicate) !== undefined;
  }

  /**
   * Get the total number of items across all priorities
   *
   * Time complexity: O(1) - uses index size
   */
  size(): number {
    return this.idIndex.size;
  }

  /**
   * Get the number of items at a specific priority
   *
   * Time complexity: O(1)
   */
  sizeAt(priority: PriorityLevel): number {
    return this.queues.get(priority)?.length ?? 0;
  }

  /**
   * Check if the queue is empty
   *
   * Time complexity: O(1)
   */
  isEmpty(): boolean {
    return this.idIndex.size === 0;
  }

  /**
   * Clear all items from the queue
   *
   * @returns Array of all cleared items
   *
   * Time complexity: O(n)
   */
  clear(): T[] {
    const items: T[] = [];
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (queue) {
        items.push(...queue.map((q) => q.item));
        queue.length = 0;
      }
    }
    this.idIndex.clear();
    return items;
  }

  /**
   * Get all items as an array (in priority order)
   *
   * Time complexity: O(n)
   */
  toArray(): T[] {
    const items: T[] = [];
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (queue) {
        items.push(...queue.map((q) => q.item));
      }
    }
    return items;
  }

  /**
   * Iterate over all items in priority order
   *
   * Time complexity: O(n) for full iteration
   */
  *[Symbol.iterator](): Iterator<T> {
    for (const priority of PRIORITY_ORDER) {
      const queue = this.queues.get(priority);
      if (queue) {
        for (const queueItem of queue) {
          yield queueItem.item;
        }
      }
    }
  }
}

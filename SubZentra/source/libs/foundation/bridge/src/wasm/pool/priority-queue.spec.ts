/**
 * Tests for PriorityQueue
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { PriorityQueue } from './priority-queue';

describe('PriorityQueue', () => {
  let queue: PriorityQueue<string>;

  beforeEach(() => {
    queue = new PriorityQueue<string>();
  });

  describe('enqueue', () => {
    it('should add items with default normal priority', () => {
      queue.enqueue('item1');
      queue.enqueue('item2');

      expect(queue.size()).toBe(2);
      expect(queue.sizeAt('normal')).toBe(2);
    });

    it('should add items with specified priority', () => {
      queue.enqueue('high', 'high');
      queue.enqueue('low', 'low');
      queue.enqueue('normal', 'normal');

      expect(queue.sizeAt('high')).toBe(1);
      expect(queue.sizeAt('normal')).toBe(1);
      expect(queue.sizeAt('low')).toBe(1);
    });

    it('should return a unique queue ID', () => {
      const id1 = queue.enqueue('item1');
      const id2 = queue.enqueue('item2');

      expect(id1).toMatch(/^q_\d+_\d+$/);
      expect(id2).toMatch(/^q_\d+_\d+$/);
      expect(id1).not.toBe(id2);
    });
  });

  describe('dequeue', () => {
    it('should dequeue items in priority order (high first)', () => {
      queue.enqueue('normal', 'normal');
      queue.enqueue('high', 'high');
      queue.enqueue('low', 'low');

      expect(queue.dequeue()).toBe('high');
      expect(queue.dequeue()).toBe('normal');
      expect(queue.dequeue()).toBe('low');
    });

    it('should maintain FIFO within same priority', () => {
      queue.enqueue('first', 'normal');
      queue.enqueue('second', 'normal');
      queue.enqueue('third', 'normal');

      expect(queue.dequeue()).toBe('first');
      expect(queue.dequeue()).toBe('second');
      expect(queue.dequeue()).toBe('third');
    });

    it('should return undefined when empty', () => {
      expect(queue.dequeue()).toBeUndefined();
    });

    it('should handle mixed priorities correctly', () => {
      queue.enqueue('normal1', 'normal');
      queue.enqueue('high1', 'high');
      queue.enqueue('low1', 'low');
      queue.enqueue('high2', 'high');
      queue.enqueue('normal2', 'normal');

      expect(queue.dequeue()).toBe('high1');
      expect(queue.dequeue()).toBe('high2');
      expect(queue.dequeue()).toBe('normal1');
      expect(queue.dequeue()).toBe('normal2');
      expect(queue.dequeue()).toBe('low1');
    });
  });

  describe('peek', () => {
    it('should return highest priority item without removing', () => {
      queue.enqueue('normal', 'normal');
      queue.enqueue('high', 'high');

      expect(queue.peek()).toBe('high');
      expect(queue.size()).toBe(2);
    });

    it('should return undefined when empty', () => {
      expect(queue.peek()).toBeUndefined();
    });
  });

  describe('remove', () => {
    it('should remove item matching predicate', () => {
      queue.enqueue('item1', 'normal');
      queue.enqueue('item2', 'normal');
      queue.enqueue('item3', 'normal');

      const removed = queue.remove((item) => item === 'item2');

      expect(removed).toBe('item2');
      expect(queue.size()).toBe(2);
    });

    it('should remove from any priority queue', () => {
      queue.enqueue('high', 'high');
      queue.enqueue('normal', 'normal');
      queue.enqueue('low', 'low');

      const removed = queue.remove((item) => item === 'normal');

      expect(removed).toBe('normal');
      expect(queue.sizeAt('normal')).toBe(0);
    });

    it('should return undefined if not found', () => {
      queue.enqueue('item1');

      const removed = queue.remove((item) => item === 'nonexistent');

      expect(removed).toBeUndefined();
    });
  });

  describe('removeById', () => {
    it('should remove item by queue ID', () => {
      const id = queue.enqueue('target');
      queue.enqueue('other');

      const removed = queue.removeById(id);

      expect(removed).toBe('target');
      expect(queue.size()).toBe(1);
    });

    it('should return undefined for invalid ID', () => {
      queue.enqueue('item');

      const removed = queue.removeById('invalid_id');

      expect(removed).toBeUndefined();
    });
  });

  describe('find', () => {
    it('should find item matching predicate', () => {
      queue.enqueue('item1', 'low');
      queue.enqueue('item2', 'high');

      const found = queue.find((item) => item === 'item1');

      expect(found).toBe('item1');
    });

    it('should return undefined if not found', () => {
      queue.enqueue('item1');

      const found = queue.find((item) => item === 'nonexistent');

      expect(found).toBeUndefined();
    });
  });

  describe('has', () => {
    it('should return true if item exists', () => {
      queue.enqueue('item1');

      expect(queue.has((item) => item === 'item1')).toBe(true);
    });

    it('should return false if item does not exist', () => {
      queue.enqueue('item1');

      expect(queue.has((item) => item === 'nonexistent')).toBe(false);
    });
  });

  describe('size and isEmpty', () => {
    it('should report correct size', () => {
      expect(queue.size()).toBe(0);

      queue.enqueue('item1');
      expect(queue.size()).toBe(1);

      queue.enqueue('item2');
      expect(queue.size()).toBe(2);

      queue.dequeue();
      expect(queue.size()).toBe(1);
    });

    it('should report isEmpty correctly', () => {
      expect(queue.isEmpty()).toBe(true);

      queue.enqueue('item');
      expect(queue.isEmpty()).toBe(false);

      queue.dequeue();
      expect(queue.isEmpty()).toBe(true);
    });

    it('should report size at specific priority', () => {
      queue.enqueue('high1', 'high');
      queue.enqueue('high2', 'high');
      queue.enqueue('normal1', 'normal');

      expect(queue.sizeAt('high')).toBe(2);
      expect(queue.sizeAt('normal')).toBe(1);
      expect(queue.sizeAt('low')).toBe(0);
    });
  });

  describe('clear', () => {
    it('should clear all items and return them', () => {
      queue.enqueue('high', 'high');
      queue.enqueue('normal', 'normal');
      queue.enqueue('low', 'low');

      const cleared = queue.clear();

      expect(cleared).toHaveLength(3);
      expect(queue.isEmpty()).toBe(true);
    });

    it('should return items in priority order', () => {
      queue.enqueue('normal', 'normal');
      queue.enqueue('high', 'high');
      queue.enqueue('low', 'low');

      const cleared = queue.clear();

      expect(cleared).toEqual(['high', 'normal', 'low']);
    });
  });

  describe('toArray', () => {
    it('should return all items in priority order', () => {
      queue.enqueue('normal', 'normal');
      queue.enqueue('high', 'high');
      queue.enqueue('low', 'low');

      const array = queue.toArray();

      expect(array).toEqual(['high', 'normal', 'low']);
    });

    it('should not modify the queue', () => {
      queue.enqueue('item1');
      queue.enqueue('item2');

      queue.toArray();

      expect(queue.size()).toBe(2);
    });
  });

  describe('iterator', () => {
    it('should iterate in priority order', () => {
      queue.enqueue('normal', 'normal');
      queue.enqueue('high', 'high');
      queue.enqueue('low', 'low');

      const items = [...queue];

      expect(items).toEqual(['high', 'normal', 'low']);
    });
  });
});

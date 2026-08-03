/**
 * Class name utility - combines clsx and tailwind-merge
 * @module utils/cn
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Combines class names using clsx and merges Tailwind classes using tailwind-merge.
 * This utility intelligently handles Tailwind class conflicts, where the last class wins.
 *
 * @example
 * cn('px-2 py-1', 'px-4') // => 'py-1 px-4' (px-4 wins)
 * cn('text-red-500', condition && 'text-blue-500')
 * cn(['flex', 'items-center'], { 'opacity-50': disabled })
 *
 * @param inputs - Class values to combine (strings, arrays, objects, etc.)
 * @returns Merged and deduplicated class string
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export type { ClassValue };

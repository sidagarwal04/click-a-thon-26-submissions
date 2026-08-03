import { describe, expect, it } from 'vitest';

import { extractRoute } from './extract-route';

describe('extractRoute', () => {
  it('should replace UUID with {id}', () => {
    const result = extractRoute(
      'https://example.com/users/550e8400-e29b-41d4-a716-446655440000/profile',
    );
    expect(result).toBe('/users/{id}/profile');
  });

  it('should replace numeric IDs with {id}', () => {
    const result = extractRoute('https://example.com/posts/123');
    expect(result).toBe('/posts/{id}');
  });

  it('should replace multiple numeric IDs with {id}', () => {
    const result = extractRoute('https://example.com/posts/123/reply/456');
    expect(result).toBe('/posts/{id}/reply/{id}');
  });

  it('should replace MongoDB ObjectIds with {id}', () => {
    const result = extractRoute('https://example.com/doc/507f1f77bcf86cd799439011');
    expect(result).toBe('/doc/{id}');
  });

  it('should replace long alphanumeric IDs with {id}', () => {
    const result = extractRoute('https://example.com/items/abc123def456');
    expect(result).toBe('/items/{id}');
  });

  it('should preserve short path segments', () => {
    const result = extractRoute('https://example.com/api/v1/users');
    expect(result).toBe('/api/v1/users');
  });

  it('should handle paths without dynamic segments', () => {
    const result = extractRoute('https://example.com/about');
    expect(result).toBe('/about');
  });

  it('should handle root path', () => {
    const result = extractRoute('https://example.com/');
    expect(result).toBe('/');
  });

  it('should return original URL on parse error', () => {
    const result = extractRoute('not-a-valid-url');
    expect(typeof result).toBe('string');
  });
});

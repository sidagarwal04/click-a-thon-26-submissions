import { Home, Search, User } from 'lucide-react';
import { beforeEach, describe, expect, it } from 'vitest';

import { clearRegistry, getAllIconNames, getIcon, hasIcon, registerIcon } from './registry';
import type { IconName } from './registry';

describe('Icon Registry', () => {
  beforeEach(() => {
    clearRegistry();
  });

  describe('registerIcon', () => {
    it('should register an icon successfully', () => {
      registerIcon({ name: 'home', component: Home });
      expect(hasIcon('home')).toBe(true);
    });

    it('should throw error when registering duplicate icon', () => {
      registerIcon({ name: 'home', component: Home });
      expect(() => {
        registerIcon({ name: 'home', component: Home });
      }).toThrow('Icon "home" is already registered');
    });

    it('should allow registering multiple different icons', () => {
      registerIcon({ name: 'home', component: Home });
      registerIcon({ name: 'search', component: Search });
      registerIcon({ name: 'user', component: User });

      expect(hasIcon('home')).toBe(true);
      expect(hasIcon('search')).toBe(true);
      expect(hasIcon('user')).toBe(true);
    });
  });

  describe('getIcon', () => {
    it('should return registered icon', () => {
      registerIcon({ name: 'home', component: Home });
      const icon = getIcon('home');
      expect(icon).toBe(Home);
    });

    it('should return undefined for unregistered icon', () => {
      const icon = getIcon('non-existent' as IconName);
      expect(icon).toBeUndefined();
    });
  });

  describe('hasIcon', () => {
    it('should return true for registered icon', () => {
      registerIcon({ name: 'home', component: Home });
      expect(hasIcon('home')).toBe(true);
    });

    it('should return false for unregistered icon', () => {
      expect(hasIcon('non-existent' as IconName)).toBe(false);
    });
  });

  describe('getAllIconNames', () => {
    it('should return empty array when no icons are registered', () => {
      expect(getAllIconNames()).toEqual([]);
    });

    it('should return all registered icon names', () => {
      registerIcon({ name: 'home', component: Home });
      registerIcon({ name: 'search', component: Search });
      registerIcon({ name: 'user', component: User });

      const names = getAllIconNames();
      expect(names).toContain('home');
      expect(names).toContain('search');
      expect(names).toContain('user');
      expect(names.length).toBe(3);
    });
  });

  describe('clearRegistry', () => {
    it('should clear all registered icons', () => {
      registerIcon({ name: 'home', component: Home });
      registerIcon({ name: 'search', component: Search });

      expect(hasIcon('home')).toBe(true);
      expect(hasIcon('search')).toBe(true);

      clearRegistry();

      expect(hasIcon('home')).toBe(false);
      expect(hasIcon('search')).toBe(false);
      expect(getAllIconNames()).toEqual([]);
    });
  });
});

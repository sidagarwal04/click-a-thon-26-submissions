/**
 * Tests for auth types
 *
 * Tests the getUserPermissions function.
 */

import { describe, expect, it } from 'vitest';

import { getUserPermissions, type UserRole } from './types';

describe('getUserPermissions', () => {
  it('should grant owner all permissions', () => {
    const perms = getUserPermissions('owner');
    expect(perms.canManageUsers).toBe(true);
    expect(perms.canManageTenant).toBe(true);
    expect(perms.canViewAnalytics).toBe(true);
    expect(perms.canExportData).toBe(true);
    expect(perms.canConfigureIntegrations).toBe(true);
  });

  it('should grant admin all except canManageTenant', () => {
    const perms = getUserPermissions('admin');
    expect(perms.canManageUsers).toBe(true);
    expect(perms.canManageTenant).toBe(false);
    expect(perms.canViewAnalytics).toBe(true);
    expect(perms.canExportData).toBe(true);
    expect(perms.canConfigureIntegrations).toBe(true);
  });

  it('should grant member view analytics and export', () => {
    const perms = getUserPermissions('member');
    expect(perms.canManageUsers).toBe(false);
    expect(perms.canManageTenant).toBe(false);
    expect(perms.canViewAnalytics).toBe(true);
    expect(perms.canExportData).toBe(true);
    expect(perms.canConfigureIntegrations).toBe(false);
  });

  it('should grant viewer only analytics viewing', () => {
    const perms = getUserPermissions('viewer');
    expect(perms.canManageUsers).toBe(false);
    expect(perms.canManageTenant).toBe(false);
    expect(perms.canViewAnalytics).toBe(true);
    expect(perms.canExportData).toBe(false);
    expect(perms.canConfigureIntegrations).toBe(false);
  });

  it('should grant guest no permissions', () => {
    const perms = getUserPermissions('guest');
    expect(perms.canManageUsers).toBe(false);
    expect(perms.canManageTenant).toBe(false);
    expect(perms.canViewAnalytics).toBe(false);
    expect(perms.canExportData).toBe(false);
    expect(perms.canConfigureIntegrations).toBe(false);
  });

  it('should have progressively fewer permissions from owner to guest', () => {
    const roles: UserRole[] = ['owner', 'admin', 'member', 'viewer', 'guest'];
    const permCounts = roles.map((role) => {
      const perms = getUserPermissions(role);
      return Object.values(perms).filter(Boolean).length;
    });

    // Each role should have same or fewer permissions than the previous
    for (let i = 1; i < permCounts.length; i++) {
      expect(permCounts[i]).toBeLessThanOrEqual(permCounts[i - 1]);
    }
  });
});

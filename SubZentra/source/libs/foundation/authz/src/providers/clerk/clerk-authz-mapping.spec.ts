import { describe, expect, it } from 'vitest';

import { resolveClerkPermissionKey, resolveClerkRoleKey } from './clerk-authz-mapping';

describe('clerk authz mapping', () => {
  it('maps action/resource checks with the default permission template', () => {
    expect(
      resolveClerkPermissionKey({
        action: 'view',
        resource: 'analytics',
      }),
    ).toBe('org:analytics:view');
  });

  it('supports explicit permission key overrides', () => {
    expect(
      resolveClerkPermissionKey(
        {
          action: 'view',
          resource: 'analytics',
        },
        {
          permissionMap: [
            {
              action: 'view',
              resource: 'analytics',
              clerkPermission: 'org:analytics:read',
            },
          ],
        },
      ),
    ).toBe('org:analytics:read');
  });

  it('returns null when no permission mapping is available', () => {
    expect(
      resolveClerkPermissionKey(
        {
          action: 'export',
          resource: 'reports',
        },
        {
          permissionTemplate: null,
        },
      ),
    ).toBeNull();
  });

  it('supports role aliases', () => {
    expect(
      resolveClerkRoleKey('owner', {
        roleMap: {
          owner: 'org:admin',
        },
      }),
    ).toBe('org:admin');
  });
});

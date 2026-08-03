import type { AuthzCheck } from '../../core';

export interface ClerkAuthzPermissionMapping {
  readonly resource: string;
  readonly action: string;
  readonly clerkPermission: string;
}

export type ClerkAuthzPermissionTemplate = string | ((check: AuthzCheck) => string | null) | null;

export interface ClerkAuthzMappingOptions {
  readonly permissionMap?: readonly ClerkAuthzPermissionMapping[];
  readonly permissionTemplate?: ClerkAuthzPermissionTemplate;
  readonly roleMap?: Readonly<Record<string, string>>;
}

const DEFAULT_PERMISSION_TEMPLATE = 'org:{resource}:{action}';

const applyTemplate = (template: string, check: AuthzCheck): string =>
  template.replace(/\{resource\}/g, check.resource).replace(/\{action\}/g, check.action);

export const resolveClerkPermissionKey = (
  check: AuthzCheck,
  options: ClerkAuthzMappingOptions = {},
): string | null => {
  const override = options.permissionMap?.find(
    (mapping) => mapping.resource === check.resource && mapping.action === check.action,
  );

  if (override) {
    return override.clerkPermission;
  }

  const template =
    options.permissionTemplate === undefined
      ? DEFAULT_PERMISSION_TEMPLATE
      : options.permissionTemplate;

  if (template === null) {
    return null;
  }

  return typeof template === 'function' ? template(check) : applyTemplate(template, check);
};

export const resolveClerkRoleKey = (
  role: string,
  options: ClerkAuthzMappingOptions = {},
): string => {
  const mappedRole = options.roleMap?.[role] ?? role;
  return mappedRole.startsWith('org:') ? mappedRole : `org:${mappedRole}`;
};

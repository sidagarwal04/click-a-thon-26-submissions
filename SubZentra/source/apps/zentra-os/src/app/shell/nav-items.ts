import type { IconName } from '@open-zentra/foundation-icons';

export interface NavItem {
  readonly label: string;
  readonly to: string;
  readonly icon: IconName;
  /** Extra path prefixes this item stays selected for. */
  readonly matches?: readonly string[];
}

/**
 * The product's destinations, in the order the rail lists them.
 *
 * Investigations is the launcher at `/`; everything else is a Phase 2 page and
 * currently answers with a placeholder rather than a dead link.
 */
export const navItems: readonly NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: 'grid' },
  { label: 'Investigations', to: '/', icon: 'search', matches: ['/investigations'] },
  { label: 'Datasets', to: '/datasets', icon: 'database' },
  { label: 'Chat', to: '/chat', icon: 'message_square' },
  { label: 'Connections', to: '/connections', icon: 'network' },
  { label: 'Settings', to: '/settings', icon: 'settings' },
];

/**
 * Whether a rail item owns the current location.
 *
 * `/` would prefix-match every path, so the launcher matches exactly and names
 * the investigation routes it also covers.
 */
export const isNavItemActive = (item: NavItem, pathname: string): boolean => {
  if (pathname === item.to) return true;
  if (item.to !== '/' && pathname.startsWith(`${item.to}/`)) return true;
  return (item.matches ?? []).some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
};

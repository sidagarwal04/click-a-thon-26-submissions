import { useState, type ReactNode } from 'react';

import { useAuth } from '@open-zentra/foundation-auth';
import { Avatar, Button, IconButton, SideNav, Tooltip } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { Link, useLocation } from 'react-router-dom';

import type { IdentityContext, ReadinessResponse } from '../types';
import { isNavItemActive, navItems } from './nav-items';
import { ProductMark } from './product-mark';

interface AppShellProps {
  readonly children: ReactNode;
  readonly identity: IdentityContext;
  readonly readiness: ReadinessResponse | undefined;
}

/**
 * Which tenant this is and whether its dependencies answered.
 *
 * It sits in the rail rather than in a bar across every page: it is context for
 * the whole session, not a heading for the page being read.
 */
const WorkspaceLockup = ({
  identity,
  readiness,
}: {
  readonly identity: IdentityContext;
  readonly readiness: ReadinessResponse | undefined;
}) => {
  const ready = readiness?.status === 'ready';
  return (
    <div className="mt-4 flex flex-col gap-1 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
      <span className="flex items-center gap-2 text-foreground">
        <i
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${ready ? 'bg-primary' : 'bg-warning'}`}
          aria-hidden="true"
        />
        <span className="truncate">{identity.tenant_name}</span>
      </span>
      <span>
        {identity.role} · {ready ? 'foundation ready' : 'dependency review'}
      </span>
    </div>
  );
};

/**
 * The frame every authenticated page renders inside: the navigation rail, and
 * the page itself. Nothing is drawn above the page — a section of chrome
 * repeated on every route earns its space only if it does something.
 */
export const AppShell = ({ children, identity, readiness }: AppShellProps) => {
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const railFooter = (
    <>
      <IconButton
        aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        intent="ghost"
        size="sm"
        className={collapsed ? undefined : 'self-end'}
        onClick={() => setCollapsed((open) => !open)}
      >
        <Icon name={collapsed ? 'chevron_right' : 'chevron_left'} size="sm" />
      </IconButton>

      {/* Collapsed, the primary action is a tile the same size as a nav item,
          so the rail stays one column of squares. */}
      {collapsed ? (
        <Tooltip content="New analysis" side="right" sideOffset={10}>
          <Button
            component={Link}
            to="/"
            aria-label="New analysis"
            className="h-11 w-11 p-0"
          >
            <Icon name="plus" size="sm" />
          </Button>
        </Tooltip>
      ) : (
        <Button component={Link} to="/" fullWidth start={<Icon name="plus" size="sm" />}>
          New analysis
        </Button>
      )}

      {collapsed ? null : (
        <>
          <a
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-foreground-muted no-underline hover:text-foreground"
            href="https://github.com/openzentra/nexus"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="file_text" size="sm" />
            Docs
          </a>
          <a
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-foreground-muted no-underline hover:text-foreground"
            href="https://github.com/openzentra/nexus/issues"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="help_circle" size="sm" />
            Help
          </a>
        </>
      )}

      <div className="mt-1 w-full border-t border-border pt-3">
        <Tooltip content={`Sign out of ${user?.email ?? 'this account'}`} side="right" sideOffset={10}>
          <button
            type="button"
            onClick={() => void logout()}
            className={`flex items-center gap-2 rounded-md text-left text-sm text-foreground-muted transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
              collapsed ? 'h-11 w-11 justify-center p-0' : 'w-full px-3 py-2'
            }`}
          >
            <Avatar size="xs" name={user?.email ?? 'Account'} />
            {collapsed ? null : (
              <>
                <span className="min-w-0 truncate">{user?.email ?? 'Account'}</span>
                <Icon name="log_out" size="sm" className="ml-auto shrink-0" />
              </>
            )}
            <span className="sr-only">Sign out</span>
          </button>
        </Tooltip>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-background text-foreground">
      <SideNav
        aria-label="Primary"
        width={collapsed ? 'compact' : 'default'}
        brand={
          <>
            <ProductMark showRelease compact={collapsed} />
            {collapsed ? null : <WorkspaceLockup identity={identity} readiness={readiness} />}
          </>
        }
        footer={railFooter}
      >
        {navItems.map((item) => (
          <SideNav.Item
            key={item.to}
            component={Link}
            to={item.to}
            icon={<Icon name={item.icon} size="sm" />}
            active={isNavItemActive(item, pathname)}
          >
            {item.label}
          </SideNav.Item>
        ))}
      </SideNav>

      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
};

import { render, screen } from '@testing-library/react';

import { describeComponent } from '../../test/describe-component';
import { SideNav, SideNavModifiers, SideNavVariants } from './index';

describeComponent(<SideNav>Rail</SideNav>, {
  name: 'SideNav',
  rootInstanceOf: window.HTMLElement,
  variants: SideNavVariants,
  modifiers: SideNavModifiers,
  shouldSupportPolymorphism: true,
});

describe('SideNav composition', () => {
  it('renders brand and footer slots around the item list', () => {
    render(
      <SideNav aria-label="Primary" brand={<span>Oddessy</span>} footer={<span>Docs</span>}>
        <SideNav.Item href="/">Dashboard</SideNav.Item>
      </SideNav>,
    );

    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();
    expect(screen.getByText('Oddessy')).toBeTruthy();
    expect(screen.getByText('Docs')).toBeTruthy();
  });

  it('keeps item labels reachable when collapsed', () => {
    render(
      <SideNav aria-label="Primary" width="compact">
        <SideNav.Item href="/chat">Chat</SideNav.Item>
      </SideNav>,
    );

    expect(screen.getByRole('navigation', { name: 'Primary' }).dataset.collapsed).toBe('true');
    // Named, not just drawn: a collapsed rail that dropped its labels would
    // leave every link anonymous to a screen reader.
    expect(screen.getByRole('link', { name: 'Chat' })).toBeTruthy();
  });

  it('announces the active item rather than only colouring it', () => {
    render(
      <SideNav aria-label="Primary">
        <SideNav.Item href="/">Dashboard</SideNav.Item>
        <SideNav.Item href="/chat" active>
          Chat
        </SideNav.Item>
      </SideNav>,
    );

    expect(screen.getByRole('link', { name: 'Chat' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Dashboard' }).getAttribute('aria-current')).toBeNull();
  });
});

import type { Meta, StoryObj } from '@storybook/react';

import { Button } from '../button';
import { Input } from '../input';
import { Drawer } from './drawer';

const meta = {
  title: 'Components/Drawer',
  component: Drawer,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    direction: {
      control: 'select',
      options: ['left', 'right', 'top', 'bottom'],
    },
    size: {
      control: 'select',
      options: ['auto', '1/3', '1/2', '2/3', 'full'],
    },
  },
} satisfies Meta<typeof Drawer>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default drawer (slides from right)
 */
export const Default: Story = {
  render: () => (
    <Drawer direction="right" size="1/3">
      <Drawer.Trigger>
        <Button>Open Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Settings</Drawer.Title>
          <Drawer.Description>Manage your account settings and preferences.</Drawer.Description>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input placeholder="Enter your name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" placeholder="Enter your email" />
            </div>
          </div>
        </Drawer.Body>
        <Drawer.Footer>
          <Drawer.Close>
            <Button intent="secondary">Cancel</Button>
          </Drawer.Close>
          <Button>Save changes</Button>
        </Drawer.Footer>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * Left drawer
 */
export const LeftDrawer: Story = {
  render: () => (
    <Drawer direction="left" size="1/3">
      <Drawer.Trigger>
        <Button>Open Left Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Navigation</Drawer.Title>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <nav className="space-y-2">
            {['Dashboard', 'Projects', 'Team', 'Settings'].map((item) => (
              <a key={item} href="#" className="block rounded-md px-3 py-2 text-sm hover:bg-muted">
                {item}
              </a>
            ))}
          </nav>
        </Drawer.Body>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * Top drawer
 */
export const TopDrawer: Story = {
  render: () => (
    <Drawer direction="top" size="auto">
      <Drawer.Trigger>
        <Button>Open Top Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Search</Drawer.Title>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <Input placeholder="Search for anything..." className="w-full" />
        </Drawer.Body>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * Bottom drawer
 */
export const BottomDrawer: Story = {
  render: () => (
    <Drawer direction="bottom" size="auto">
      <Drawer.Trigger>
        <Button>Open Bottom Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Actions</Drawer.Title>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <div className="grid grid-cols-3 gap-4">
            {['Share', 'Copy', 'Download', 'Edit', 'Delete', 'Archive'].map((action) => (
              <Button key={action} intent="secondary" className="h-20">
                {action}
              </Button>
            ))}
          </div>
        </Drawer.Body>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * Half width drawer
 */
export const HalfWidth: Story = {
  render: () => (
    <Drawer direction="right" size="1/2">
      <Drawer.Trigger>
        <Button>Open Half Width Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Details Panel</Drawer.Title>
          <Drawer.Description>View and edit item details.</Drawer.Description>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <p className="text-muted-foreground">This drawer takes up half the screen width.</p>
        </Drawer.Body>
        <Drawer.Footer>
          <Drawer.Close>
            <Button intent="secondary">Close</Button>
          </Drawer.Close>
        </Drawer.Footer>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * Full width drawer
 */
export const FullWidth: Story = {
  render: () => (
    <Drawer direction="right" size="full">
      <Drawer.Trigger>
        <Button>Open Full Width Drawer</Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Full Screen Panel</Drawer.Title>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Full width content area
          </div>
        </Drawer.Body>
      </Drawer.Content>
    </Drawer>
  ),
};

/**
 * All directions showcase
 */
export const AllDirections: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Drawer direction="left" size="1/3">
        <Drawer.Trigger>
          <Button intent="secondary">Left</Button>
        </Drawer.Trigger>
        <Drawer.Content>
          <Drawer.Header>
            <Drawer.Title>Left Drawer</Drawer.Title>
            <Drawer.Close />
          </Drawer.Header>
          <Drawer.Body>
            <p className="text-muted-foreground">Slides in from the left</p>
          </Drawer.Body>
        </Drawer.Content>
      </Drawer>

      <Drawer direction="right" size="1/3">
        <Drawer.Trigger>
          <Button intent="secondary">Right</Button>
        </Drawer.Trigger>
        <Drawer.Content>
          <Drawer.Header>
            <Drawer.Title>Right Drawer</Drawer.Title>
            <Drawer.Close />
          </Drawer.Header>
          <Drawer.Body>
            <p className="text-muted-foreground">Slides in from the right</p>
          </Drawer.Body>
        </Drawer.Content>
      </Drawer>

      <Drawer direction="top" size="auto">
        <Drawer.Trigger>
          <Button intent="secondary">Top</Button>
        </Drawer.Trigger>
        <Drawer.Content>
          <Drawer.Header>
            <Drawer.Title>Top Drawer</Drawer.Title>
            <Drawer.Close />
          </Drawer.Header>
          <Drawer.Body>
            <p className="text-muted-foreground">Slides in from the top</p>
          </Drawer.Body>
        </Drawer.Content>
      </Drawer>

      <Drawer direction="bottom" size="auto">
        <Drawer.Trigger>
          <Button intent="secondary">Bottom</Button>
        </Drawer.Trigger>
        <Drawer.Content>
          <Drawer.Header>
            <Drawer.Title>Bottom Drawer</Drawer.Title>
            <Drawer.Close />
          </Drawer.Header>
          <Drawer.Body>
            <p className="text-muted-foreground">Slides in from the bottom</p>
          </Drawer.Body>
        </Drawer.Content>
      </Drawer>
    </div>
  ),
};

/**
 * Mobile-style drawer
 */
export const MobileMenu: Story = {
  render: () => (
    <Drawer direction="left" size="2/3">
      <Drawer.Trigger>
        <Button intent="secondary" aria-label="Menu">
          ☰
        </Button>
      </Drawer.Trigger>
      <Drawer.Content>
        <Drawer.Header>
          <Drawer.Title>Menu</Drawer.Title>
          <Drawer.Close />
        </Drawer.Header>
        <Drawer.Body>
          <nav className="space-y-1">
            {[
              { icon: '🏠', label: 'Home' },
              { icon: '📊', label: 'Dashboard' },
              { icon: '📁', label: 'Projects' },
              { icon: '👥', label: 'Team' },
              { icon: '📅', label: 'Calendar' },
              { icon: '⚙️', label: 'Settings' },
            ].map((item) => (
              <a
                key={item.label}
                href="#"
                className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-muted"
              >
                <span>{item.icon}</span>
                {item.label}
              </a>
            ))}
          </nav>
        </Drawer.Body>
        <Drawer.Footer>
          <Button intent="secondary" className="w-full">
            Sign Out
          </Button>
        </Drawer.Footer>
      </Drawer.Content>
    </Drawer>
  ),
};

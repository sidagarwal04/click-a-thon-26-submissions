import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from '../button';
import { Menu } from './menu';

const meta = {
  title: 'Components/Menu',
  component: Menu,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
  },
} satisfies Meta<typeof Menu>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default menu
 */
export const Default: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Open Menu</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Item onSelect={() => alert('Profile clicked')}>Profile</Menu.Item>
        <Menu.Item onSelect={() => alert('Settings clicked')}>Settings</Menu.Item>
        <Menu.Separator />
        <Menu.Item onSelect={() => alert('Logout clicked')}>Logout</Menu.Item>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * With icons
 */
export const WithIcons: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Actions</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Item start={<Icon name="user" />}>Profile</Menu.Item>
        <Menu.Item start={<Icon name="settings" />}>Settings</Menu.Item>
        <Menu.Item start={<Icon name="credit-card" />}>Billing</Menu.Item>
        <Menu.Separator />
        <Menu.Item start={<Icon name="log-out" />}>Logout</Menu.Item>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * With shortcuts
 */
export const WithShortcuts: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Edit</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Item start={<Icon name="clipboard" />} end="⌘X">
          Cut
        </Menu.Item>
        <Menu.Item start={<Icon name="copy" />} end="⌘C">
          Copy
        </Menu.Item>
        <Menu.Item start={<Icon name="clipboard" />} end="⌘V">
          Paste
        </Menu.Item>
        <Menu.Separator />
        <Menu.Item start={<Icon name="trash" />} end="⌫">
          Delete
        </Menu.Item>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * With groups
 */
export const WithGroups: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Menu with Groups</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Group>
          <Menu.GroupLabel>Account</Menu.GroupLabel>
          <Menu.Item>Profile</Menu.Item>
          <Menu.Item>Settings</Menu.Item>
        </Menu.Group>
        <Menu.Separator />
        <Menu.Group>
          <Menu.GroupLabel>Team</Menu.GroupLabel>
          <Menu.Item>Invite Members</Menu.Item>
          <Menu.Item>Team Settings</Menu.Item>
        </Menu.Group>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * With checkbox items
 */
export const WithCheckboxItems: Story = {
  render: function CheckboxExample() {
    const [showStatusBar, setShowStatusBar] = useState(true);
    const [showPanel, setShowPanel] = useState(false);
    const [showNotifications, setShowNotifications] = useState(true);

    return (
      <Menu>
        <Menu.Trigger>
          <Button intent="secondary">View Options</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.CheckboxItem checked={showStatusBar} onCheckedChange={setShowStatusBar}>
            Show Status Bar
          </Menu.CheckboxItem>
          <Menu.CheckboxItem checked={showPanel} onCheckedChange={setShowPanel}>
            Show Panel
          </Menu.CheckboxItem>
          <Menu.CheckboxItem checked={showNotifications} onCheckedChange={setShowNotifications}>
            Show Notifications
          </Menu.CheckboxItem>
        </Menu.Content>
      </Menu>
    );
  },
};

/**
 * With radio items
 */
export const WithRadioItems: Story = {
  render: function RadioExample() {
    const [theme, setTheme] = useState('system');

    return (
      <Menu>
        <Menu.Trigger>
          <Button intent="secondary">Theme: {theme}</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.RadioGroup value={theme} onValueChange={setTheme}>
            <Menu.GroupLabel>Theme</Menu.GroupLabel>
            <Menu.RadioItem value="light">Light</Menu.RadioItem>
            <Menu.RadioItem value="dark">Dark</Menu.RadioItem>
            <Menu.RadioItem value="system">System</Menu.RadioItem>
          </Menu.RadioGroup>
        </Menu.Content>
      </Menu>
    );
  },
};

/**
 * With submenu
 */
export const WithSubmenu: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Menu with Submenu</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Item>Back</Menu.Item>
        <Menu.Item>Forward</Menu.Item>
        <Menu.Item>Reload</Menu.Item>
        <Menu.Separator />
        <Menu.Sub>
          <Menu.SubTrigger>More Tools</Menu.SubTrigger>
          <Menu.SubContent>
            <Menu.Item>Save Page As...</Menu.Item>
            <Menu.Item>Create Shortcut...</Menu.Item>
            <Menu.Item>Name Window...</Menu.Item>
            <Menu.Separator />
            <Menu.Item>Developer Tools</Menu.Item>
          </Menu.SubContent>
        </Menu.Sub>
        <Menu.Separator />
        <Menu.Item>Settings</Menu.Item>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * Different sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="flex gap-4">
      <Menu size="sm">
        <Menu.Trigger>
          <Button size="sm">Small</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.Item>Item 1</Menu.Item>
          <Menu.Item>Item 2</Menu.Item>
          <Menu.Item>Item 3</Menu.Item>
        </Menu.Content>
      </Menu>

      <Menu size="md">
        <Menu.Trigger>
          <Button>Medium</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.Item>Item 1</Menu.Item>
          <Menu.Item>Item 2</Menu.Item>
          <Menu.Item>Item 3</Menu.Item>
        </Menu.Content>
      </Menu>

      <Menu size="lg">
        <Menu.Trigger>
          <Button size="lg">Large</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.Item>Item 1</Menu.Item>
          <Menu.Item>Item 2</Menu.Item>
          <Menu.Item>Item 3</Menu.Item>
        </Menu.Content>
      </Menu>
    </div>
  ),
};

/**
 * Disabled items
 */
export const DisabledItems: Story = {
  render: () => (
    <Menu>
      <Menu.Trigger>
        <Button intent="secondary">Some Items Disabled</Button>
      </Menu.Trigger>
      <Menu.Content>
        <Menu.Item>Active Item</Menu.Item>
        <Menu.Item disabled>Disabled Item</Menu.Item>
        <Menu.Item>Another Active Item</Menu.Item>
        <Menu.Separator />
        <Menu.Item disabled>Also Disabled</Menu.Item>
      </Menu.Content>
    </Menu>
  ),
};

/**
 * Complex menu example
 */
export const ComplexExample: Story = {
  render: function ComplexMenu() {
    const [bookmarks, setBookmarks] = useState(true);
    const [fullUrls, setFullUrls] = useState(false);
    const [sortBy, setSortBy] = useState('date');

    return (
      <Menu>
        <Menu.Trigger>
          <Button start={<Icon name="menu" />}>Menu</Button>
        </Menu.Trigger>
        <Menu.Content>
          <Menu.Group>
            <Menu.GroupLabel>Navigation</Menu.GroupLabel>
            <Menu.Item start={<Icon name="home" />}>Home</Menu.Item>
            <Menu.Item start={<Icon name="compass" />}>Explore</Menu.Item>
            <Menu.Item start={<Icon name="star" />}>Favorites</Menu.Item>
          </Menu.Group>

          <Menu.Separator />

          <Menu.Group>
            <Menu.GroupLabel>View Options</Menu.GroupLabel>
            <Menu.CheckboxItem checked={bookmarks} onCheckedChange={setBookmarks}>
              Show Bookmarks
            </Menu.CheckboxItem>
            <Menu.CheckboxItem checked={fullUrls} onCheckedChange={setFullUrls}>
              Show Full URLs
            </Menu.CheckboxItem>
          </Menu.Group>

          <Menu.Separator />

          <Menu.RadioGroup value={sortBy} onValueChange={setSortBy}>
            <Menu.GroupLabel>Sort By</Menu.GroupLabel>
            <Menu.RadioItem value="date">Date</Menu.RadioItem>
            <Menu.RadioItem value="name">Name</Menu.RadioItem>
            <Menu.RadioItem value="size">Size</Menu.RadioItem>
          </Menu.RadioGroup>

          <Menu.Separator />

          <Menu.Sub>
            <Menu.SubTrigger start={<Icon name="share" />}>Share</Menu.SubTrigger>
            <Menu.SubContent>
              <Menu.Item>Email</Menu.Item>
              <Menu.Item>Message</Menu.Item>
              <Menu.Item>Copy Link</Menu.Item>
            </Menu.SubContent>
          </Menu.Sub>

          <Menu.Separator />

          <Menu.Item start={<Icon name="settings" />} end="⌘,">
            Settings
          </Menu.Item>
        </Menu.Content>
      </Menu>
    );
  },
};

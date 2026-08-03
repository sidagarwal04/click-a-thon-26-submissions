import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Badge } from '../badge';
import { Tabs } from './tabs';

const meta = {
  title: 'Components/Tabs',
  component: Tabs,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    variant: {
      control: 'select',
      options: ['default', 'pills', 'underline'],
    },
    fullWidth: {
      control: 'boolean',
    },
  },
  decorators: [
    (Story) => (
      <div className="w-[500px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Tabs>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default tabs
 */
export const Default: Story = {
  render: () => (
    <Tabs defaultValue="account">
      <Tabs.List>
        <Tabs.Trigger value="account">Account</Tabs.Trigger>
        <Tabs.Trigger value="password">Password</Tabs.Trigger>
        <Tabs.Trigger value="notifications">Notifications</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="account">
        <p className="text-sm text-muted-foreground">
          Make changes to your account here. Click save when you're done.
        </p>
      </Tabs.Content>
      <Tabs.Content value="password">
        <p className="text-sm text-muted-foreground">
          Change your password here. After saving, you'll be logged out.
        </p>
      </Tabs.Content>
      <Tabs.Content value="notifications">
        <p className="text-sm text-muted-foreground">Manage your notification preferences here.</p>
      </Tabs.Content>
    </Tabs>
  ),
};

/**
 * Pills variant
 */
export const Pills: Story = {
  render: () => (
    <Tabs defaultValue="overview" variant="pills">
      <Tabs.List>
        <Tabs.Trigger value="overview">Overview</Tabs.Trigger>
        <Tabs.Trigger value="analytics">Analytics</Tabs.Trigger>
        <Tabs.Trigger value="reports">Reports</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="overview">
        <p className="text-sm text-muted-foreground">Overview content goes here.</p>
      </Tabs.Content>
      <Tabs.Content value="analytics">
        <p className="text-sm text-muted-foreground">Analytics content goes here.</p>
      </Tabs.Content>
      <Tabs.Content value="reports">
        <p className="text-sm text-muted-foreground">Reports content goes here.</p>
      </Tabs.Content>
    </Tabs>
  ),
};

/**
 * Underline variant
 */
export const Underline: Story = {
  render: () => (
    <Tabs defaultValue="profile" variant="underline">
      <Tabs.List>
        <Tabs.Trigger value="profile">Profile</Tabs.Trigger>
        <Tabs.Trigger value="settings">Settings</Tabs.Trigger>
        <Tabs.Trigger value="billing">Billing</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="profile">
        <p className="text-sm text-muted-foreground">Your profile information.</p>
      </Tabs.Content>
      <Tabs.Content value="settings">
        <p className="text-sm text-muted-foreground">Application settings.</p>
      </Tabs.Content>
      <Tabs.Content value="billing">
        <p className="text-sm text-muted-foreground">Billing and subscription.</p>
      </Tabs.Content>
    </Tabs>
  ),
};

/**
 * All variants
 */
export const AllVariants: Story = {
  render: () => (
    <div className="space-y-8">
      <div>
        <h3 className="mb-2 text-sm font-medium">Default</h3>
        <Tabs defaultValue="tab1" variant="default">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
            <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Pills</h3>
        <Tabs defaultValue="tab1" variant="pills">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
            <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Underline</h3>
        <Tabs defaultValue="tab1" variant="underline">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
            <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
    </div>
  ),
};

/**
 * Different sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="space-y-8">
      <div>
        <h3 className="mb-2 text-sm font-medium">Small</h3>
        <Tabs defaultValue="tab1" size="sm">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Medium</h3>
        <Tabs defaultValue="tab1" size="md">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Large</h3>
        <Tabs defaultValue="tab1" size="lg">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
          </Tabs.List>
        </Tabs>
      </div>
    </div>
  ),
};

/**
 * Full width tabs
 */
export const FullWidth: Story = {
  render: () => (
    <Tabs defaultValue="tab1" fullWidth>
      <Tabs.List>
        <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
        <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
        <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="tab1">Content 1</Tabs.Content>
      <Tabs.Content value="tab2">Content 2</Tabs.Content>
      <Tabs.Content value="tab3">Content 3</Tabs.Content>
    </Tabs>
  ),
};

/**
 * With icons
 */
export const WithIcons: Story = {
  render: () => (
    <Tabs defaultValue="inbox">
      <Tabs.List>
        <Tabs.Trigger value="inbox" start={<Icon name="inbox" />}>
          Inbox
        </Tabs.Trigger>
        <Tabs.Trigger value="sent" start={<Icon name="send" />}>
          Sent
        </Tabs.Trigger>
        <Tabs.Trigger value="drafts" start={<Icon name="file" />}>
          Drafts
        </Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="inbox">
        <p className="text-sm text-muted-foreground">Your inbox messages.</p>
      </Tabs.Content>
      <Tabs.Content value="sent">
        <p className="text-sm text-muted-foreground">Your sent messages.</p>
      </Tabs.Content>
      <Tabs.Content value="drafts">
        <p className="text-sm text-muted-foreground">Your draft messages.</p>
      </Tabs.Content>
    </Tabs>
  ),
};

/**
 * With badges
 */
export const WithBadges: Story = {
  render: () => (
    <Tabs defaultValue="inbox" variant="underline">
      <Tabs.List>
        <Tabs.Trigger value="inbox" end={<Badge>5</Badge>}>
          Inbox
        </Tabs.Trigger>
        <Tabs.Trigger value="sent">Sent</Tabs.Trigger>
        <Tabs.Trigger value="drafts" end={<Badge intent="secondary">2</Badge>}>
          Drafts
        </Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="inbox">Inbox content</Tabs.Content>
      <Tabs.Content value="sent">Sent content</Tabs.Content>
      <Tabs.Content value="drafts">Drafts content</Tabs.Content>
    </Tabs>
  ),
};

/**
 * Disabled tab
 */
export const DisabledTab: Story = {
  render: () => (
    <Tabs defaultValue="tab1">
      <Tabs.List>
        <Tabs.Trigger value="tab1">Enabled</Tabs.Trigger>
        <Tabs.Trigger value="tab2" disabled>
          Disabled
        </Tabs.Trigger>
        <Tabs.Trigger value="tab3">Enabled</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="tab1">Tab 1 content</Tabs.Content>
      <Tabs.Content value="tab2">Tab 2 content (disabled)</Tabs.Content>
      <Tabs.Content value="tab3">Tab 3 content</Tabs.Content>
    </Tabs>
  ),
};

/**
 * Controlled tabs
 */
export const Controlled: Story = {
  render: function ControlledTabs() {
    const [value, setValue] = useState('tab1');

    return (
      <div className="space-y-4">
        <div className="text-sm">
          Current tab: <code className="bg-muted px-1 py-0.5 rounded">{value}</code>
        </div>
        <Tabs value={value} onValueChange={setValue}>
          <Tabs.List>
            <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
            <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="tab1">Content for tab 1</Tabs.Content>
          <Tabs.Content value="tab2">Content for tab 2</Tabs.Content>
          <Tabs.Content value="tab3">Content for tab 3</Tabs.Content>
        </Tabs>
      </div>
    );
  },
};

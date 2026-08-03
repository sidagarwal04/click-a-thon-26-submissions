import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from '../button';
import { EmptyState } from './empty-state';

const meta = {
  title: 'Components/EmptyState',
  component: EmptyState,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    compact: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof EmptyState>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default empty state with all sub-components
 */
export const Default: Story = {
  render: () => (
    <EmptyState icon={<Icon name="inbox" />}>
      <EmptyState.Title>No messages</EmptyState.Title>
      <EmptyState.Description>
        Your inbox is empty. Messages will appear here when you receive them.
      </EmptyState.Description>
      <EmptyState.Actions>
        <Button>Compose message</Button>
      </EmptyState.Actions>
    </EmptyState>
  ),
};

/**
 * Search empty state
 */
export const SearchResults: Story = {
  render: () => (
    <EmptyState icon={<Icon name="search" />}>
      <EmptyState.Title>No results found</EmptyState.Title>
      <EmptyState.Description>
        Try adjusting your search or filters to find what you're looking for.
      </EmptyState.Description>
      <EmptyState.Actions>
        <Button intent="secondary">Clear filters</Button>
        <Button>New search</Button>
      </EmptyState.Actions>
    </EmptyState>
  ),
};

/**
 * Error empty state
 */
export const Error: Story = {
  render: () => (
    <EmptyState icon={<Icon name="alert-triangle" />}>
      <EmptyState.Title>Something went wrong</EmptyState.Title>
      <EmptyState.Description>
        We couldn't load your data. Please try again or contact support if the problem persists.
      </EmptyState.Description>
      <EmptyState.Actions>
        <Button>Try again</Button>
        <Button intent="secondary">Contact support</Button>
      </EmptyState.Actions>
    </EmptyState>
  ),
};

/**
 * Small size variant
 */
export const Small: Story = {
  render: () => (
    <div className="w-64 border rounded-lg">
      <EmptyState size="sm" icon={<Icon name="file" />}>
        <EmptyState.Title>No files</EmptyState.Title>
        <EmptyState.Description>Upload files to get started.</EmptyState.Description>
      </EmptyState>
    </div>
  ),
};

/**
 * Large size variant
 */
export const Large: Story = {
  render: () => (
    <EmptyState size="lg" icon={<Icon name="users" />}>
      <EmptyState.Title>No team members</EmptyState.Title>
      <EmptyState.Description>
        Invite your team members to collaborate on this project. They'll be able to view, edit, and
        contribute to your work.
      </EmptyState.Description>
      <EmptyState.Actions>
        <Button size="lg">Invite team members</Button>
      </EmptyState.Actions>
    </EmptyState>
  ),
};

/**
 * Compact mode
 */
export const Compact: Story = {
  render: () => (
    <div className="w-48 border rounded-lg">
      <EmptyState compact icon={<Icon name="image" />}>
        <EmptyState.Title>No images</EmptyState.Title>
      </EmptyState>
    </div>
  ),
};

/**
 * Custom illustration
 */
export const CustomIllustration: Story = {
  render: () => (
    <EmptyState
      icon={
        <div className="h-32 w-32 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
          <Icon name="package" />
        </div>
      }
    >
      <EmptyState.Title>No products yet</EmptyState.Title>
      <EmptyState.Description>
        Start building your catalog by adding your first product.
      </EmptyState.Description>
      <EmptyState.Actions>
        <Button>Add product</Button>
      </EmptyState.Actions>
    </EmptyState>
  ),
};

/**
 * Without icon
 */
export const WithoutIcon: Story = {
  render: () => (
    <EmptyState>
      <EmptyState.Title>No notifications</EmptyState.Title>
      <EmptyState.Description>
        You're all caught up! Check back later for new updates.
      </EmptyState.Description>
    </EmptyState>
  ),
};

/**
 * In card context
 */
export const InCard: Story = {
  render: () => (
    <div className="w-96 rounded-lg border bg-card p-6">
      <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
      <EmptyState size="sm" compact icon={<Icon name="activity" />}>
        <EmptyState.Title>No recent activity</EmptyState.Title>
        <EmptyState.Description>
          Activity from your projects will appear here.
        </EmptyState.Description>
      </EmptyState>
    </div>
  ),
};

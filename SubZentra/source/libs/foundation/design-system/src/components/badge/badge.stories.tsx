import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Badge } from './badge';

/**
 * Badge component for displaying status, counts, or labels.
 * Supports multiple intents and sizes.
 */
const meta: Meta<typeof Badge> = {
  title: 'Components/Badge',
  component: Badge,
  tags: ['autodocs'],
  argTypes: {
    intent: {
      control: 'select',
      options: ['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info'],
      description: 'Visual style variant',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the badge',
    },
    children: {
      control: 'text',
      description: 'Badge content',
    },
  },
  args: {
    children: 'Badge',
    intent: 'default',
    size: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Badge>;

/**
 * Default badge style.
 */
export const Default: Story = {
  args: {
    intent: 'default',
    children: 'Default',
  },
};

/**
 * Primary badge.
 */
export const Primary: Story = {
  args: {
    intent: 'primary',
    children: 'Primary',
  },
};

/**
 * Secondary badge.
 */
export const Secondary: Story = {
  args: {
    intent: 'secondary',
    children: 'Secondary',
  },
};

/**
 * Success badge for positive status.
 */
export const Success: Story = {
  args: {
    intent: 'success',
    children: 'Active',
  },
};

/**
 * Warning badge for cautionary status.
 */
export const Warning: Story = {
  args: {
    intent: 'warning',
    children: 'Pending',
  },
};

/**
 * Danger badge for error/critical status.
 */
export const Danger: Story = {
  args: {
    intent: 'danger',
    children: 'Error',
  },
};

/**
 * Info badge.
 */
export const Info: Story = {
  args: {
    intent: 'info',
    children: 'Info',
  },
};

/**
 * Small badge.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    children: 'Small',
  },
};

/**
 * Large badge.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    children: 'Large',
  },
};

/**
 * Badge with count.
 */
export const WithCount: Story = {
  args: {
    intent: 'danger',
    children: '3',
  },
};

/**
 * All badge variants.
 */
export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <Badge intent="default">Default</Badge>
        <Badge intent="primary">Primary</Badge>
        <Badge intent="secondary">Secondary</Badge>
        <Badge intent="success">Success</Badge>
        <Badge intent="warning">Warning</Badge>
        <Badge intent="danger">Danger</Badge>
        <Badge intent="info">Info</Badge>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Badge size="sm">Small</Badge>
        <Badge size="md">Medium</Badge>
        <Badge size="lg">Large</Badge>
      </div>
    </div>
  ),
};

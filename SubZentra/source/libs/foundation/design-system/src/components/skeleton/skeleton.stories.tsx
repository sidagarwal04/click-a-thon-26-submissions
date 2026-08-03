import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Skeleton } from './skeleton';

/**
 * Skeleton component for loading placeholders.
 * Mimics content shape while data is loading.
 */
const meta: Meta<typeof Skeleton> = {
  title: 'Components/Skeleton',
  component: Skeleton,
  tags: ['autodocs'],
  argTypes: {
    width: {
      control: 'text',
      description: 'Width of the skeleton',
    },
    height: {
      control: 'text',
      description: 'Height of the skeleton',
    },
    radius: {
      control: 'select',
      options: ['none', 'sm', 'md', 'lg', 'full'],
      description: 'Border radius',
    },
    animated: {
      control: 'boolean',
      description: 'Enable pulse animation',
    },
  },
  args: {
    width: '200px',
    height: '20px',
    radius: 'md',
    animated: true,
  },
};

export default meta;
type Story = StoryObj<typeof Skeleton>;

/**
 * Default text-like skeleton.
 */
export const Default: Story = {
  args: {
    width: '200px',
    height: '16px',
  },
};

/**
 * Avatar skeleton.
 */
export const Avatar: Story = {
  args: {
    width: 48,
    height: 48,
    radius: 'full',
  },
};

/**
 * Card skeleton.
 */
export const Card: Story = {
  args: {
    width: '300px',
    height: '150px',
    radius: 'lg',
  },
};

/**
 * Button skeleton.
 */
export const Button: Story = {
  args: {
    width: '100px',
    height: '40px',
    radius: 'md',
  },
};

/**
 * Skeleton without animation.
 */
export const Static: Story = {
  args: {
    width: '200px',
    height: '20px',
    animated: false,
  },
};

/**
 * Different radius options.
 */
export const AllRadii: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Skeleton width={100} height={40} radius="none" />
        <span style={{ fontSize: '14px' }}>radius: none</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Skeleton width={100} height={40} radius="sm" />
        <span style={{ fontSize: '14px' }}>radius: sm</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Skeleton width={100} height={40} radius="md" />
        <span style={{ fontSize: '14px' }}>radius: md</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Skeleton width={100} height={40} radius="lg" />
        <span style={{ fontSize: '14px' }}>radius: lg</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Skeleton width={40} height={40} radius="full" />
        <span style={{ fontSize: '14px' }}>radius: full</span>
      </div>
    </div>
  ),
};

/**
 * Text content skeleton.
 */
export const TextContent: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '300px' }}>
      <Skeleton width="80%" height={24} />
      <Skeleton width="100%" height={16} />
      <Skeleton width="100%" height={16} />
      <Skeleton width="60%" height={16} />
    </div>
  ),
};

/**
 * Profile card skeleton.
 */
export const ProfileCard: Story = {
  render: () => (
    <div
      style={{
        display: 'flex',
        gap: '16px',
        padding: '16px',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        width: '300px',
      }}
    >
      <Skeleton width={64} height={64} radius="full" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <Skeleton width="70%" height={20} />
        <Skeleton width="50%" height={16} />
        <Skeleton width="90%" height={16} />
      </div>
    </div>
  ),
};

/**
 * List skeleton.
 */
export const List: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '300px' }}>
      {[1, 2, 3].map((item) => (
        <div key={item} style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Skeleton width={40} height={40} radius="md" />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <Skeleton width="60%" height={16} />
            <Skeleton width="80%" height={14} />
          </div>
        </div>
      ))}
    </div>
  ),
};

/**
 * Full page skeleton.
 */
export const PageSkeleton: Story = {
  render: () => (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '400px' }}
      aria-busy="true"
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Skeleton width={150} height={32} />
        <Skeleton width={100} height={36} radius="md" />
      </div>

      {/* Image */}
      <Skeleton width="100%" height={200} radius="lg" />

      {/* Content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <Skeleton width="90%" height={24} />
        <Skeleton width="100%" height={16} />
        <Skeleton width="100%" height={16} />
        <Skeleton width="75%" height={16} />
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px' }}>
        <Skeleton width={120} height={40} radius="md" />
        <Skeleton width={120} height={40} radius="md" />
      </div>
    </div>
  ),
};

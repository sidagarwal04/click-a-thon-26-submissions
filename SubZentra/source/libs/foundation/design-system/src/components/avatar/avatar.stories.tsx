import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Avatar } from './avatar';

const meta = {
  title: 'Components/Avatar',
  component: Avatar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg', 'xl', '2xl'],
    },
    shape: {
      control: 'radio',
      options: ['circle', 'square'],
    },
    status: {
      control: 'select',
      options: ['online', 'offline', 'away', 'busy', 'none'],
    },
    skeleton: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Avatar>;

export default meta;
type Story = StoryObj<typeof meta>;

const SAMPLE_IMAGE =
  'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop';

/**
 * Default avatar with image
 */
export const Default: Story = {
  args: {
    src: SAMPLE_IMAGE,
    alt: 'John Doe',
    size: 'md',
    shape: 'circle',
  },
};

/**
 * Avatar with initials fallback when no image provided
 */
export const WithInitials: Story = {
  args: {
    name: 'John Doe',
    size: 'md',
  },
};

/**
 * Avatar with single name (one initial)
 */
export const SingleInitial: Story = {
  args: {
    name: 'Alice',
    size: 'lg',
  },
};

/**
 * Default fallback when no name or image provided
 */
export const DefaultFallback: Story = {
  args: {
    size: 'lg',
  },
};

/**
 * Custom fallback content
 */
export const CustomFallback: Story = {
  args: {
    size: 'lg',
    fallback: <Icon name="user" />,
  },
};

/**
 * All available sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="flex items-end gap-4">
      <Avatar src={SAMPLE_IMAGE} size="xs" alt="XS Avatar" />
      <Avatar src={SAMPLE_IMAGE} size="sm" alt="SM Avatar" />
      <Avatar src={SAMPLE_IMAGE} size="md" alt="MD Avatar" />
      <Avatar src={SAMPLE_IMAGE} size="lg" alt="LG Avatar" />
      <Avatar src={SAMPLE_IMAGE} size="xl" alt="XL Avatar" />
      <Avatar src={SAMPLE_IMAGE} size="2xl" alt="2XL Avatar" />
    </div>
  ),
};

/**
 * Square shape avatars
 */
export const Square: Story = {
  render: () => (
    <div className="flex items-end gap-4">
      <Avatar src={SAMPLE_IMAGE} shape="square" size="sm" alt="Square Avatar" />
      <Avatar src={SAMPLE_IMAGE} shape="square" size="md" alt="Square Avatar" />
      <Avatar src={SAMPLE_IMAGE} shape="square" size="lg" alt="Square Avatar" />
    </div>
  ),
};

/**
 * Avatar with status indicators
 */
export const WithStatus: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Avatar src={SAMPLE_IMAGE} status="online" alt="Online" />
      <Avatar src={SAMPLE_IMAGE} status="away" alt="Away" />
      <Avatar src={SAMPLE_IMAGE} status="busy" alt="Busy" />
      <Avatar src={SAMPLE_IMAGE} status="offline" alt="Offline" />
    </div>
  ),
};

/**
 * Avatar with context icon
 */
export const WithContext: Story = {
  args: {
    src: SAMPLE_IMAGE,
    size: 'lg',
    context: (
      <span className="flex h-full w-full items-center justify-center bg-blue-500 text-white">
        <Icon name="check" size="xs" />
      </span>
    ),
    alt: 'Verified User',
  },
};

/**
 * Skeleton loading state
 */
export const Skeleton: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Avatar skeleton size="sm" />
      <Avatar skeleton size="md" />
      <Avatar skeleton size="lg" />
      <Avatar skeleton size="xl" shape="square" />
    </div>
  ),
};

/**
 * Avatar group (stacked)
 */
export const AvatarGroup: Story = {
  render: () => (
    <div className="flex -space-x-3">
      <Avatar src={SAMPLE_IMAGE} alt="User 1" className="ring-2 ring-background" />
      <Avatar name="Alice Bob" className="ring-2 ring-background" />
      <Avatar name="Charlie Dan" className="ring-2 ring-background" />
      <Avatar
        fallback={<span className="text-xs">+5</span>}
        className="ring-2 ring-background bg-muted"
      />
    </div>
  ),
};

/**
 * Failed image load (shows fallback)
 */
export const FailedImageLoad: Story = {
  args: {
    src: 'https://invalid-url.com/image.jpg',
    name: 'Fallback Name',
    size: 'lg',
  },
};

import type { Meta, StoryObj } from '@storybook/react';

import { Loader } from './loader';

const meta = {
  title: 'Components/Loader',
  component: Loader,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg', 'xl'],
    },
    variant: {
      control: 'select',
      options: ['spinner', 'dots', 'skeleton'],
    },
    fullScreen: {
      control: 'boolean',
    },
    overlay: {
      control: 'boolean',
    },
    inline: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Loader>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default spinner loader
 */
export const Default: Story = {
  args: {
    loading: true,
    size: 'md',
    variant: 'spinner',
  },
};

/**
 * Loader with text label
 */
export const WithLabel: Story = {
  args: {
    loading: true,
    label: 'Loading...',
  },
};

/**
 * Different sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-8">
      <Loader size="sm" label="Small" />
      <Loader size="md" label="Medium" />
      <Loader size="lg" label="Large" />
      <Loader size="xl" label="XL" />
    </div>
  ),
};

/**
 * Dots variant
 */
export const DotsVariant: Story = {
  args: {
    variant: 'dots',
    label: 'Loading...',
  },
};

/**
 * Skeleton variant
 */
export const SkeletonVariant: Story = {
  args: {
    variant: 'skeleton',
  },
};

/**
 * Inline loader (horizontal layout)
 */
export const Inline: Story = {
  args: {
    inline: true,
    label: 'Processing...',
    size: 'sm',
  },
};

/**
 * Overlay mode - covers content with semi-transparent background
 */
export const Overlay: Story = {
  render: () => (
    <div className="relative h-48 w-64 rounded-lg border bg-card p-4">
      <h3 className="font-semibold">Card Title</h3>
      <p className="text-sm text-muted-foreground">
        Some content that will be covered by the loader overlay.
      </p>
      <Loader overlay label="Saving..." />
    </div>
  ),
};

/**
 * Conditional rendering - shows children when not loading
 */
export const ConditionalContent: Story = {
  render: () => {
    const isLoading = false;
    return (
      <Loader loading={isLoading}>
        <div className="rounded-lg border p-4">
          <h3 className="font-semibold">Loaded Content</h3>
          <p className="text-sm text-muted-foreground">
            This content is shown when loading is complete.
          </p>
        </div>
      </Loader>
    );
  },
};

/**
 * Custom indicator
 */
export const CustomIndicator: Story = {
  args: {
    indicator: (
      <div className="relative h-10 w-10">
        <div className="absolute inset-0 animate-ping rounded-full bg-primary/30" />
        <div className="absolute inset-0 animate-pulse rounded-full bg-primary/60" />
      </div>
    ),
    label: 'Custom animation',
  },
};

/**
 * Full screen loader (click to preview in separate story)
 */
export const FullScreenPreview: Story = {
  parameters: {
    layout: 'fullscreen',
  },
  render: () => (
    <div className="relative h-screen w-full">
      <Loader fullScreen label="Loading application..." />
    </div>
  ),
};

/**
 * All variants comparison
 */
export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-col gap-8">
      <div className="flex items-center gap-4">
        <span className="w-20 text-sm font-medium">Spinner:</span>
        <Loader variant="spinner" />
      </div>
      <div className="flex items-center gap-4">
        <span className="w-20 text-sm font-medium">Dots:</span>
        <Loader variant="dots" />
      </div>
      <div className="flex items-center gap-4">
        <span className="w-20 text-sm font-medium">Skeleton:</span>
        <Loader variant="skeleton" />
      </div>
    </div>
  ),
};

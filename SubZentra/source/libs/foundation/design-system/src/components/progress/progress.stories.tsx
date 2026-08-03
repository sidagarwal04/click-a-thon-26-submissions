import React, { useEffect, useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Progress } from './progress';

/**
 * Progress component for showing completion status.
 * Supports determinate and indeterminate states.
 */
const meta: Meta<typeof Progress> = {
  title: 'Components/Progress',
  component: Progress,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: { type: 'range', min: 0, max: 100 },
      description: 'Progress value (0-100)',
    },
    intent: {
      control: 'select',
      options: ['primary', 'success', 'warning', 'danger'],
      description: 'Visual style variant',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the progress bar',
    },
    indeterminate: {
      control: 'boolean',
      description: 'Indeterminate loading state',
    },
  },
  args: {
    value: 60,
    intent: 'primary',
    size: 'md',
    'aria-label': 'Progress',
  },
  decorators: [
    (Story) => (
      <div style={{ width: '300px' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof Progress>;

/**
 * Default progress bar at 60%.
 */
export const Default: Story = {
  args: {
    value: 60,
    'aria-label': 'Progress: 60%',
  },
};

/**
 * Progress bar at 0%.
 */
export const Empty: Story = {
  args: {
    value: 0,
    'aria-label': 'Progress: 0%',
  },
};

/**
 * Progress bar at 100%.
 */
export const Complete: Story = {
  args: {
    value: 100,
    'aria-label': 'Progress: 100%',
  },
};

/**
 * Primary intent (default).
 */
export const Primary: Story = {
  args: {
    value: 75,
    intent: 'primary',
    'aria-label': 'Progress: 75%',
  },
};

/**
 * Success intent.
 */
export const Success: Story = {
  args: {
    value: 100,
    intent: 'success',
    'aria-label': 'Complete',
  },
};

/**
 * Warning intent.
 */
export const Warning: Story = {
  args: {
    value: 50,
    intent: 'warning',
    'aria-label': 'Progress: 50%',
  },
};

/**
 * Danger intent.
 */
export const Danger: Story = {
  args: {
    value: 25,
    intent: 'danger',
    'aria-label': 'Critical: 25%',
  },
};

/**
 * Small progress bar.
 */
export const Small: Story = {
  args: {
    value: 60,
    size: 'sm',
    'aria-label': 'Progress: 60%',
  },
};

/**
 * Large progress bar.
 */
export const Large: Story = {
  args: {
    value: 60,
    size: 'lg',
    'aria-label': 'Progress: 60%',
  },
};

/**
 * Indeterminate loading state.
 */
export const Indeterminate: Story = {
  args: {
    indeterminate: true,
    'aria-label': 'Loading',
  },
};

/**
 * Animated progress.
 */
export const Animated: Story = {
  render: function AnimatedRender() {
    const [progress, setProgress] = useState(0);

    useEffect(() => {
      const timer = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) return 0;
          return prev + 10;
        });
      }, 500);
      return () => clearInterval(timer);
    }, []);

    return <Progress value={progress} aria-label={`Progress: ${progress}%`} />;
  },
};

/**
 * All progress sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Small</p>
        <Progress value={60} size="sm" aria-label="Small progress" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Medium</p>
        <Progress value={60} size="md" aria-label="Medium progress" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Large</p>
        <Progress value={60} size="lg" aria-label="Large progress" />
      </div>
    </div>
  ),
};

/**
 * All progress intents.
 */
export const AllIntents: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Primary</p>
        <Progress value={75} intent="primary" aria-label="Primary progress" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Success</p>
        <Progress value={100} intent="success" aria-label="Success progress" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Warning</p>
        <Progress value={50} intent="warning" aria-label="Warning progress" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px' }}>Danger</p>
        <Progress value={25} intent="danger" aria-label="Danger progress" />
      </div>
    </div>
  ),
};

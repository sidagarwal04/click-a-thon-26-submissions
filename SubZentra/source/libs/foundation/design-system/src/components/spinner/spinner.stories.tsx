import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Spinner } from './spinner';

/**
 * Spinner component for loading indicators.
 * Includes accessible labeling for screen readers.
 */
const meta: Meta<typeof Spinner> = {
  title: 'Components/Spinner',
  component: Spinner,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg', 'xl'],
      description: 'Size of the spinner',
    },
    'aria-label': {
      control: 'text',
      description: 'Accessible label for screen readers',
    },
  },
  args: {
    size: 'md',
    'aria-label': 'Loading',
  },
};

export default meta;
type Story = StoryObj<typeof Spinner>;

/**
 * Default medium spinner.
 */
export const Default: Story = {
  args: {
    size: 'md',
  },
};

/**
 * Extra small spinner.
 */
export const ExtraSmall: Story = {
  args: {
    size: 'xs',
  },
};

/**
 * Small spinner.
 */
export const Small: Story = {
  args: {
    size: 'sm',
  },
};

/**
 * Large spinner.
 */
export const Large: Story = {
  args: {
    size: 'lg',
  },
};

/**
 * Extra large spinner.
 */
export const ExtraLarge: Story = {
  args: {
    size: 'xl',
  },
};

/**
 * Spinner with custom aria-label.
 */
export const WithCustomLabel: Story = {
  args: {
    size: 'md',
    'aria-label': 'Submitting form...',
  },
};

/**
 * All spinner sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <Spinner size="xs" />
        <span style={{ fontSize: '12px' }}>xs</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <Spinner size="sm" />
        <span style={{ fontSize: '12px' }}>sm</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <Spinner size="md" />
        <span style={{ fontSize: '12px' }}>md</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <Spinner size="lg" />
        <span style={{ fontSize: '12px' }}>lg</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <Spinner size="xl" />
        <span style={{ fontSize: '12px' }}>xl</span>
      </div>
    </div>
  ),
};

/**
 * Spinner with text.
 */
export const WithText: Story = {
  render: () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <Spinner size="sm" />
      <span>Loading...</span>
    </div>
  ),
};

/**
 * Centered loading overlay.
 */
export const LoadingOverlay: Story = {
  render: () => (
    <div
      style={{
        position: 'relative',
        width: '300px',
        height: '200px',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
        <Spinner size="lg" />
        <span style={{ fontSize: '14px', color: '#666' }}>Loading content...</span>
      </div>
    </div>
  ),
};

/**
 * Inline spinner with button text.
 */
export const InlineWithText: Story = {
  render: () => (
    <button
      disabled
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 16px',
        backgroundColor: '#3b82f6',
        color: 'white',
        border: 'none',
        borderRadius: '6px',
        cursor: 'not-allowed',
        opacity: 0.7,
      }}
    >
      <Spinner size="sm" aria-label="Submitting" />
      <span>Submitting...</span>
    </button>
  ),
};

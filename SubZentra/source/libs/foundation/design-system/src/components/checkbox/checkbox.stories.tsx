import React, { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Checkbox } from './checkbox';

/**
 * Checkbox component for boolean input.
 * Built on Base UI primitives for accessibility.
 */
const meta: Meta<typeof Checkbox> = {
  title: 'Components/Checkbox',
  component: Checkbox,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the checkbox',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the checkbox',
    },
    checked: {
      control: 'boolean',
      description: 'Checked state',
    },
    indeterminate: {
      control: 'boolean',
      description: 'Indeterminate state',
    },
  },
  args: {
    size: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Checkbox>;

/**
 * Default unchecked checkbox.
 */
export const Default: Story = {
  args: {},
};

/**
 * Checked checkbox.
 */
export const Checked: Story = {
  args: {
    defaultChecked: true,
  },
};

/**
 * Indeterminate state (typically for "select all" scenarios).
 */
export const Indeterminate: Story = {
  args: {
    indeterminate: true,
  },
};

/**
 * Disabled checkbox.
 */
export const Disabled: Story = {
  args: {
    disabled: true,
  },
};

/**
 * Disabled and checked.
 */
export const DisabledChecked: Story = {
  args: {
    disabled: true,
    defaultChecked: true,
  },
};

/**
 * Small checkbox.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    defaultChecked: true,
  },
};

/**
 * Large checkbox.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    defaultChecked: true,
  },
};

/**
 * Checkbox with label.
 */
export const WithLabel: Story = {
  render: () => (
    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
      <Checkbox id="terms" />
      <span>Accept terms and conditions</span>
    </label>
  ),
};

/**
 * Controlled checkbox with state.
 */
export const Controlled: Story = {
  render: function ControlledRender() {
    const [checked, setChecked] = useState(false);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <Checkbox checked={checked} onCheckedChange={(c) => setChecked(c as boolean)} />
          <span>Controlled checkbox</span>
        </label>
        <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
          State: {checked ? 'Checked' : 'Unchecked'}
        </p>
      </div>
    );
  },
};

/**
 * All checkbox sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Checkbox size="sm" defaultChecked />
        <span>Small</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Checkbox size="md" defaultChecked />
        <span>Medium</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Checkbox size="lg" defaultChecked />
        <span>Large</span>
      </label>
    </div>
  ),
};

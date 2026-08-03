import React, { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { RadioGroup } from './radio-group';

/**
 * RadioGroup component for selecting one option from a set.
 * Built on Base UI primitives for accessibility.
 */
const meta: Meta<typeof RadioGroup> = {
  title: 'Components/RadioGroup',
  component: RadioGroup,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the radio items',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables all radio items',
    },
    orientation: {
      control: 'select',
      options: ['horizontal', 'vertical'],
      description: 'Layout orientation',
    },
  },
  args: {
    size: 'md',
    orientation: 'vertical',
  },
};

export default meta;
type Story = StoryObj<typeof RadioGroup>;

/**
 * Default radio group.
 */
export const Default: Story = {
  render: (args) => (
    <RadioGroup {...args} defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="option1" />
        <label htmlFor="option1">Option 1</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="option2" />
        <label htmlFor="option2">Option 2</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option3" id="option3" />
        <label htmlFor="option3">Option 3</label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Radio group with pre-selected value.
 */
export const WithDefaultValue: Story = {
  render: (args) => (
    <RadioGroup {...args} defaultValue="option2">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="dv-option1" />
        <label htmlFor="dv-option1">First choice</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="dv-option2" />
        <label htmlFor="dv-option2">Second choice (default)</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option3" id="dv-option3" />
        <label htmlFor="dv-option3">Third choice</label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Disabled radio group.
 */
export const Disabled: Story = {
  render: (args) => (
    <RadioGroup {...args} disabled defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="dis-option1" />
        <label htmlFor="dis-option1">Option 1</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="dis-option2" />
        <label htmlFor="dis-option2">Option 2</label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Individual item disabled.
 */
export const IndividualDisabled: Story = {
  render: (args) => (
    <RadioGroup {...args} defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="id-option1" />
        <label htmlFor="id-option1">Available</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', opacity: 0.5 }}>
        <RadioGroup.Item value="option2" id="id-option2" disabled />
        <label htmlFor="id-option2">Unavailable</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option3" id="id-option3" />
        <label htmlFor="id-option3">Available</label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Small radio items.
 */
export const Small: Story = {
  render: (args) => (
    <RadioGroup {...args} size="sm" defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="sm-option1" />
        <label htmlFor="sm-option1" style={{ fontSize: '14px' }}>
          Small Option 1
        </label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="sm-option2" />
        <label htmlFor="sm-option2" style={{ fontSize: '14px' }}>
          Small Option 2
        </label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Large radio items.
 */
export const Large: Story = {
  render: (args) => (
    <RadioGroup {...args} size="lg" defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="lg-option1" />
        <label htmlFor="lg-option1" style={{ fontSize: '18px' }}>
          Large Option 1
        </label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="lg-option2" />
        <label htmlFor="lg-option2" style={{ fontSize: '18px' }}>
          Large Option 2
        </label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Horizontal layout.
 */
export const Horizontal: Story = {
  render: (args) => (
    <RadioGroup {...args} orientation="horizontal" defaultValue="option1">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option1" id="hz-option1" />
        <label htmlFor="hz-option1">Yes</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option2" id="hz-option2" />
        <label htmlFor="hz-option2">No</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <RadioGroup.Item value="option3" id="hz-option3" />
        <label htmlFor="hz-option3">Maybe</label>
      </div>
    </RadioGroup>
  ),
};

/**
 * Controlled radio group.
 */
export const Controlled: Story = {
  render: function ControlledRender() {
    const [value, setValue] = useState('option1');

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <RadioGroup value={value} onValueChange={setValue}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RadioGroup.Item value="option1" id="ctrl-option1" />
            <label htmlFor="ctrl-option1">First</label>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RadioGroup.Item value="option2" id="ctrl-option2" />
            <label htmlFor="ctrl-option2">Second</label>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RadioGroup.Item value="option3" id="ctrl-option3" />
            <label htmlFor="ctrl-option3">Third</label>
          </div>
        </RadioGroup>
        <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>Selected: {value}</p>
      </div>
    );
  },
};

/**
 * All radio group sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '32px' }}>
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 500 }}>Small</p>
        <RadioGroup size="sm" defaultValue="option1">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <RadioGroup.Item value="option1" id="as-sm-1" />
            <label htmlFor="as-sm-1" style={{ fontSize: '14px' }}>
              Option
            </label>
          </div>
        </RadioGroup>
      </div>
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 500 }}>Medium</p>
        <RadioGroup size="md" defaultValue="option1">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RadioGroup.Item value="option1" id="as-md-1" />
            <label htmlFor="as-md-1">Option</label>
          </div>
        </RadioGroup>
      </div>
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 500 }}>Large</p>
        <RadioGroup size="lg" defaultValue="option1">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RadioGroup.Item value="option1" id="as-lg-1" />
            <label htmlFor="as-lg-1" style={{ fontSize: '18px' }}>
              Option
            </label>
          </div>
        </RadioGroup>
      </div>
    </div>
  ),
};

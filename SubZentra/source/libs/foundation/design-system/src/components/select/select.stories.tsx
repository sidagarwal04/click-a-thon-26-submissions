import React, { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Select } from './select';

/**
 * Select component for choosing from a list of options.
 * Built on Base UI primitives for accessibility.
 */
const meta: Meta<typeof Select> = {
  title: 'Components/Select',
  component: Select,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the select',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the select',
    },
  },
  args: {
    size: 'md',
  },
  decorators: [
    (Story) => (
      <div style={{ width: '250px' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof Select>;

/**
 * Default select.
 */
export const Default: Story = {
  render: (args) => (
    <Select {...args}>
      <Select.Trigger placeholder="Select an option" />
      <Select.Content>
        <Select.Item value="option1">Option 1</Select.Item>
        <Select.Item value="option2">Option 2</Select.Item>
        <Select.Item value="option3">Option 3</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Select with default value.
 */
export const WithDefaultValue: Story = {
  render: (args) => (
    <Select {...args} defaultValue="option2">
      <Select.Trigger placeholder="Select an option" />
      <Select.Content>
        <Select.Item value="option1">First Option</Select.Item>
        <Select.Item value="option2">Second Option</Select.Item>
        <Select.Item value="option3">Third Option</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Disabled select.
 */
export const Disabled: Story = {
  render: (args) => (
    <Select {...args} disabled defaultValue="option1">
      <Select.Trigger placeholder="Select an option" />
      <Select.Content>
        <Select.Item value="option1">Option 1</Select.Item>
        <Select.Item value="option2">Option 2</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Small select.
 */
export const Small: Story = {
  render: (args) => (
    <Select {...args} size="sm">
      <Select.Trigger placeholder="Small select" />
      <Select.Content>
        <Select.Item value="option1">Option 1</Select.Item>
        <Select.Item value="option2">Option 2</Select.Item>
        <Select.Item value="option3">Option 3</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Large select.
 */
export const Large: Story = {
  render: (args) => (
    <Select {...args} size="lg">
      <Select.Trigger placeholder="Large select" />
      <Select.Content>
        <Select.Item value="option1">Option 1</Select.Item>
        <Select.Item value="option2">Option 2</Select.Item>
        <Select.Item value="option3">Option 3</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Select with disabled items.
 */
export const WithDisabledItems: Story = {
  render: (args) => (
    <Select {...args}>
      <Select.Trigger placeholder="Choose framework" />
      <Select.Content>
        <Select.Item value="react">React</Select.Item>
        <Select.Item value="vue" disabled>
          Vue (unavailable)
        </Select.Item>
        <Select.Item value="angular">Angular</Select.Item>
        <Select.Item value="svelte" disabled>
          Svelte (unavailable)
        </Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Select with many options.
 */
export const ManyOptions: Story = {
  render: (args) => (
    <Select {...args}>
      <Select.Trigger placeholder="Select a country" />
      <Select.Content>
        <Select.Item value="us">United States</Select.Item>
        <Select.Item value="ca">Canada</Select.Item>
        <Select.Item value="uk">United Kingdom</Select.Item>
        <Select.Item value="de">Germany</Select.Item>
        <Select.Item value="fr">France</Select.Item>
        <Select.Item value="es">Spain</Select.Item>
        <Select.Item value="it">Italy</Select.Item>
        <Select.Item value="jp">Japan</Select.Item>
        <Select.Item value="au">Australia</Select.Item>
        <Select.Item value="br">Brazil</Select.Item>
      </Select.Content>
    </Select>
  ),
};

/**
 * Controlled select.
 */
export const Controlled: Story = {
  render: function ControlledRender() {
    const [value, setValue] = useState('');

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <Select value={value} onValueChange={setValue}>
          <Select.Trigger placeholder="Select a fruit" />
          <Select.Content>
            <Select.Item value="apple">Apple</Select.Item>
            <Select.Item value="banana">Banana</Select.Item>
            <Select.Item value="orange">Orange</Select.Item>
            <Select.Item value="grape">Grape</Select.Item>
          </Select.Content>
        </Select>
        <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>Selected: {value || '(none)'}</p>
      </div>
    );
  },
};

/**
 * All select sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Select size="sm" defaultValue="option1">
        <Select.Trigger placeholder="Small" />
        <Select.Content>
          <Select.Item value="option1">Small Option</Select.Item>
        </Select.Content>
      </Select>
      <Select size="md" defaultValue="option1">
        <Select.Trigger placeholder="Medium" />
        <Select.Content>
          <Select.Item value="option1">Medium Option</Select.Item>
        </Select.Content>
      </Select>
      <Select size="lg" defaultValue="option1">
        <Select.Trigger placeholder="Large" />
        <Select.Content>
          <Select.Item value="option1">Large Option</Select.Item>
        </Select.Content>
      </Select>
    </div>
  ),
};

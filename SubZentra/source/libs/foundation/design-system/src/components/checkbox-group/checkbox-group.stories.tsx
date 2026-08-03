import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { CheckboxGroup } from './checkbox-group';

const meta = {
  title: 'Components/CheckboxGroup',
  component: CheckboxGroup,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    orientation: {
      control: 'radio',
      options: ['vertical', 'horizontal'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    disabled: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof CheckboxGroup>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default checkbox group
 */
export const Default: Story = {
  render: function DefaultExample() {
    const [value, setValue] = useState<string[]>(['react']);

    return (
      <div className="space-y-4">
        <CheckboxGroup value={value} onValueChange={setValue} label="Select frameworks">
          <CheckboxGroup.Item value="react">React</CheckboxGroup.Item>
          <CheckboxGroup.Item value="vue">Vue</CheckboxGroup.Item>
          <CheckboxGroup.Item value="angular">Angular</CheckboxGroup.Item>
          <CheckboxGroup.Item value="svelte">Svelte</CheckboxGroup.Item>
        </CheckboxGroup>
        <div className="text-sm text-muted-foreground">Selected: {value.join(', ') || 'None'}</div>
      </div>
    );
  },
};

/**
 * With select all label
 */
export const WithSelectAll: Story = {
  render: function SelectAllExample() {
    const [value, setValue] = useState<string[]>([]);

    return (
      <div className="space-y-4">
        <CheckboxGroup value={value} onValueChange={setValue}>
          <CheckboxGroup.Label selectAll>Select all items</CheckboxGroup.Label>
          <CheckboxGroup.Item value="item1">Item 1</CheckboxGroup.Item>
          <CheckboxGroup.Item value="item2">Item 2</CheckboxGroup.Item>
          <CheckboxGroup.Item value="item3">Item 3</CheckboxGroup.Item>
          <CheckboxGroup.Item value="item4">Item 4</CheckboxGroup.Item>
        </CheckboxGroup>
        <div className="text-sm text-muted-foreground">Selected: {value.length} of 4</div>
      </div>
    );
  },
};

/**
 * Horizontal layout
 */
export const Horizontal: Story = {
  render: function HorizontalExample() {
    const [value, setValue] = useState<string[]>(['sm']);

    return (
      <CheckboxGroup
        orientation="horizontal"
        value={value}
        onValueChange={setValue}
        label="Select sizes"
      >
        <CheckboxGroup.Item value="xs">XS</CheckboxGroup.Item>
        <CheckboxGroup.Item value="sm">SM</CheckboxGroup.Item>
        <CheckboxGroup.Item value="md">MD</CheckboxGroup.Item>
        <CheckboxGroup.Item value="lg">LG</CheckboxGroup.Item>
        <CheckboxGroup.Item value="xl">XL</CheckboxGroup.Item>
      </CheckboxGroup>
    );
  },
};

/**
 * Different sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="space-y-6">
      <div>
        <p className="mb-2 text-sm font-medium">Small</p>
        <CheckboxGroup size="sm" defaultValue={['a']}>
          <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
          <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
        </CheckboxGroup>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Medium (default)</p>
        <CheckboxGroup size="md" defaultValue={['a']}>
          <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
          <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
        </CheckboxGroup>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Large</p>
        <CheckboxGroup size="lg" defaultValue={['a']}>
          <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
          <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
        </CheckboxGroup>
      </div>
    </div>
  ),
};

/**
 * Disabled group
 */
export const Disabled: Story = {
  render: () => (
    <CheckboxGroup disabled defaultValue={['a', 'b']}>
      <CheckboxGroup.Item value="a">Option A (checked)</CheckboxGroup.Item>
      <CheckboxGroup.Item value="b">Option B (checked)</CheckboxGroup.Item>
      <CheckboxGroup.Item value="c">Option C</CheckboxGroup.Item>
    </CheckboxGroup>
  ),
};

/**
 * Individual disabled items
 */
export const DisabledItems: Story = {
  render: function DisabledItemsExample() {
    const [value, setValue] = useState<string[]>(['a']);

    return (
      <CheckboxGroup value={value} onValueChange={setValue}>
        <CheckboxGroup.Item value="a">Available option</CheckboxGroup.Item>
        <CheckboxGroup.Item value="b" disabled>
          Disabled option
        </CheckboxGroup.Item>
        <CheckboxGroup.Item value="c">Another available option</CheckboxGroup.Item>
      </CheckboxGroup>
    );
  },
};

/**
 * Uncontrolled with default value
 */
export const Uncontrolled: Story = {
  render: () => (
    <CheckboxGroup defaultValue={['option2']} label="Select preferences">
      <CheckboxGroup.Item value="option1">Email notifications</CheckboxGroup.Item>
      <CheckboxGroup.Item value="option2">Push notifications</CheckboxGroup.Item>
      <CheckboxGroup.Item value="option3">SMS notifications</CheckboxGroup.Item>
    </CheckboxGroup>
  ),
};

/**
 * Form field example
 */
export const FormFieldExample: Story = {
  render: function FormFieldExample() {
    const [permissions, setPermissions] = useState<string[]>(['read']);

    return (
      <div className="w-64 space-y-4 rounded-lg border p-4">
        <div>
          <h3 className="text-sm font-medium">User Permissions</h3>
          <p className="text-xs text-muted-foreground">Select the permissions for this user</p>
        </div>
        <CheckboxGroup value={permissions} onValueChange={setPermissions}>
          <CheckboxGroup.Label selectAll>All permissions</CheckboxGroup.Label>
          <CheckboxGroup.Item value="read">Read access</CheckboxGroup.Item>
          <CheckboxGroup.Item value="write">Write access</CheckboxGroup.Item>
          <CheckboxGroup.Item value="delete">Delete access</CheckboxGroup.Item>
          <CheckboxGroup.Item value="admin">Admin access</CheckboxGroup.Item>
        </CheckboxGroup>
        <div className="border-t pt-2 text-xs text-muted-foreground">
          Selected permissions: {permissions.length > 0 ? permissions.join(', ') : 'None'}
        </div>
      </div>
    );
  },
};

/**
 * Filter panel example
 */
export const FilterPanelExample: Story = {
  render: function FilterPanelExample() {
    const [categories, setCategories] = useState<string[]>([]);
    const [sizes, setSizes] = useState<string[]>([]);

    return (
      <div className="w-56 space-y-6 rounded-lg border p-4">
        <div>
          <h3 className="mb-3 text-sm font-semibold">Categories</h3>
          <CheckboxGroup value={categories} onValueChange={setCategories}>
            <CheckboxGroup.Item value="electronics">Electronics</CheckboxGroup.Item>
            <CheckboxGroup.Item value="clothing">Clothing</CheckboxGroup.Item>
            <CheckboxGroup.Item value="books">Books</CheckboxGroup.Item>
            <CheckboxGroup.Item value="home">Home & Garden</CheckboxGroup.Item>
          </CheckboxGroup>
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold">Sizes</h3>
          <CheckboxGroup orientation="horizontal" value={sizes} onValueChange={setSizes} size="sm">
            <CheckboxGroup.Item value="xs">XS</CheckboxGroup.Item>
            <CheckboxGroup.Item value="s">S</CheckboxGroup.Item>
            <CheckboxGroup.Item value="m">M</CheckboxGroup.Item>
            <CheckboxGroup.Item value="l">L</CheckboxGroup.Item>
            <CheckboxGroup.Item value="xl">XL</CheckboxGroup.Item>
          </CheckboxGroup>
        </div>
      </div>
    );
  },
};

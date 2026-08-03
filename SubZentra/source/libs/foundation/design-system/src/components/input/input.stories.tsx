import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Input } from './input';

// Sample icons using foundation/icons
const SearchIcon = () => <Icon name="search" size="base" />;
const MailIcon = () => <Icon name="mail" size="base" />;
const EyeIcon = () => <Icon name="eye" size="base" />;

/**
 * Input component for text entry with validation states and adornments.
 */
const meta: Meta<typeof Input> = {
  title: 'Components/Input',
  component: Input,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the input',
    },
    type: {
      control: 'select',
      options: ['text', 'email', 'password', 'number', 'tel', 'url', 'search'],
      description: 'Input type',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the input',
    },
    invalid: {
      control: 'boolean',
      description: 'Invalid/error state',
    },
    readOnly: {
      control: 'boolean',
      description: 'Read-only state',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text',
    },
  },
  args: {
    size: 'md',
    placeholder: 'Enter text...',
  },
};

export default meta;
type Story = StoryObj<typeof Input>;

/**
 * Default input.
 */
export const Default: Story = {
  args: {
    placeholder: 'Enter text...',
  },
};

/**
 * Input with value.
 */
export const WithValue: Story = {
  args: {
    defaultValue: 'Hello World',
  },
};

/**
 * Small input.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    placeholder: 'Small input',
  },
};

/**
 * Large input.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    placeholder: 'Large input',
  },
};

/**
 * Disabled input.
 */
export const Disabled: Story = {
  args: {
    disabled: true,
    defaultValue: 'Disabled input',
  },
};

/**
 * Invalid/error input.
 */
export const Invalid: Story = {
  args: {
    invalid: true,
    defaultValue: 'invalid@email',
  },
};

/**
 * Read-only input.
 */
export const ReadOnly: Story = {
  args: {
    readOnly: true,
    defaultValue: 'Read-only content',
  },
};

/**
 * Email input type.
 */
export const Email: Story = {
  args: {
    type: 'email',
    placeholder: 'you@example.com',
  },
};

/**
 * Password input type.
 */
export const Password: Story = {
  args: {
    type: 'password',
    placeholder: 'Enter password',
  },
};

/**
 * Input with start icon.
 */
export const WithStartIcon: Story = {
  args: {
    placeholder: 'Search...',
    start: { children: <SearchIcon /> },
  },
};

/**
 * Input with end icon.
 */
export const WithEndIcon: Story = {
  args: {
    type: 'password',
    placeholder: 'Password',
    end: { children: <EyeIcon /> },
  },
};

/**
 * Email input with icon.
 */
export const EmailWithIcon: Story = {
  args: {
    type: 'email',
    placeholder: 'Enter your email',
    start: { children: <MailIcon /> },
  },
};

/**
 * Input with both icons.
 */
export const WithBothIcons: Story = {
  args: {
    placeholder: 'Search...',
    start: { children: <SearchIcon /> },
    end: { children: <EyeIcon /> },
  },
};

/**
 * Input with validation error.
 */
export const WithError: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '300px' }}>
      <Input invalid defaultValue="invalid-email" type="email" aria-describedby="email-error" />
      <span id="email-error" style={{ color: '#dc2626', fontSize: '14px' }}>
        Please enter a valid email address
      </span>
    </div>
  ),
};

/**
 * All input sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '300px' }}>
      <Input size="sm" placeholder="Small input" />
      <Input size="md" placeholder="Medium input" />
      <Input size="lg" placeholder="Large input" />
    </div>
  ),
};

/**
 * All input states.
 */
export const AllStates: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '300px' }}>
      <Input placeholder="Default" />
      <Input placeholder="Disabled" disabled />
      <Input placeholder="Read-only" readOnly defaultValue="Read-only content" />
      <Input placeholder="Invalid" invalid defaultValue="Invalid value" />
    </div>
  ),
};

import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { IconButton } from './icon-button';

// Sample icons using foundation/icons
const CloseIcon = () => <Icon name="x" size="base" />;
const SearchIcon = () => <Icon name="search" size="base" />;
const MenuIcon = () => <Icon name="menu" size="base" />;
const PlusIcon = () => <Icon name="plus" size="base" />;
const TrashIcon = () => <Icon name="trash" size="base" />;

/**
 * IconButton is designed for icon-only actions.
 * Requires aria-label for accessibility.
 */
const meta: Meta<typeof IconButton> = {
  title: 'Components/IconButton',
  component: IconButton,
  tags: ['autodocs'],
  argTypes: {
    intent: {
      control: 'select',
      options: ['primary', 'secondary', 'danger', 'ghost'],
      description: 'Visual style variant',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the button',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the button',
    },
    loading: {
      control: 'boolean',
      description: 'Shows loading state',
    },
  },
  args: {
    'aria-label': 'Icon button',
    intent: 'secondary',
    size: 'md',
    children: <CloseIcon />,
  },
};

export default meta;
type Story = StoryObj<typeof IconButton>;

/**
 * Default secondary icon button.
 */
export const Default: Story = {
  args: {
    'aria-label': 'Close',
    children: <CloseIcon />,
  },
};

/**
 * Primary icon button.
 */
export const Primary: Story = {
  args: {
    'aria-label': 'Add',
    intent: 'primary',
    children: <PlusIcon />,
  },
};

/**
 * Danger icon button for destructive actions.
 */
export const Danger: Story = {
  args: {
    'aria-label': 'Delete',
    intent: 'danger',
    children: <TrashIcon />,
  },
};

/**
 * Ghost icon button for minimal emphasis.
 */
export const Ghost: Story = {
  args: {
    'aria-label': 'Menu',
    intent: 'ghost',
    children: <MenuIcon />,
  },
};

/**
 * Small icon button.
 */
export const Small: Story = {
  args: {
    'aria-label': 'Search',
    size: 'sm',
    children: <SearchIcon />,
  },
};

/**
 * Large icon button.
 */
export const Large: Story = {
  args: {
    'aria-label': 'Search',
    size: 'lg',
    children: <SearchIcon />,
  },
};

/**
 * Disabled icon button.
 */
export const Disabled: Story = {
  args: {
    'aria-label': 'Close',
    disabled: true,
    children: <CloseIcon />,
  },
};

/**
 * Loading icon button.
 */
export const Loading: Story = {
  args: {
    'aria-label': 'Loading',
    loading: true,
    children: <CloseIcon />,
  },
};

/**
 * All icon button variants.
 */
export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <IconButton aria-label="Primary" intent="primary">
          <PlusIcon />
        </IconButton>
        <IconButton aria-label="Secondary" intent="secondary">
          <SearchIcon />
        </IconButton>
        <IconButton aria-label="Danger" intent="danger">
          <TrashIcon />
        </IconButton>
        <IconButton aria-label="Ghost" intent="ghost">
          <MenuIcon />
        </IconButton>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <IconButton aria-label="Small" size="sm">
          <CloseIcon />
        </IconButton>
        <IconButton aria-label="Medium" size="md">
          <CloseIcon />
        </IconButton>
        <IconButton aria-label="Large" size="lg">
          <CloseIcon />
        </IconButton>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <IconButton aria-label="Disabled" disabled>
          <CloseIcon />
        </IconButton>
        <IconButton aria-label="Loading" loading>
          <CloseIcon />
        </IconButton>
      </div>
    </div>
  ),
};

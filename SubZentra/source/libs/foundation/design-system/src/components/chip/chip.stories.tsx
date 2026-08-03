import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Chip } from './chip';

const meta = {
  title: 'Components/Chip',
  component: Chip,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'primary', 'success', 'warning', 'error', 'info'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    removable: {
      control: 'boolean',
    },
    rounded: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Chip>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default chip
 */
export const Default: Story = {
  args: {
    children: 'Chip',
    variant: 'default',
    size: 'md',
  },
};

/**
 * All variants
 */
export const Variants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Chip variant="default">Default</Chip>
      <Chip variant="primary">Primary</Chip>
      <Chip variant="success">Success</Chip>
      <Chip variant="warning">Warning</Chip>
      <Chip variant="error">Error</Chip>
      <Chip variant="info">Info</Chip>
    </div>
  ),
};

/**
 * All sizes
 */
export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <Chip size="sm">Small</Chip>
      <Chip size="md">Medium</Chip>
      <Chip size="lg">Large</Chip>
    </div>
  ),
};

/**
 * With start icon
 */
export const WithStartIcon: Story = {
  args: {
    children: 'John Doe',
    start: <Icon name="user" />,
  },
};

/**
 * Removable chip
 */
export const Removable: Story = {
  args: {
    children: 'Remove me',
    removable: true,
    onRemove: () => alert('Chip removed!'),
  },
};

/**
 * Removable chip variants
 */
export const RemovableVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Chip variant="default" removable onRemove={() => undefined}>
        Default
      </Chip>
      <Chip variant="primary" removable onRemove={() => undefined}>
        Primary
      </Chip>
      <Chip variant="success" removable onRemove={() => undefined}>
        Success
      </Chip>
      <Chip variant="error" removable onRemove={() => undefined}>
        Error
      </Chip>
    </div>
  ),
};

/**
 * Square corners (not rounded)
 */
export const NotRounded: Story = {
  render: () => (
    <div className="flex gap-2">
      <Chip rounded={false}>Square</Chip>
      <Chip rounded={false} variant="primary">
        Primary
      </Chip>
      <Chip rounded={false} variant="success" removable onRemove={() => undefined}>
        Removable
      </Chip>
    </div>
  ),
};

/**
 * Disabled state
 */
export const Disabled: Story = {
  args: {
    children: 'Disabled Chip',
    disabled: true,
    removable: true,
  },
};

/**
 * Interactive chip list
 */
export const InteractiveList: Story = {
  render: function InteractiveChips() {
    const [chips, setChips] = useState(['React', 'TypeScript', 'Tailwind', 'Vite']);

    const handleRemove = (chip: string) => {
      setChips((prev) => prev.filter((c) => c !== chip));
    };

    return (
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <Chip key={chip} variant="primary" removable onRemove={() => handleRemove(chip)}>
            {chip}
          </Chip>
        ))}
        {chips.length === 0 && (
          <span className="text-sm text-muted-foreground">All chips removed</span>
        )}
      </div>
    );
  },
};

/**
 * With custom start content
 */
export const CustomStart: Story = {
  render: () => (
    <div className="flex gap-2">
      <Chip
        start={
          <img
            src="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=20&h=20&fit=crop"
            alt=""
            className="h-4 w-4 rounded-full"
          />
        }
      >
        John Doe
      </Chip>
      <Chip variant="success" start={<span className="h-2 w-2 rounded-full bg-green-500" />}>
        Online
      </Chip>
    </div>
  ),
};

/**
 * Filter chips use case
 */
export const FilterChips: Story = {
  render: function FilterChipsExample() {
    const [activeFilters, setActiveFilters] = useState(['Status: Active', 'Type: Premium']);

    const handleRemove = (filter: string) => {
      setActiveFilters((prev) => prev.filter((f) => f !== filter));
    };

    return (
      <div className="space-y-2">
        <div className="text-sm font-medium">Active Filters:</div>
        <div className="flex flex-wrap gap-2">
          {activeFilters.map((filter) => (
            <Chip
              key={filter}
              variant="info"
              size="sm"
              removable
              onRemove={() => handleRemove(filter)}
            >
              {filter}
            </Chip>
          ))}
          {activeFilters.length > 0 && (
            <button
              className="text-sm text-muted-foreground hover:underline"
              onClick={() => setActiveFilters([])}
            >
              Clear all
            </button>
          )}
        </div>
      </div>
    );
  },
};

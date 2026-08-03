import type { Meta, StoryObj } from '@storybook/react';

import { Separator } from './separator';

const meta = {
  title: 'Components/Separator',
  component: Separator,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    orientation: {
      control: 'radio',
      options: ['horizontal', 'vertical'],
    },
    decorative: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Separator>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default horizontal separator
 */
export const Default: Story = {
  args: {
    orientation: 'horizontal',
  },
  render: (args) => (
    <div className="w-64">
      <div className="text-sm">Content above</div>
      <Separator {...args} className="my-4" />
      <div className="text-sm">Content below</div>
    </div>
  ),
};

/**
 * Vertical separator for dividing content horizontally
 */
export const Vertical: Story = {
  args: {
    orientation: 'vertical',
  },
  render: (args) => (
    <div className="flex h-8 items-center gap-4">
      <div className="text-sm">Left</div>
      <Separator {...args} />
      <div className="text-sm">Right</div>
    </div>
  ),
};

/**
 * Decorative separator with no ARIA semantics
 */
export const Decorative: Story = {
  args: {
    decorative: true,
  },
  render: (args) => (
    <div className="w-64">
      <div className="text-sm">This separator is purely decorative</div>
      <Separator {...args} className="my-4" />
      <div className="text-sm">It has no semantic meaning</div>
    </div>
  ),
};

/**
 * In navigation context
 */
export const InNavigation: Story = {
  render: () => (
    <nav className="flex h-10 items-center gap-2 rounded-md border px-4">
      <a href="#" className="text-sm hover:underline">
        Home
      </a>
      <Separator orientation="vertical" decorative />
      <a href="#" className="text-sm hover:underline">
        Products
      </a>
      <Separator orientation="vertical" decorative />
      <a href="#" className="text-sm hover:underline">
        About
      </a>
    </nav>
  ),
};

/**
 * With custom styling
 */
export const CustomStyling: Story = {
  render: () => (
    <div className="w-64 space-y-4">
      <Separator className="bg-primary" />
      <Separator className="h-0.5 bg-gradient-to-r from-transparent via-border to-transparent" />
      <Separator className="border-t border-dashed border-border bg-transparent" />
    </div>
  ),
};

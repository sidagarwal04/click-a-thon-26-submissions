import type { Meta, StoryObj } from '@storybook/react';
import { expect, fn, userEvent, within } from 'storybook/test';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from './button';

/**
 * Button is a versatile component for triggering actions.
 * It supports multiple intents, sizes, loading states, and icon slots.
 */
const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    intent: {
      control: 'select',
      options: ['primary', 'secondary', 'danger', 'ghost', 'link'],
      description: 'Visual style variant of the button',
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
    fullWidth: {
      control: 'boolean',
      description: 'Makes button full width',
    },
    children: {
      control: 'text',
      description: 'Button content',
    },
  },
  args: {
    children: 'Button',
    intent: 'primary',
    size: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

/**
 * The default primary button style.
 */
export const Primary: Story = {
  args: {
    intent: 'primary',
    children: 'Primary Button',
  },
};

/**
 * Secondary button for less prominent actions.
 */
export const Secondary: Story = {
  args: {
    intent: 'secondary',
    children: 'Secondary Button',
  },
};

/**
 * Danger button for destructive actions.
 */
export const Danger: Story = {
  args: {
    intent: 'danger',
    children: 'Delete',
  },
};

/**
 * Ghost button for minimal visual emphasis.
 */
export const Ghost: Story = {
  args: {
    intent: 'ghost',
    children: 'Ghost Button',
  },
};

/**
 * Link-styled button.
 */
export const Link: Story = {
  args: {
    intent: 'link',
    children: 'Link Button',
  },
};

/**
 * Small sized button.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    children: 'Small',
  },
};

/**
 * Medium sized button (default).
 */
export const Medium: Story = {
  args: {
    size: 'md',
    children: 'Medium',
  },
};

/**
 * Large sized button.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    children: 'Large',
  },
};

/**
 * Disabled state.
 */
export const Disabled: Story = {
  args: {
    disabled: true,
    children: 'Disabled',
  },
};

/**
 * Loading state with spinner.
 */
export const Loading: Story = {
  args: {
    loading: true,
    children: 'Submitting...',
  },
};

/**
 * Full width button.
 */
export const FullWidth: Story = {
  args: {
    fullWidth: true,
    children: 'Full Width Button',
  },
  decorators: [
    (Story) => (
      <div style={{ width: '300px' }}>
        <Story />
      </div>
    ),
  ],
};

/**
 * Button with start icon.
 */
export const WithStartIcon: Story = {
  args: {
    children: 'Add Item',
    start: {
      children: <Icon name="plus" size="sm" />,
    },
  },
};

/**
 * Button with end icon.
 */
export const WithEndIcon: Story = {
  args: {
    children: 'Next',
    end: {
      children: <Icon name="chevron-right" size="sm" />,
    },
  },
};

/**
 * All button variants displayed together.
 */
export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Button intent="primary">Primary</Button>
        <Button intent="secondary">Secondary</Button>
        <Button intent="danger">Danger</Button>
        <Button intent="ghost">Ghost</Button>
        <Button intent="link">Link</Button>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Button size="sm">Small</Button>
        <Button size="md">Medium</Button>
        <Button size="lg">Large</Button>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Button disabled>Disabled</Button>
        <Button loading>Loading</Button>
      </div>
    </div>
  ),
};

/**
 * Interactive test demonstrating click behavior.
 * This story includes a play function that simulates user interactions
 * and verifies the expected behavior.
 */
export const InteractionTest: Story = {
  args: {
    children: 'Click Me',
    onClick: fn(),
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole('button', { name: /click me/i });

    // Verify button is visible and enabled
    await expect(button).toBeVisible();
    await expect(button).toBeEnabled();

    // Click the button
    await userEvent.click(button);

    // Verify onClick was called
    await expect(args.onClick).toHaveBeenCalledTimes(1);
  },
};

/**
 * Interactive test for keyboard accessibility.
 * Demonstrates that the button can be activated via keyboard.
 */
export const KeyboardAccessibility: Story = {
  args: {
    children: 'Press Enter',
    onClick: fn(),
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole('button', { name: /press enter/i });

    // Focus the button
    button.focus();
    await expect(button).toHaveFocus();

    // Press Enter to activate
    await userEvent.keyboard('{Enter}');
    await expect(args.onClick).toHaveBeenCalledTimes(1);

    // Press Space to activate
    await userEvent.keyboard(' ');
    await expect(args.onClick).toHaveBeenCalledTimes(2);
  },
};

/**
 * Interactive test verifying disabled state prevents clicks.
 */
export const DisabledInteraction: Story = {
  args: {
    children: 'Disabled Button',
    disabled: true,
    onClick: fn(),
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole('button', { name: /disabled button/i });

    // Verify button is disabled
    await expect(button).toBeDisabled();

    // Attempt to click - onClick should not be called
    await userEvent.click(button);
    await expect(args.onClick).not.toHaveBeenCalled();
  },
};

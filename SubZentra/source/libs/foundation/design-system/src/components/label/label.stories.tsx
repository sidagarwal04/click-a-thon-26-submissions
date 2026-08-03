import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Input } from '../input';
import { Label } from './label';

const meta = {
  title: 'Components/Label',
  component: Label,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'radio',
      options: ['sm', 'md'],
    },
    required: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Label>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default label
 */
export const Default: Story = {
  args: {
    children: 'Email Address',
    htmlFor: 'email',
  },
};

/**
 * Required field label
 */
export const Required: Story = {
  args: {
    children: 'Full Name',
    htmlFor: 'name',
    required: true,
  },
};

/**
 * Label with tooltip
 */
export const WithTooltip: Story = {
  args: {
    children: 'Password',
    htmlFor: 'password',
    tooltip: 'Password must be at least 8 characters long and contain a number',
  },
};

/**
 * Label with description
 */
export const WithDescription: Story = {
  args: {
    children: 'Biography',
    htmlFor: 'bio',
    description: 'Write a short bio about yourself. Maximum 500 characters.',
  },
};

/**
 * Label with icon
 */
export const WithIcon: Story = {
  args: {
    children: 'Email',
    htmlFor: 'email-icon',
    icon: <Icon name="mail" />,
  },
};

/**
 * Complete label with all features
 */
export const FullFeatured: Story = {
  args: {
    children: 'API Key',
    htmlFor: 'api-key',
    required: true,
    icon: <Icon name="key" />,
    tooltip: 'Your API key is used for authentication',
    description: 'Keep this key secure and never share it publicly',
  },
};

/**
 * Disabled state
 */
export const Disabled: Story = {
  args: {
    children: 'Disabled Field',
    htmlFor: 'disabled-field',
    disabled: true,
  },
};

/**
 * Error state
 */
export const Error: Story = {
  args: {
    children: 'Email Address',
    htmlFor: 'email-error',
    error: true,
    description: 'Please enter a valid email address',
  },
};

/**
 * Size variants
 */
export const Sizes: Story = {
  render: () => (
    <div className="space-y-4">
      <Label size="sm" htmlFor="small">
        Small Label
      </Label>
      <Label size="md" htmlFor="medium">
        Medium Label
      </Label>
    </div>
  ),
};

/**
 * Custom required indicator
 */
export const CustomRequiredIndicator: Story = {
  args: {
    children: 'Username',
    htmlFor: 'username',
    required: true,
    requiredIndicator: <span className="text-destructive text-xs">(required)</span>,
  },
};

/**
 * With form input
 */
export const WithInput: Story = {
  render: () => (
    <div className="w-64 space-y-2">
      <Label htmlFor="email-input" required tooltip="We'll never share your email">
        Email Address
      </Label>
      <Input id="email-input" type="email" placeholder="you@example.com" />
    </div>
  ),
};

/**
 * Form field with error
 */
export const FormFieldWithError: Story = {
  render: () => (
    <div className="w-64 space-y-2">
      <Label
        htmlFor="email-error-input"
        required
        error
        description="Please enter a valid email address"
      >
        Email Address
      </Label>
      <Input
        id="email-error-input"
        type="email"
        placeholder="you@example.com"
        className="border-destructive"
      />
    </div>
  ),
};

/**
 * Multiple form fields
 */
export const FormExample: Story = {
  render: () => (
    <form className="w-72 space-y-4">
      <div className="space-y-2">
        <Label htmlFor="fname" required>
          First Name
        </Label>
        <Input id="fname" placeholder="John" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="lname" required>
          Last Name
        </Label>
        <Input id="lname" placeholder="Doe" />
      </div>

      <div className="space-y-2">
        <Label
          htmlFor="email-form"
          required
          icon={<Icon name="mail" />}
          tooltip="Used for account recovery"
        >
          Email
        </Label>
        <Input id="email-form" type="email" placeholder="john@example.com" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="phone" description="Optional - for two-factor authentication">
          Phone Number
        </Label>
        <Input id="phone" type="tel" placeholder="+1 (555) 000-0000" />
      </div>
    </form>
  ),
};

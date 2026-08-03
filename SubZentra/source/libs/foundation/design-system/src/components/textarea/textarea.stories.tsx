import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Textarea } from './textarea';

/**
 * Textarea component for multi-line text input.
 * Supports validation states and form integration.
 */
const meta: Meta<typeof Textarea> = {
  title: 'Components/Textarea',
  component: Textarea,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the textarea',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the textarea',
    },
    invalid: {
      control: 'boolean',
      description: 'Invalid/error state',
    },
    readOnly: {
      control: 'boolean',
      description: 'Read-only state',
    },
    rows: {
      control: { type: 'number', min: 1, max: 20 },
      description: 'Number of visible rows',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text',
    },
  },
  args: {
    size: 'md',
    rows: 3,
    placeholder: 'Enter text...',
  },
  decorators: [
    (Story) => (
      <div style={{ width: '300px' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof Textarea>;

/**
 * Default textarea.
 */
export const Default: Story = {
  args: {
    placeholder: 'Enter your message...',
  },
};

/**
 * Textarea with value.
 */
export const WithValue: Story = {
  args: {
    defaultValue:
      'This is some example text that demonstrates how the textarea looks with content inside it.',
  },
};

/**
 * Small textarea.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    placeholder: 'Small textarea',
  },
};

/**
 * Large textarea.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    placeholder: 'Large textarea',
  },
};

/**
 * More rows.
 */
export const MoreRows: Story = {
  args: {
    rows: 6,
    placeholder: 'This textarea has more rows...',
  },
};

/**
 * Disabled textarea.
 */
export const Disabled: Story = {
  args: {
    disabled: true,
    defaultValue: 'This textarea is disabled',
  },
};

/**
 * Invalid/error textarea.
 */
export const Invalid: Story = {
  args: {
    invalid: true,
    defaultValue: 'This content has validation errors',
  },
};

/**
 * Read-only textarea.
 */
export const ReadOnly: Story = {
  args: {
    readOnly: true,
    defaultValue:
      'This is read-only content that cannot be edited by the user but can be selected and copied.',
  },
};

/**
 * Textarea with max length.
 */
export const WithMaxLength: Story = {
  args: {
    maxLength: 100,
    placeholder: 'Max 100 characters',
  },
};

/**
 * Textarea with validation error.
 */
export const WithError: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <Textarea invalid defaultValue="Short" aria-describedby="message-error" />
      <span id="message-error" style={{ color: '#dc2626', fontSize: '14px' }}>
        Message must be at least 10 characters
      </span>
    </div>
  ),
};

/**
 * All textarea sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Small</p>
        <Textarea size="sm" placeholder="Small textarea" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Medium</p>
        <Textarea size="md" placeholder="Medium textarea" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Large</p>
        <Textarea size="lg" placeholder="Large textarea" />
      </div>
    </div>
  ),
};

/**
 * All textarea states.
 */
export const AllStates: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Default</p>
        <Textarea placeholder="Default textarea" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Disabled</p>
        <Textarea disabled defaultValue="Disabled textarea" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Read-only</p>
        <Textarea readOnly defaultValue="Read-only textarea" />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 500 }}>Invalid</p>
        <Textarea invalid defaultValue="Invalid textarea" />
      </div>
    </div>
  ),
};

/**
 * Form example with textarea.
 */
export const FormExample: Story = {
  render: () => (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        console.log('Form submitted!');
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
    >
      <div>
        <label
          htmlFor="feedback"
          style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}
        >
          Your feedback
        </label>
        <Textarea id="feedback" name="feedback" placeholder="Tell us what you think..." rows={5} />
      </div>
      <button
        type="submit"
        style={{
          padding: '8px 16px',
          backgroundColor: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer',
          width: 'fit-content',
        }}
      >
        Submit
      </button>
    </form>
  ),
};

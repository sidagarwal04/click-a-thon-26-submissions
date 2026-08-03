import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Alert } from './alert';

/**
 * Alert component for displaying important messages to users.
 * Supports different intents, optional titles, and dismissible functionality.
 */
const meta: Meta<typeof Alert> = {
  title: 'Components/Alert',
  component: Alert,
  tags: ['autodocs'],
  argTypes: {
    intent: {
      control: 'select',
      options: ['info', 'success', 'warning', 'error'],
      description: 'Visual style variant of the alert',
    },
    dismissible: {
      control: 'boolean',
      description: 'Shows dismiss button',
    },
    title: {
      control: 'text',
      description: 'Alert title',
    },
    children: {
      control: 'text',
      description: 'Alert content',
    },
  },
  args: {
    intent: 'info',
    children: 'This is an alert message.',
  },
};

export default meta;
type Story = StoryObj<typeof Alert>;

/**
 * Info alert for general information.
 */
export const Info: Story = {
  args: {
    intent: 'info',
    children: 'This is an informational message.',
  },
};

/**
 * Success alert for positive feedback.
 */
export const Success: Story = {
  args: {
    intent: 'success',
    children: 'Your changes have been saved successfully.',
  },
};

/**
 * Warning alert for cautionary messages.
 */
export const Warning: Story = {
  args: {
    intent: 'warning',
    children: 'Please review your input before continuing.',
  },
};

/**
 * Error alert for error messages.
 */
export const Error: Story = {
  args: {
    intent: 'error',
    children: 'An error occurred. Please try again.',
  },
};

/**
 * Alert with a title.
 */
export const WithTitle: Story = {
  args: {
    intent: 'success',
    title: 'Success!',
    children: 'Your changes have been saved successfully.',
  },
};

/**
 * Dismissible alert with close button.
 */
export const Dismissible: Story = {
  args: {
    intent: 'info',
    dismissible: true,
    children: 'Click the X to dismiss this alert.',
    onDismiss: () => console.log('Alert dismissed!'),
  },
};

/**
 * Dismissible alert with title.
 */
export const DismissibleWithTitle: Story = {
  args: {
    intent: 'warning',
    dismissible: true,
    title: 'Heads up!',
    children: 'This action may take a while to complete.',
    onDismiss: () => console.log('Alert dismissed!'),
  },
};

/**
 * All alert variants displayed together.
 */
export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '400px' }}>
      <Alert intent="info">This is an info alert.</Alert>
      <Alert intent="success">This is a success alert.</Alert>
      <Alert intent="warning">This is a warning alert.</Alert>
      <Alert intent="error">This is an error alert.</Alert>
      <Alert intent="info" title="With Title">
        Alerts can have titles for emphasis.
      </Alert>
      <Alert intent="success" dismissible onDismiss={() => undefined}>
        This alert can be dismissed.
      </Alert>
    </div>
  ),
};

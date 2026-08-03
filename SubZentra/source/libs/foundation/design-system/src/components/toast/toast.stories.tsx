import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from '../button';
import { Toast } from './toast';

const meta = {
  title: 'Components/Toast',
  component: Toast,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    feedback: {
      control: 'select',
      options: ['info', 'success', 'warning', 'error'],
    },
    closable: {
      control: 'boolean',
    },
  },
  decorators: [
    (Story) => (
      <div className="w-96">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Toast>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default info toast
 */
export const Default: Story = {
  render: () => (
    <Toast feedback="info" closable>
      <Toast.Title>Information</Toast.Title>
      <Toast.Description>This is an informational message for the user.</Toast.Description>
    </Toast>
  ),
};

/**
 * Success toast
 */
export const Success: Story = {
  render: () => (
    <Toast feedback="success" closable>
      <Toast.Title>Success!</Toast.Title>
      <Toast.Description>Your changes have been saved successfully.</Toast.Description>
    </Toast>
  ),
};

/**
 * Warning toast
 */
export const Warning: Story = {
  render: () => (
    <Toast feedback="warning" closable>
      <Toast.Title>Warning</Toast.Title>
      <Toast.Description>Your session will expire in 5 minutes.</Toast.Description>
    </Toast>
  ),
};

/**
 * Error toast
 */
export const Error: Story = {
  render: () => (
    <Toast feedback="error" closable>
      <Toast.Title>Error</Toast.Title>
      <Toast.Description>Failed to save changes. Please try again.</Toast.Description>
    </Toast>
  ),
};

/**
 * Toast with actions
 */
export const WithActions: Story = {
  render: () => (
    <Toast feedback="error" closable>
      <Toast.Title>Connection lost</Toast.Title>
      <Toast.Description>
        Unable to connect to the server. Please check your internet connection.
      </Toast.Description>
      <Toast.Actions>
        <Button size="sm" intent="secondary">
          Retry
        </Button>
        <Button size="sm" intent="ghost">
          Dismiss
        </Button>
      </Toast.Actions>
    </Toast>
  ),
};

/**
 * Simple toast without close button
 */
export const NotClosable: Story = {
  render: () => (
    <Toast feedback="success">
      <Toast.Title>Auto-dismissing toast</Toast.Title>
      <Toast.Description>This toast will auto-dismiss after a few seconds.</Toast.Description>
    </Toast>
  ),
};

/**
 * Custom start icon
 */
export const CustomIcon: Story = {
  render: () => (
    <Toast feedback="info" closable start={<Icon name="bell" />}>
      <Toast.Title>New notification</Toast.Title>
      <Toast.Description>You have 3 new messages in your inbox.</Toast.Description>
    </Toast>
  ),
};

/**
 * Toast with body content
 */
export const WithBody: Story = {
  render: () => (
    <Toast feedback="info" closable>
      <Toast.Title>Update available</Toast.Title>
      <Toast.Description>A new version is ready to install.</Toast.Description>
      <Toast.Body>
        <div className="mt-2 rounded border bg-muted/50 p-2 text-xs">
          <div>Version: 2.0.0</div>
          <div>Size: 15.3 MB</div>
        </div>
      </Toast.Body>
      <Toast.Actions>
        <Button size="sm">Install now</Button>
        <Button size="sm" intent="ghost">
          Later
        </Button>
      </Toast.Actions>
    </Toast>
  ),
};

/**
 * All feedback variants
 */
export const AllVariants: Story = {
  render: () => (
    <div className="space-y-4">
      <Toast feedback="info" closable>
        <Toast.Title>Info</Toast.Title>
        <Toast.Description>Informational message</Toast.Description>
      </Toast>
      <Toast feedback="success" closable>
        <Toast.Title>Success</Toast.Title>
        <Toast.Description>Success message</Toast.Description>
      </Toast>
      <Toast feedback="warning" closable>
        <Toast.Title>Warning</Toast.Title>
        <Toast.Description>Warning message</Toast.Description>
      </Toast>
      <Toast feedback="error" closable>
        <Toast.Title>Error</Toast.Title>
        <Toast.Description>Error message</Toast.Description>
      </Toast>
    </div>
  ),
};

/**
 * Title only
 */
export const TitleOnly: Story = {
  render: () => (
    <Toast feedback="success" closable>
      <Toast.Title>Changes saved successfully</Toast.Title>
    </Toast>
  ),
};

/**
 * Undo action pattern
 */
export const UndoPattern: Story = {
  render: () => (
    <Toast feedback="info" closable>
      <Toast.Title>Item deleted</Toast.Title>
      <Toast.Description>The item has been moved to trash.</Toast.Description>
      <Toast.Actions>
        <Button size="sm" intent="secondary">
          Undo
        </Button>
      </Toast.Actions>
    </Toast>
  ),
};

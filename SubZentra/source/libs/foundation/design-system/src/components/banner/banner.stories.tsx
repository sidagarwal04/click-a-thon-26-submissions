import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from '../button';
import { Banner } from './banner';

const meta = {
  title: 'Components/Banner',
  component: Banner,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['info', 'success', 'warning', 'error'],
    },
    type: {
      control: 'radio',
      options: ['inline', 'section'],
    },
    spotlight: {
      control: 'boolean',
    },
    dismissible: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Banner>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default info banner
 */
export const Default: Story = {
  render: () => (
    <Banner variant="info" dismissible>
      <Banner.Title>New Update Available</Banner.Title>
      <Banner.Description>
        A new version of the application is available. Refresh to update.
      </Banner.Description>
    </Banner>
  ),
};

/**
 * Success banner
 */
export const Success: Story = {
  render: () => (
    <Banner variant="success" dismissible>
      <Banner.Title>Payment Successful</Banner.Title>
      <Banner.Description>
        Your payment has been processed successfully. You will receive a confirmation email shortly.
      </Banner.Description>
    </Banner>
  ),
};

/**
 * Warning banner
 */
export const Warning: Story = {
  render: () => (
    <Banner variant="warning" dismissible>
      <Banner.Title>Subscription Expiring</Banner.Title>
      <Banner.Description>
        Your subscription will expire in 7 days. Renew now to avoid service interruption.
      </Banner.Description>
      <Banner.Actions>
        <Button size="sm">Renew Now</Button>
      </Banner.Actions>
    </Banner>
  ),
};

/**
 * Error banner
 */
export const Error: Story = {
  render: () => (
    <Banner variant="error" dismissible>
      <Banner.Title>Connection Error</Banner.Title>
      <Banner.Description>
        Unable to connect to the server. Please check your internet connection and try again.
      </Banner.Description>
      <Banner.Actions>
        <Button size="sm" intent="secondary">
          Retry
        </Button>
      </Banner.Actions>
    </Banner>
  ),
};

/**
 * Spotlight mode (emphasized left border)
 */
export const Spotlight: Story = {
  render: () => (
    <div className="space-y-4">
      <Banner variant="info" spotlight>
        <Banner.Title>Info Spotlight</Banner.Title>
        <Banner.Description>
          This banner has a highlighted left border for emphasis.
        </Banner.Description>
      </Banner>
      <Banner variant="warning" spotlight dismissible>
        <Banner.Title>Warning Spotlight</Banner.Title>
        <Banner.Description>Important warning that needs attention.</Banner.Description>
      </Banner>
    </div>
  ),
};

/**
 * Section type (full width, no rounded corners)
 */
export const Section: Story = {
  parameters: {
    layout: 'fullscreen',
  },
  render: () => (
    <Banner variant="info" type="section" dismissible>
      <Banner.Title>System Maintenance</Banner.Title>
      <Banner.Description>
        We will be performing scheduled maintenance on Saturday from 2:00 AM to 4:00 AM EST.
      </Banner.Description>
    </Banner>
  ),
};

/**
 * All variants
 */
export const AllVariants: Story = {
  render: () => (
    <div className="space-y-4">
      <Banner variant="info" dismissible>
        <Banner.Title>Info Banner</Banner.Title>
        <Banner.Description>Informational message for the user.</Banner.Description>
      </Banner>
      <Banner variant="success" dismissible>
        <Banner.Title>Success Banner</Banner.Title>
        <Banner.Description>Operation completed successfully.</Banner.Description>
      </Banner>
      <Banner variant="warning" dismissible>
        <Banner.Title>Warning Banner</Banner.Title>
        <Banner.Description>Something needs your attention.</Banner.Description>
      </Banner>
      <Banner variant="error" dismissible>
        <Banner.Title>Error Banner</Banner.Title>
        <Banner.Description>An error occurred.</Banner.Description>
      </Banner>
    </div>
  ),
};

/**
 * With custom icon
 */
export const CustomIcon: Story = {
  render: () => (
    <Banner variant="info" dismissible icon={<Icon name="sparkles" />}>
      <Banner.Title>New Feature</Banner.Title>
      <Banner.Description>
        We've just launched a new feature that you might be interested in!
      </Banner.Description>
      <Banner.Actions>
        <Button size="sm">Learn More</Button>
        <Button size="sm" intent="ghost">
          Not Now
        </Button>
      </Banner.Actions>
    </Banner>
  ),
};

/**
 * With body content
 */
export const WithBody: Story = {
  render: () => (
    <Banner variant="warning" dismissible>
      <Banner.Title>Action Required</Banner.Title>
      <Banner.Description>Please review the following items before proceeding.</Banner.Description>
      <Banner.Body>
        <ul className="mt-2 list-disc list-inside text-sm text-yellow-700 dark:text-yellow-300">
          <li>Update your billing information</li>
          <li>Verify your email address</li>
          <li>Complete your profile</li>
        </ul>
      </Banner.Body>
      <Banner.Actions>
        <Button size="sm">Complete Setup</Button>
      </Banner.Actions>
    </Banner>
  ),
};

/**
 * Interactive dismissible example
 */
export const Interactive: Story = {
  render: function InteractiveBanner() {
    const [visible, setVisible] = useState(true);

    if (!visible) {
      return <Button onClick={() => setVisible(true)}>Show Banner</Button>;
    }

    return (
      <Banner variant="success" dismissible onDismiss={() => setVisible(false)}>
        <Banner.Title>Welcome Back!</Banner.Title>
        <Banner.Description>You have 3 new notifications since your last visit.</Banner.Description>
        <Banner.Actions>
          <Button size="sm">View Notifications</Button>
        </Banner.Actions>
      </Banner>
    );
  },
};

/**
 * Not dismissible
 */
export const NotDismissible: Story = {
  render: () => (
    <Banner variant="error">
      <Banner.Title>Service Unavailable</Banner.Title>
      <Banner.Description>
        This service is currently unavailable. We are working to restore it.
      </Banner.Description>
    </Banner>
  ),
};

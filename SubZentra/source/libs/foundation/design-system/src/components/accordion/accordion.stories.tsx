import type { Meta, StoryObj } from '@storybook/react';

import { Accordion } from './accordion';

const meta = {
  title: 'Components/Accordion',
  component: Accordion,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'bordered', 'separated'],
    },
    multiple: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
  },
  decorators: [
    (Story) => (
      <div className="w-[500px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Accordion>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default accordion
 */
export const Default: Story = {
  render: () => (
    <Accordion defaultValue={['item-1']}>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>Is it accessible?</Accordion.Trigger>
        <Accordion.Content>Yes. It adheres to the WAI-ARIA design pattern.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2">
        <Accordion.Trigger>Is it styled?</Accordion.Trigger>
        <Accordion.Content>
          Yes. It comes with default styles that match the design system.
        </Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-3">
        <Accordion.Trigger>Is it animated?</Accordion.Trigger>
        <Accordion.Content>
          Yes. It's animated by default with smooth height transitions.
        </Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * Bordered variant
 */
export const Bordered: Story = {
  render: () => (
    <Accordion variant="bordered" defaultValue={['item-1']}>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>Section 1</Accordion.Trigger>
        <Accordion.Content>
          Content for section 1. This variant has a border around all items.
        </Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2">
        <Accordion.Trigger>Section 2</Accordion.Trigger>
        <Accordion.Content>Content for section 2.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-3">
        <Accordion.Trigger>Section 3</Accordion.Trigger>
        <Accordion.Content>Content for section 3.</Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * Separated variant
 */
export const Separated: Story = {
  render: () => (
    <Accordion variant="separated" defaultValue={['item-1']}>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>What is your refund policy?</Accordion.Trigger>
        <Accordion.Content>
          We offer a 30-day money-back guarantee on all purchases.
        </Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2">
        <Accordion.Trigger>How do I track my order?</Accordion.Trigger>
        <Accordion.Content>
          You can track your order using the tracking link sent to your email.
        </Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-3">
        <Accordion.Trigger>Do you offer international shipping?</Accordion.Trigger>
        <Accordion.Content>Yes, we ship to over 100 countries worldwide.</Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * Multiple items open
 */
export const Multiple: Story = {
  render: () => (
    <Accordion multiple defaultValue={['item-1', 'item-2']}>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>First item (open)</Accordion.Trigger>
        <Accordion.Content>
          With multiple mode enabled, you can have multiple items open at once.
        </Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2">
        <Accordion.Trigger>Second item (also open)</Accordion.Trigger>
        <Accordion.Content>This item is also open by default.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-3">
        <Accordion.Trigger>Third item</Accordion.Trigger>
        <Accordion.Content>Click to open this one too.</Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * Disabled accordion
 */
export const Disabled: Story = {
  render: () => (
    <Accordion disabled>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>Disabled item 1</Accordion.Trigger>
        <Accordion.Content>This content is inaccessible.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2">
        <Accordion.Trigger>Disabled item 2</Accordion.Trigger>
        <Accordion.Content>This content is also inaccessible.</Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * Single disabled item
 */
export const SingleDisabledItem: Story = {
  render: () => (
    <Accordion>
      <Accordion.Item value="item-1">
        <Accordion.Trigger>Enabled item</Accordion.Trigger>
        <Accordion.Content>This item works normally.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-2" disabled>
        <Accordion.Trigger>Disabled item</Accordion.Trigger>
        <Accordion.Content>This content is inaccessible.</Accordion.Content>
      </Accordion.Item>
      <Accordion.Item value="item-3">
        <Accordion.Trigger>Another enabled item</Accordion.Trigger>
        <Accordion.Content>This item also works normally.</Accordion.Content>
      </Accordion.Item>
    </Accordion>
  ),
};

/**
 * All variants comparison
 */
export const AllVariants: Story = {
  render: () => (
    <div className="space-y-8">
      <div>
        <h3 className="mb-2 text-sm font-medium">Default</h3>
        <Accordion variant="default" defaultValue={['item-1']}>
          <Accordion.Item value="item-1">
            <Accordion.Trigger>Item 1</Accordion.Trigger>
            <Accordion.Content>Content 1</Accordion.Content>
          </Accordion.Item>
          <Accordion.Item value="item-2">
            <Accordion.Trigger>Item 2</Accordion.Trigger>
            <Accordion.Content>Content 2</Accordion.Content>
          </Accordion.Item>
        </Accordion>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Bordered</h3>
        <Accordion variant="bordered" defaultValue={['item-1']}>
          <Accordion.Item value="item-1">
            <Accordion.Trigger>Item 1</Accordion.Trigger>
            <Accordion.Content>Content 1</Accordion.Content>
          </Accordion.Item>
          <Accordion.Item value="item-2">
            <Accordion.Trigger>Item 2</Accordion.Trigger>
            <Accordion.Content>Content 2</Accordion.Content>
          </Accordion.Item>
        </Accordion>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Separated</h3>
        <Accordion variant="separated" defaultValue={['item-1']}>
          <Accordion.Item value="item-1">
            <Accordion.Trigger>Item 1</Accordion.Trigger>
            <Accordion.Content>Content 1</Accordion.Content>
          </Accordion.Item>
          <Accordion.Item value="item-2">
            <Accordion.Trigger>Item 2</Accordion.Trigger>
            <Accordion.Content>Content 2</Accordion.Content>
          </Accordion.Item>
        </Accordion>
      </div>
    </div>
  ),
};

/**
 * FAQ example
 */
export const FAQExample: Story = {
  render: () => (
    <div>
      <h2 className="mb-4 text-xl font-semibold">Frequently Asked Questions</h2>
      <Accordion variant="separated">
        <Accordion.Item value="faq-1">
          <Accordion.Trigger>What payment methods do you accept?</Accordion.Trigger>
          <Accordion.Content>
            We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and bank
            transfers. For enterprise customers, we also offer invoice-based payments.
          </Accordion.Content>
        </Accordion.Item>
        <Accordion.Item value="faq-2">
          <Accordion.Trigger>Can I cancel my subscription anytime?</Accordion.Trigger>
          <Accordion.Content>
            Yes, you can cancel your subscription at any time. If you cancel, you'll continue to
            have access until the end of your current billing period.
          </Accordion.Content>
        </Accordion.Item>
        <Accordion.Item value="faq-3">
          <Accordion.Trigger>Do you offer a free trial?</Accordion.Trigger>
          <Accordion.Content>
            Yes! We offer a 14-day free trial on all plans. No credit card required to start your
            trial.
          </Accordion.Content>
        </Accordion.Item>
        <Accordion.Item value="faq-4">
          <Accordion.Trigger>How do I contact support?</Accordion.Trigger>
          <Accordion.Content>
            You can reach our support team via email at support@example.com, through the in-app
            chat, or by scheduling a call with our team. Enterprise customers have access to
            dedicated support channels.
          </Accordion.Content>
        </Accordion.Item>
      </Accordion>
    </div>
  ),
};

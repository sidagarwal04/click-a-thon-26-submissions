import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Card } from './card';

/**
 * Card groups related content into one bordered panel.
 */
const meta: Meta<typeof Card> = {
  title: 'Components/Card',
  component: Card,
  tags: ['autodocs'],
  argTypes: {
    padding: {
      control: 'select',
      options: ['none', 'sm', 'md', 'lg'],
      description: 'Inner padding',
    },
    emphasis: {
      control: 'boolean',
      description: 'Draw the card with an accent border',
    },
  },
  args: {
    padding: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Card>;

/**
 * A plain panel.
 */
export const Default: Story = {
  args: {
    children: <p className="text-sm text-foreground-muted">Governed metrics only.</p>,
  },
};

/**
 * With a header row and a title.
 */
export const WithHeader: Story = {
  args: {
    children: (
      <>
        <Card.Header end={<span className="text-xs text-foreground-muted">Stable</span>}>
          <Card.Title>Security protocols</Card.Title>
        </Card.Header>
        <p className="text-sm text-foreground-muted">
          Require biometric trace for all critical analysis executions.
        </p>
      </>
    ),
  },
};

/**
 * The accent border marks the one card carrying the page's primary signal.
 */
export const Emphasis: Story = {
  args: {
    emphasis: true,
    children: (
      <>
        <Card.Header>
          <Card.Title>Secure endpoints</Card.Title>
        </Card.Header>
        <p className="text-2xl">08</p>
      </>
    ),
  },
};

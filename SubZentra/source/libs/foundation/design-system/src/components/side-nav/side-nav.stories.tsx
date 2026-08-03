import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Button } from '../button';
import { SideNav } from './side-nav';

/**
 * SideNav is the product's primary navigation rail.
 */
const meta: Meta<typeof SideNav> = {
  title: 'Components/SideNav',
  component: SideNav,
  tags: ['autodocs'],
  argTypes: {
    width: {
      control: 'select',
      options: ['compact', 'default'],
      description: 'Rail width',
    },
  },
  args: {
    width: 'default',
    'aria-label': 'Primary',
  },
  decorators: [
    (Story) => (
      <div className="h-[420px] bg-background">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SideNav>;

const items = (
  <>
    <SideNav.Item href="#" active>
      Dashboard
    </SideNav.Item>
    <SideNav.Item href="#">Investigations</SideNav.Item>
    <SideNav.Item href="#">Datasets</SideNav.Item>
    <SideNav.Item href="#">Settings</SideNav.Item>
  </>
);

/**
 * The rail on its own.
 */
export const Default: Story = {
  args: {
    children: items,
  },
};

/**
 * With the brand lockup and a pinned footer action.
 */
export const WithBrandAndFooter: Story = {
  args: {
    brand: <span className="font-mono text-lg font-bold text-primary">ODDESSY</span>,
    footer: <Button fullWidth>New analysis</Button>,
    children: items,
  },
};

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Button } from '../button';
import { Input } from '../input';
import { Popover } from './popover';

const meta = {
  title: 'Components/Popover',
  component: Popover,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    maxWidth: {
      control: 'select',
      options: ['320', '480', '720', 'auto'],
    },
    side: {
      control: 'select',
      options: ['top', 'right', 'bottom', 'left'],
    },
    align: {
      control: 'select',
      options: ['start', 'center', 'end'],
    },
    arrow: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Popover>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default popover
 */
export const Default: Story = {
  render: () => (
    <Popover>
      <Popover.Trigger>
        <Button intent="secondary">Open Popover</Button>
      </Popover.Trigger>
      <Popover.Content>
        <div className="space-y-2">
          <h4 className="font-semibold">Dimensions</h4>
          <p className="text-sm text-muted-foreground">Set the dimensions for the layer.</p>
        </div>
      </Popover.Content>
    </Popover>
  ),
};

/**
 * With arrow
 */
export const WithArrow: Story = {
  render: () => (
    <Popover arrow>
      <Popover.Trigger>
        <Button intent="secondary">With Arrow</Button>
      </Popover.Trigger>
      <Popover.Content>
        <div className="space-y-2">
          <h4 className="font-semibold">Popover with Arrow</h4>
          <p className="text-sm text-muted-foreground">
            This popover has an arrow pointing to the trigger.
          </p>
        </div>
      </Popover.Content>
    </Popover>
  ),
};

/**
 * Different positions
 */
export const Positions: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4 p-20">
      <Popover side="top" arrow>
        <Popover.Trigger>
          <Button intent="secondary">Top</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Positioned on top</p>
        </Popover.Content>
      </Popover>

      <Popover side="right" arrow>
        <Popover.Trigger>
          <Button intent="secondary">Right</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Positioned on right</p>
        </Popover.Content>
      </Popover>

      <Popover side="bottom" arrow>
        <Popover.Trigger>
          <Button intent="secondary">Bottom</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Positioned on bottom</p>
        </Popover.Content>
      </Popover>

      <Popover side="left" arrow>
        <Popover.Trigger>
          <Button intent="secondary">Left</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Positioned on left</p>
        </Popover.Content>
      </Popover>
    </div>
  ),
};

/**
 * Alignment options
 */
export const Alignments: Story = {
  render: () => (
    <div className="flex gap-4">
      <Popover align="start">
        <Popover.Trigger>
          <Button intent="secondary">Start</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Aligned to start</p>
        </Popover.Content>
      </Popover>

      <Popover align="center">
        <Popover.Trigger>
          <Button intent="secondary">Center</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Aligned to center</p>
        </Popover.Content>
      </Popover>

      <Popover align="end">
        <Popover.Trigger>
          <Button intent="secondary">End</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">Aligned to end</p>
        </Popover.Content>
      </Popover>
    </div>
  ),
};

/**
 * Different max widths
 */
export const MaxWidths: Story = {
  render: () => (
    <div className="flex gap-4">
      <Popover maxWidth="320">
        <Popover.Trigger>
          <Button intent="secondary">320px</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">
            This popover has a max width of 320px. Lorem ipsum dolor sit amet, consectetur
            adipiscing elit.
          </p>
        </Popover.Content>
      </Popover>

      <Popover maxWidth="480">
        <Popover.Trigger>
          <Button intent="secondary">480px</Button>
        </Popover.Trigger>
        <Popover.Content>
          <p className="text-sm">
            This popover has a max width of 480px. Lorem ipsum dolor sit amet, consectetur
            adipiscing elit.
          </p>
        </Popover.Content>
      </Popover>
    </div>
  ),
};

/**
 * With form content
 */
export const WithForm: Story = {
  render: () => (
    <Popover maxWidth="480">
      <Popover.Trigger>
        <Button>Edit dimensions</Button>
      </Popover.Trigger>
      <Popover.Content>
        <div className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium">Dimensions</h4>
            <p className="text-sm text-muted-foreground">Set the dimensions for the layer.</p>
          </div>
          <div className="grid gap-2">
            <div className="grid grid-cols-3 items-center gap-4">
              <label className="text-sm">Width</label>
              <Input className="col-span-2" defaultValue="100%" />
            </div>
            <div className="grid grid-cols-3 items-center gap-4">
              <label className="text-sm">Max. width</label>
              <Input className="col-span-2" defaultValue="300px" />
            </div>
            <div className="grid grid-cols-3 items-center gap-4">
              <label className="text-sm">Height</label>
              <Input className="col-span-2" defaultValue="25px" />
            </div>
            <div className="grid grid-cols-3 items-center gap-4">
              <label className="text-sm">Max. height</label>
              <Input className="col-span-2" defaultValue="none" />
            </div>
          </div>
        </div>
      </Popover.Content>
    </Popover>
  ),
};

/**
 * Icon trigger
 */
export const IconTrigger: Story = {
  render: () => (
    <Popover arrow>
      <Popover.Trigger>
        <Button intent="ghost" aria-label="Info">
          <Icon name="info" />
        </Button>
      </Popover.Trigger>
      <Popover.Content>
        <div className="space-y-2">
          <h4 className="font-semibold">Help</h4>
          <p className="text-sm text-muted-foreground">
            This is additional information about this feature.
          </p>
        </div>
      </Popover.Content>
    </Popover>
  ),
};

/**
 * With close button
 */
export const WithCloseButton: Story = {
  render: () => (
    <Popover>
      <Popover.Trigger>
        <Button intent="secondary">Open</Button>
      </Popover.Trigger>
      <Popover.Content>
        <Popover.Close />
        <div className="space-y-2 pr-6">
          <h4 className="font-semibold">Notification</h4>
          <p className="text-sm text-muted-foreground">You have 3 new messages in your inbox.</p>
          <Button size="sm" className="mt-2">
            View all
          </Button>
        </div>
      </Popover.Content>
    </Popover>
  ),
};

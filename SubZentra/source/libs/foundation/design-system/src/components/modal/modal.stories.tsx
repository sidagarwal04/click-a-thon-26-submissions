import { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';
import { expect, userEvent, within } from 'storybook/test';

import { Button } from '../button';
import { Input } from '../input';
import { Modal } from './modal';

const meta = {
  title: 'Components/Modal',
  component: Modal,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['480', '720', '960', '1080', 'full'],
    },
    fillContainer: {
      control: 'boolean',
    },
    fitContent: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Modal>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default modal
 */
export const Default: Story = {
  render: () => (
    <Modal>
      <Modal.Trigger>
        <Button>Open Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Edit Profile</Modal.Title>
          <Modal.Description>
            Make changes to your profile here. Click save when you're done.
          </Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input placeholder="Enter your name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" placeholder="Enter your email" />
            </div>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Cancel</Button>
          </Modal.Close>
          <Button>Save changes</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Small modal (480px)
 */
export const Small: Story = {
  render: () => (
    <Modal size="480">
      <Modal.Trigger>
        <Button>Small Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Confirm Action</Modal.Title>
          <Modal.Description>Are you sure you want to proceed?</Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Cancel</Button>
          </Modal.Close>
          <Button>Confirm</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Large modal (960px)
 */
export const Large: Story = {
  render: () => (
    <Modal size="960">
      <Modal.Trigger>
        <Button>Large Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Large Content Area</Modal.Title>
          <Modal.Description>This modal has more space for complex content.</Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">First Name</label>
              <Input placeholder="First name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Last Name</label>
              <Input placeholder="Last name" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" placeholder="Email" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Phone</label>
              <Input type="tel" placeholder="Phone" />
            </div>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Cancel</Button>
          </Modal.Close>
          <Button>Save</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Full screen modal
 */
export const FullScreen: Story = {
  render: () => (
    <Modal size="full">
      <Modal.Trigger>
        <Button>Full Screen Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Full Screen Content</Modal.Title>
          <Modal.Description>This modal takes up most of the viewport.</Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Full screen content area
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Close</Button>
          </Modal.Close>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Controlled modal
 */
export const Controlled: Story = {
  render: function ControlledModal() {
    const [open, setOpen] = useState(false);

    return (
      <div className="space-x-2">
        <Button onClick={() => setOpen(true)}>Open Modal</Button>
        <Modal open={open} onOpenChange={setOpen}>
          <Modal.Content>
            <Modal.Header>
              <Modal.Title>Controlled Modal</Modal.Title>
              <Modal.Description>This modal is controlled via state.</Modal.Description>
              <Modal.Close />
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm text-muted-foreground">Open state: {open ? 'true' : 'false'}</p>
            </Modal.Body>
            <Modal.Footer>
              <Button intent="secondary" onClick={() => setOpen(false)}>
                Close via state
              </Button>
            </Modal.Footer>
          </Modal.Content>
        </Modal>
      </div>
    );
  },
};

/**
 * Modal with long content (scrollable)
 */
export const ScrollableContent: Story = {
  render: () => (
    <Modal>
      <Modal.Trigger>
        <Button>Scrollable Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Terms of Service</Modal.Title>
          <Modal.Description>Please read and accept our terms of service.</Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <div className="space-y-4">
            {Array.from({ length: 20 }).map((_, i) => (
              <p key={i} className="text-sm text-muted-foreground">
                Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
                incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
                exercitation ullamco laboris.
              </p>
            ))}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Decline</Button>
          </Modal.Close>
          <Button>Accept</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Confirmation dialog pattern
 */
export const ConfirmationDialog: Story = {
  render: () => (
    <Modal size="480">
      <Modal.Trigger>
        <Button intent="danger">Delete Item</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Delete Item</Modal.Title>
          <Modal.Description>
            Are you sure you want to delete this item? This action cannot be undone.
          </Modal.Description>
        </Modal.Header>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Cancel</Button>
          </Modal.Close>
          <Button intent="danger">Delete</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Modal without footer
 */
export const WithoutFooter: Story = {
  render: () => (
    <Modal>
      <Modal.Trigger>
        <Button>Information Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Information</Modal.Title>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <p className="text-sm text-muted-foreground">
            This modal only has a header and body, no footer. The close button in the header can be
            used to dismiss it.
          </p>
        </Modal.Body>
      </Modal.Content>
    </Modal>
  ),
};

/**
 * Interactive test demonstrating modal open/close behavior.
 * This story verifies the modal can be opened via trigger and closed via cancel button.
 */
export const ModalInteractionTest: Story = {
  render: () => (
    <Modal>
      <Modal.Trigger>
        <Button>Open Test Modal</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Test Modal</Modal.Title>
          <Modal.Description>This modal is used for interaction testing.</Modal.Description>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <p className="text-sm text-muted-foreground">Modal content here.</p>
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close>
            <Button intent="secondary">Cancel</Button>
          </Modal.Close>
          <Button>Confirm</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // Find and click the trigger button to open modal
    const triggerButton = canvas.getByRole('button', {
      name: /open test modal/i,
    });
    await expect(triggerButton).toBeVisible();
    await userEvent.click(triggerButton);

    // Wait for modal to appear and verify it's visible
    // Note: Modal renders in a portal, so we need to query the document body
    const body = within(document.body);
    const dialog = await body.findByRole('dialog');
    await expect(dialog).toBeVisible();

    // Verify modal title is correct
    const title = body.getByText('Test Modal');
    await expect(title).toBeVisible();

    // Click the cancel button to close
    const cancelButton = body.getByRole('button', { name: /cancel/i });
    await userEvent.click(cancelButton);

    // Modal should be closed (dialog should not exist)
    await expect(body.queryByRole('dialog')).not.toBeInTheDocument();
  },
};

/**
 * Interactive test for keyboard accessibility - Escape to close.
 */
export const ModalKeyboardTest: Story = {
  render: () => (
    <Modal>
      <Modal.Trigger>
        <Button>Open for Keyboard Test</Button>
      </Modal.Trigger>
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>Keyboard Test Modal</Modal.Title>
          <Modal.Close />
        </Modal.Header>
        <Modal.Body>
          <p className="text-sm text-muted-foreground">Press Escape to close this modal.</p>
        </Modal.Body>
      </Modal.Content>
    </Modal>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // Open the modal
    const triggerButton = canvas.getByRole('button', {
      name: /open for keyboard test/i,
    });
    await userEvent.click(triggerButton);

    // Verify modal is open
    const body = within(document.body);
    const dialog = await body.findByRole('dialog');
    await expect(dialog).toBeVisible();

    // Press Escape to close
    await userEvent.keyboard('{Escape}');

    // Modal should be closed
    await expect(body.queryByRole('dialog')).not.toBeInTheDocument();
  },
};

import React, { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Switch } from './switch';

/**
 * Switch component for toggling between two states.
 * Built on Base UI primitives for accessibility.
 */
const meta: Meta<typeof Switch> = {
  title: 'Components/Switch',
  component: Switch,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the switch',
    },
    disabled: {
      control: 'boolean',
      description: 'Disables the switch',
    },
    checked: {
      control: 'boolean',
      description: 'Checked state',
    },
  },
  args: {
    size: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Switch>;

/**
 * Default unchecked switch.
 */
export const Default: Story = {
  args: {},
};

/**
 * Checked switch.
 */
export const Checked: Story = {
  args: {
    defaultChecked: true,
  },
};

/**
 * Disabled switch.
 */
export const Disabled: Story = {
  args: {
    disabled: true,
  },
};

/**
 * Disabled and checked.
 */
export const DisabledChecked: Story = {
  args: {
    disabled: true,
    defaultChecked: true,
  },
};

/**
 * Small switch.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    defaultChecked: true,
  },
};

/**
 * Large switch.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    defaultChecked: true,
  },
};

/**
 * Switch with label.
 */
export const WithLabel: Story = {
  render: () => (
    <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
      <Switch id="notifications" defaultChecked />
      <span>Enable notifications</span>
    </label>
  ),
};

/**
 * Controlled switch.
 */
export const Controlled: Story = {
  render: function ControlledRender() {
    const [checked, setChecked] = useState(false);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
          <Switch checked={checked} onCheckedChange={setChecked} />
          <span>Dark mode</span>
        </label>
        <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
          State: {checked ? 'On' : 'Off'}
        </p>
      </div>
    );
  },
};

/**
 * All switch sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Switch size="sm" defaultChecked />
        <span style={{ fontSize: '14px' }}>Small</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Switch size="md" defaultChecked />
        <span>Medium</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Switch size="lg" defaultChecked />
        <span style={{ fontSize: '18px' }}>Large</span>
      </label>
    </div>
  ),
};

/**
 * Settings form example.
 */
export const SettingsForm: Story = {
  render: function SettingsFormRender() {
    const [settings, setSettings] = useState({
      notifications: true,
      marketing: false,
      analytics: true,
    });

    const handleChange = (key: keyof typeof settings) => (checked: boolean) => {
      setSettings((prev) => ({ ...prev, [key]: checked }));
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '300px' }}>
        <h3 style={{ margin: 0 }}>Settings</h3>

        <label
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
          }}
        >
          <div>
            <p style={{ margin: 0, fontWeight: 500 }}>Email notifications</p>
            <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
              Receive email about your account
            </p>
          </div>
          <Switch
            checked={settings.notifications}
            onCheckedChange={handleChange('notifications')}
          />
        </label>

        <label
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
          }}
        >
          <div>
            <p style={{ margin: 0, fontWeight: 500 }}>Marketing emails</p>
            <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>Receive marketing emails</p>
          </div>
          <Switch checked={settings.marketing} onCheckedChange={handleChange('marketing')} />
        </label>

        <label
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
          }}
        >
          <div>
            <p style={{ margin: 0, fontWeight: 500 }}>Analytics</p>
            <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>Share usage data</p>
          </div>
          <Switch checked={settings.analytics} onCheckedChange={handleChange('analytics')} />
        </label>
      </div>
    );
  },
};

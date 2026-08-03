import React, { useState } from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { Tag } from './tag';

// Sample icon using foundation/icons
const UserIcon = () => <Icon name="user" size="sm" />;

/**
 * Tag component for labeling and categorization.
 * Supports optional dismiss functionality.
 */
const meta: Meta<typeof Tag> = {
  title: 'Components/Tag',
  component: Tag,
  tags: ['autodocs'],
  argTypes: {
    intent: {
      control: 'select',
      options: ['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info'],
      description: 'Visual style variant',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the tag',
    },
    dismissible: {
      control: 'boolean',
      description: 'Shows dismiss button',
    },
    children: {
      control: 'text',
      description: 'Tag content',
    },
  },
  args: {
    children: 'Tag',
    intent: 'default',
    size: 'md',
  },
};

export default meta;
type Story = StoryObj<typeof Tag>;

/**
 * Default tag.
 */
export const Default: Story = {
  args: {
    children: 'Default',
  },
};

/**
 * Primary tag.
 */
export const Primary: Story = {
  args: {
    intent: 'primary',
    children: 'Primary',
  },
};

/**
 * Secondary tag.
 */
export const Secondary: Story = {
  args: {
    intent: 'secondary',
    children: 'Secondary',
  },
};

/**
 * Success tag.
 */
export const Success: Story = {
  args: {
    intent: 'success',
    children: 'Active',
  },
};

/**
 * Warning tag.
 */
export const Warning: Story = {
  args: {
    intent: 'warning',
    children: 'Pending',
  },
};

/**
 * Danger tag.
 */
export const Danger: Story = {
  args: {
    intent: 'danger',
    children: 'Error',
  },
};

/**
 * Info tag.
 */
export const Info: Story = {
  args: {
    intent: 'info',
    children: 'Info',
  },
};

/**
 * Small tag.
 */
export const Small: Story = {
  args: {
    size: 'sm',
    children: 'Small',
  },
};

/**
 * Large tag.
 */
export const Large: Story = {
  args: {
    size: 'lg',
    children: 'Large',
  },
};

/**
 * Dismissible tag.
 */
export const Dismissible: Story = {
  args: {
    dismissible: true,
    children: 'Click X to dismiss',
    onDismiss: () => console.log('Dismissed!'),
  },
};

/**
 * Tag with start icon.
 */
export const WithStartIcon: Story = {
  args: {
    children: 'User',
    start: { children: <UserIcon /> },
  },
};

/**
 * All tag intents.
 */
export const AllIntents: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      <Tag intent="default">Default</Tag>
      <Tag intent="primary">Primary</Tag>
      <Tag intent="secondary">Secondary</Tag>
      <Tag intent="success">Success</Tag>
      <Tag intent="warning">Warning</Tag>
      <Tag intent="danger">Danger</Tag>
      <Tag intent="info">Info</Tag>
    </div>
  ),
};

/**
 * All tag sizes.
 */
export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
      <Tag size="sm">Small</Tag>
      <Tag size="md">Medium</Tag>
      <Tag size="lg">Large</Tag>
    </div>
  ),
};

/**
 * Interactive tags list.
 */
export const InteractiveTags: Story = {
  render: function InteractiveTagsRender() {
    const [tags, setTags] = useState(['React', 'TypeScript', 'Tailwind', 'Storybook']);

    const removeTag = (tagToRemove: string) => {
      setTags(tags.filter((tag) => tag !== tagToRemove));
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {tags.map((tag) => (
            <Tag key={tag} intent="primary" dismissible onDismiss={() => removeTag(tag)}>
              {tag}
            </Tag>
          ))}
        </div>
        {tags.length === 0 && <p style={{ margin: 0, color: '#666' }}>All tags removed</p>}
        {tags.length < 4 && (
          <button
            onClick={() => setTags(['React', 'TypeScript', 'Tailwind', 'Storybook'])}
            style={{
              padding: '8px 16px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              background: 'white',
              cursor: 'pointer',
              width: 'fit-content',
            }}
          >
            Reset tags
          </button>
        )}
      </div>
    );
  },
};

/**
 * Tag group example.
 */
export const TagGroup: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 500 }}>Categories</p>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Tag intent="primary">Technology</Tag>
          <Tag intent="primary">Design</Tag>
          <Tag intent="primary">Business</Tag>
        </div>
      </div>
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 500 }}>Status</p>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Tag intent="success">Published</Tag>
          <Tag intent="warning">Draft</Tag>
          <Tag intent="danger">Archived</Tag>
        </div>
      </div>
    </div>
  ),
};

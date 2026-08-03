import { useState } from 'react';

import type { Meta, StoryFn } from '@storybook/react';

import { Icon } from '@open-zentra/foundation-icons';

import { MultiSelect } from './multi-select';
import type { MultiSelectProps } from './types';

const meta: Meta<typeof MultiSelect> = {
  title: 'Components/MultiSelect',
  component: MultiSelect,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    feedback: {
      control: 'select',
      options: ['default', 'success', 'warning', 'error'],
    },
    disabled: {
      control: 'boolean',
    },
    searchable: {
      control: 'boolean',
    },
    showCounter: {
      control: 'boolean',
    },
  },
  decorators: [
    (Story) => (
      <div className="w-[300px]">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = { render: () => React.ReactElement } | { render: StoryFn<MultiSelectProps> };

const frameworkOptions = [
  { value: 'react', label: 'React' },
  { value: 'vue', label: 'Vue' },
  { value: 'angular', label: 'Angular' },
  { value: 'svelte', label: 'Svelte' },
  { value: 'solid', label: 'SolidJS' },
  { value: 'preact', label: 'Preact' },
  { value: 'qwik', label: 'Qwik' },
  { value: 'alpine', label: 'Alpine.js' },
];

/**
 * Default multi-select
 */
export const Default: Story = {
  render: function DefaultExample() {
    const [value, setValue] = useState<string[]>([]);

    return (
      <div className="space-y-4">
        <MultiSelect
          options={frameworkOptions}
          value={value}
          onValueChange={setValue}
          placeholder="Select frameworks..."
        />
        <div className="text-sm text-muted-foreground">
          Selected: {value.length > 0 ? value.join(', ') : 'None'}
        </div>
      </div>
    );
  },
};

/**
 * With search
 */
export const Searchable: Story = {
  render: function SearchableExample() {
    const [value, setValue] = useState<string[]>(['react']);

    return (
      <MultiSelect
        options={frameworkOptions}
        value={value}
        onValueChange={setValue}
        placeholder="Search and select..."
        searchable
      />
    );
  },
};

/**
 * With counter badge
 */
export const WithCounter: Story = {
  render: function CounterExample() {
    const [value, setValue] = useState<string[]>(['react', 'vue', 'angular']);

    return (
      <MultiSelect
        options={frameworkOptions}
        value={value}
        onValueChange={setValue}
        placeholder="Select frameworks..."
        showCounter
      />
    );
  },
};

/**
 * Different sizes
 */
export const Sizes: Story = {
  render: function SizesExample() {
    const [small, setSmall] = useState<string[]>(['react']);
    const [medium, setMedium] = useState<string[]>(['react']);
    const [large, setLarge] = useState<string[]>(['react']);

    return (
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-xs font-medium">Small</label>
          <MultiSelect
            options={frameworkOptions}
            value={small}
            onValueChange={setSmall}
            size="sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium">Medium</label>
          <MultiSelect
            options={frameworkOptions}
            value={medium}
            onValueChange={setMedium}
            size="md"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium">Large</label>
          <MultiSelect
            options={frameworkOptions}
            value={large}
            onValueChange={setLarge}
            size="lg"
          />
        </div>
      </div>
    );
  },
};

/**
 * Feedback states
 */
export const FeedbackStates: Story = {
  render: () => (
    <div className="space-y-4">
      <MultiSelect
        options={frameworkOptions}
        defaultValue={['react']}
        feedback="default"
        placeholder="Default"
      />
      <MultiSelect
        options={frameworkOptions}
        defaultValue={['react']}
        feedback="success"
        placeholder="Success"
      />
      <MultiSelect
        options={frameworkOptions}
        defaultValue={['react']}
        feedback="warning"
        placeholder="Warning"
      />
      <MultiSelect
        options={frameworkOptions}
        defaultValue={['react']}
        feedback="error"
        placeholder="Error"
      />
    </div>
  ),
};

/**
 * Disabled state
 */
export const Disabled: Story = {
  render: () => (
    <MultiSelect
      options={frameworkOptions}
      defaultValue={['react', 'vue']}
      disabled
      placeholder="Disabled"
    />
  ),
};

/**
 * With disabled options
 */
export const DisabledOptions: Story = {
  render: function DisabledOptionsExample() {
    const [value, setValue] = useState<string[]>([]);

    const optionsWithDisabled = [
      { value: 'react', label: 'React' },
      { value: 'vue', label: 'Vue' },
      { value: 'angular', label: 'Angular (Disabled)', disabled: true },
      { value: 'svelte', label: 'Svelte' },
      { value: 'solid', label: 'SolidJS (Disabled)', disabled: true },
    ];

    return (
      <MultiSelect
        options={optionsWithDisabled}
        value={value}
        onValueChange={setValue}
        placeholder="Some options disabled"
      />
    );
  },
};

/**
 * With custom start icon
 */
export const WithIcon: Story = {
  render: function IconExample() {
    const [value, setValue] = useState<string[]>([]);

    return (
      <MultiSelect
        options={frameworkOptions}
        value={value}
        onValueChange={setValue}
        placeholder="Select frameworks..."
        start={<Icon name="layers" className="h-4 w-4 opacity-50" />}
      />
    );
  },
};

/**
 * Full featured example
 */
export const FullFeatured: Story = {
  render: function FullFeaturedExample() {
    const [value, setValue] = useState<string[]>(['react', 'vue']);

    return (
      <div className="space-y-4">
        <MultiSelect
          options={frameworkOptions}
          value={value}
          onValueChange={setValue}
          placeholder="Select frameworks..."
          searchable
          showCounter
          start={<Icon name="code" className="h-4 w-4 opacity-50" />}
          label="Select JavaScript frameworks"
        />
        <div className="rounded border bg-muted/50 p-3 text-xs">
          <p className="font-medium">Selected frameworks:</p>
          {value.length > 0 ? (
            <ul className="mt-1 list-inside list-disc">
              {value.map((v) => (
                <li key={v}>{frameworkOptions.find((o) => o.value === v)?.label}</li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground">None selected</p>
          )}
        </div>
      </div>
    );
  },
};

/**
 * Many options (with scroll)
 */
export const ManyOptions: Story = {
  render: function ManyOptionsExample() {
    const [value, setValue] = useState<string[]>([]);

    const manyOptions = Array.from({ length: 30 }, (_, i) => ({
      value: `option-${i + 1}`,
      label: `Option ${i + 1}`,
    }));

    return (
      <MultiSelect
        options={manyOptions}
        value={value}
        onValueChange={setValue}
        placeholder="Select options..."
        searchable
        showCounter
        maxHeight={200}
      />
    );
  },
};

/**
 * Form field example
 */
export const FormField: Story = {
  render: function FormFieldExample() {
    const [value, setValue] = useState<string[]>([]);

    return (
      <div className="space-y-2">
        <label className="text-sm font-medium">
          Programming Languages <span className="text-red-500">*</span>
        </label>
        <MultiSelect
          options={[
            { value: 'js', label: 'JavaScript' },
            { value: 'ts', label: 'TypeScript' },
            { value: 'py', label: 'Python' },
            { value: 'go', label: 'Go' },
            { value: 'rust', label: 'Rust' },
            { value: 'java', label: 'Java' },
          ]}
          value={value}
          onValueChange={setValue}
          placeholder="Select languages you know..."
          searchable
          feedback={value.length === 0 ? 'error' : 'default'}
        />
        {value.length === 0 && (
          <p className="text-xs text-red-500">Please select at least one language</p>
        )}
      </div>
    );
  },
};

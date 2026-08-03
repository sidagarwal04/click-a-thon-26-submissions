import type { Meta, StoryObj } from '@storybook/react';

import { ScrollArea } from './scroll-area';

const meta = {
  title: 'Components/ScrollArea',
  component: ScrollArea,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    orientation: {
      control: 'select',
      options: ['vertical', 'horizontal', 'both'],
    },
    type: {
      control: 'select',
      options: ['hover', 'scroll', 'always'],
    },
  },
} satisfies Meta<typeof ScrollArea>;

export default meta;
type Story = StoryObj<typeof meta>;

const longContent = `
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor 
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis 
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore 
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt 
in culpa qui officia deserunt mollit anim id est laborum.

Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium 
doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore 
veritatis et quasi architecto beatae vitae dicta sunt explicabo.

Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, 
sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.

Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, 
adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et 
dolore magnam aliquam quaerat voluptatem.
`.trim();

/**
 * Default vertical scroll area
 */
export const Default: Story = {
  render: () => (
    <ScrollArea height={200} className="w-[350px] rounded-md border p-4">
      <div className="text-sm">{longContent}</div>
    </ScrollArea>
  ),
};

/**
 * Always visible scrollbar
 */
export const AlwaysVisible: Story = {
  render: () => (
    <ScrollArea type="always" height={200} className="w-[350px] rounded-md border p-4">
      <div className="text-sm">{longContent}</div>
    </ScrollArea>
  ),
};

/**
 * Horizontal scroll
 */
export const Horizontal: Story = {
  render: () => (
    <ScrollArea orientation="horizontal" className="w-[350px] rounded-md border">
      <div className="flex gap-4 p-4">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="flex h-20 w-20 shrink-0 items-center justify-center rounded-md bg-muted"
          >
            {i + 1}
          </div>
        ))}
      </div>
    </ScrollArea>
  ),
};

/**
 * Both scrollbars
 */
export const Both: Story = {
  render: () => (
    <ScrollArea orientation="both" height={200} className="w-[350px] rounded-md border">
      <div className="w-[600px] p-4">
        <table className="w-full">
          <thead>
            <tr>
              {Array.from({ length: 10 }).map((_, i) => (
                <th key={i} className="whitespace-nowrap border px-4 py-2 text-left">
                  Column {i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 20 }).map((_, rowIndex) => (
              <tr key={rowIndex}>
                {Array.from({ length: 10 }).map((_, colIndex) => (
                  <td key={colIndex} className="whitespace-nowrap border px-4 py-2">
                    Cell {rowIndex + 1}-{colIndex + 1}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ScrollArea>
  ),
};

/**
 * List example
 */
export const ListExample: Story = {
  render: () => (
    <ScrollArea height={300} className="w-[300px] rounded-md border">
      <div className="p-4">
        <h4 className="mb-4 text-sm font-medium">Notifications</h4>
        <div className="space-y-3">
          {Array.from({ length: 15 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg p-3 hover:bg-muted">
              <div className="h-8 w-8 rounded-full bg-primary/10" />
              <div className="flex-1">
                <p className="text-sm font-medium">Notification {i + 1}</p>
                <p className="text-xs text-muted-foreground">This is a notification message</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </ScrollArea>
  ),
};

/**
 * Tags example (horizontal)
 */
export const TagsExample: Story = {
  render: () => (
    <div className="w-[300px]">
      <ScrollArea orientation="horizontal" className="rounded-md border">
        <div className="flex gap-2 p-4">
          {[
            'JavaScript',
            'TypeScript',
            'React',
            'Vue',
            'Angular',
            'Svelte',
            'Node.js',
            'Express',
            'Next.js',
            'Nuxt',
            'Tailwind',
            'CSS',
            'HTML',
          ].map((tag) => (
            <span
              key={tag}
              className="inline-flex shrink-0 rounded-full bg-primary/10 px-3 py-1 text-sm text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      </ScrollArea>
    </div>
  ),
};

/**
 * Max height with dynamic content
 */
export const MaxHeight: Story = {
  render: () => (
    <ScrollArea maxHeight={200} className="w-[350px] rounded-md border p-4">
      <div className="text-sm">
        {longContent}
        <br />
        <br />
        {longContent}
      </div>
    </ScrollArea>
  ),
};

/**
 * Scrollbar visibility comparison
 */
export const TypeComparison: Story = {
  render: () => (
    <div className="flex gap-4">
      <div>
        <p className="mb-2 text-sm font-medium">Hover (default)</p>
        <ScrollArea type="hover" height={150} className="w-[200px] rounded-md border p-4">
          <div className="text-sm">{longContent}</div>
        </ScrollArea>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Scroll</p>
        <ScrollArea type="scroll" height={150} className="w-[200px] rounded-md border p-4">
          <div className="text-sm">{longContent}</div>
        </ScrollArea>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Always</p>
        <ScrollArea type="always" height={150} className="w-[200px] rounded-md border p-4">
          <div className="text-sm">{longContent}</div>
        </ScrollArea>
      </div>
    </div>
  ),
};

# Foundation Icons

A thin, extensible wrapper over [lucide-react](https://lucide.dev/) icons with Tailwind-driven sizing and styling. This library provides a consistent icon API across the application.

## Features

- 🎨 **Tailwind-driven sizing** - Use predefined size variants that map to Tailwind classes
- 🎨 **Tailwind-driven colors** - Apply any Tailwind color classes via `className`
- 📦 **Tree-shaking support** - Only import icons you use
- 🔧 **Extensible** - Easily add custom icons to the registry
- ♿ **Accessible** - Built-in ARIA support
- 🎯 **Type-safe** - Full TypeScript support

## Installation

The library is already part of the monorepo. Import it in your components:

```tsx
import { Icon } from '@open-zentra/foundation-icons';
```

## Basic Usage

```tsx
import { Icon } from '@open-zentra/foundation-icons';

// Simple icon
<Icon name="home" />

// With size
<Icon name="search" size="lg" />

// With Tailwind color classes
<Icon name="user" className="text-blue-500" />

// Interactive icon
<Icon
  name="settings"
  onClick={handleClick}
  aria-label="Settings"
/>
```

## Size Variants

The library provides a comprehensive set of size variants that map to Tailwind spacing:

| Size   | Tailwind Classes | Pixel Size (approx) |
| ------ | ---------------- | ------------------- |
| `4xs`  | `h-1 w-1`        | 4x4px               |
| `3xs`  | `h-2 w-2`        | 8x8px               |
| `2xs`  | `h-2.5 w-2.5`    | 10x10px             |
| `xs`   | `h-3 w-3`        | 12x12px             |
| `sm`   | `h-3.5 w-3.5`    | 14x14px             |
| `base` | `h-4 w-4`        | 16x16px (default)   |
| `lg`   | `h-5 w-5`        | 20x20px             |
| `xl`   | `h-6 w-6`        | 24x24px             |
| `2xl`  | `h-8 w-8`        | 32x32px             |
| `3xl`  | `h-9 w-9`        | 36x36px             |
| `4xl`  | `h-10 w-10`      | 40x40px             |
| `5xl`  | `h-12 w-12`      | 48x48px             |
| `9xl`  | `h-16 w-16`      | 64x64px             |
| `12xl` | `h-24 w-24`      | 96x96px             |
| `16xl` | `h-44 w-44`      | 176x176px           |
| `24xl` | `h-56 w-56`      | 224x224px           |
| `full` | `h-full w-full`  | 100% of parent      |

```tsx
<Icon name="home" size="sm" />
<Icon name="home" size="base" />
<Icon name="home" size="lg" />
<Icon name="home" size="xl" />
```

## Styling

### Colors

Apply Tailwind color classes via the `className` prop:

```tsx
// Text color
<Icon name="home" className="text-blue-500" />
<Icon name="search" className="text-red-600" />

// With hover states
<Icon name="heart" className="text-gray-400 hover:text-red-500" />
```

### Custom SVG Styling

Use the `iconClassName` prop to style the SVG element directly:

```tsx
// Control fill and stroke
<Icon
  name="star"
  iconClassName="fill-current stroke-2"
/>

// Custom stroke width
<Icon
  name="circle"
  iconClassName="stroke-2"
/>
```

### Combining Classes

```tsx
<Icon
  name="settings"
  className="text-gray-600 hover:text-blue-500 transition-colors"
  iconClassName="stroke-2"
/>
```

## Available Icons

The library comes with 100+ common UI icons pre-registered. Here are some categories:

### Navigation

- `home`, `menu`, `chevron-left`, `chevron-right`, `chevron-up`, `chevron-down`
- `arrow-left`, `arrow-right`, `arrow-up`, `arrow-down`
- `navigation`, `navigation-2`, `compass`

### Actions

- `search`, `plus`, `minus`, `edit`, `edit-2`, `edit-3`
- `trash`, `trash-2`, `save`, `copy`, `scissors`
- `download`, `upload`, `share`, `share-2`, `send`
- `filter`, `sort-asc`, `sort-desc`

### Status

- `alert-circle`, `alert-triangle`, `info`
- `check-circle`, `x-circle`, `help-circle`
- `clock`, `calendar`, `bell`, `bell-off`
- `star`, `heart`, `thumbs-up`, `thumbs-down`

### UI Elements

- `user`, `users`, `user-plus`, `user-minus`
- `lock`, `unlock`, `eye`, `eye-off`
- `settings`, `cog`, `wrench`
- `grid`, `list`, `layout`, `sidebar`

See the full list in [`src/icons/index.ts`](./src/icons/index.ts).

## API Reference

### Icon Component

```tsx
<Icon
  name: IconName          // Required: Name of the icon
  size?: IconSizeType     // Optional: Size variant (default: 'base')
  className?: string      // Optional: Tailwind classes for wrapper
  iconClassName?: string  // Optional: Tailwind classes for SVG
  onClick?: MouseEventHandler<HTMLElement>
  style?: CSSProperties
  'data-testid'?: string
  'aria-label'?: string   // Required for interactive icons
  'aria-hidden'?: boolean // Default: true (unless aria-label provided)
/>
```

### IconName

Type representing all available icon names. This is a union type that includes all registered icons.

### IconSizeType

```ts
type IconSizeType =
  | '4xs'
  | '3xs'
  | '2xs'
  | 'xs'
  | 'sm'
  | 'base'
  | 'lg'
  | 'xl'
  | '2xl'
  | '3xl'
  | '4xl'
  | '5xl'
  | '9xl'
  | '12xl'
  | '16xl'
  | '24xl'
  | 'full';
```

## Extending the Icon Set

### Registering Custom Icons

You can add custom icons to the registry:

```tsx
import { CustomIcon } from 'lucide-react';

import { registerIcon } from '@open-zentra/foundation-icons';

// Register a new icon
registerIcon({
  name: 'custom-icon',
  component: CustomIcon,
});

// Now use it
<Icon name="custom-icon" />;
```

### Adding Icons from Lucide

To add more icons from lucide-react:

1. Import the icon component from `lucide-react`
2. Register it using `registerIcon`
3. Use it in your components

```tsx
import { Sparkles, Zap } from 'lucide-react';

import { registerIcon } from '@open-zentra/foundation-icons';

registerIcon({ name: 'zap', component: Zap });
registerIcon({ name: 'sparkles', component: Sparkles });
```

### Registry Utilities

```tsx
import {
  clearRegistry,
  getAllIconNames,
  getIcon,
  hasIcon,
  registerIcon,
} from '@open-zentra/foundation-icons';

// Check if icon exists
if (hasIcon('home')) {
  // Icon is registered
}

// Get icon component directly
const HomeIcon = getIcon('home');

// Get all registered icon names
const allIcons = getAllIconNames();
// ['home', 'search', 'user', ...]

// Clear registry (useful for testing)
clearRegistry();
```

## Accessibility

Icons are decorative by default and hidden from screen readers. For interactive icons, always provide an `aria-label`:

```tsx
// Decorative icon (hidden from screen readers)
<Icon name="check" />

// Interactive icon (accessible)
<Icon
  name="settings"
  onClick={handleClick}
  aria-label="Open settings"
/>
```

## Examples

### Button with Icon

```tsx
<button className="flex items-center gap-2">
  <Icon name="plus" size="sm" className="text-white" />
  Add Item
</button>
```

### Icon-Only Button

```tsx
<button>
  <Icon name="x" size="lg" className="text-gray-500 hover:text-gray-700" aria-label="Close" />
</button>
```

### Status Indicators

```tsx
<div className="flex items-center gap-2">
  <Icon name="check-circle" className="text-green-500" />
  <span>Success</span>
</div>
```

### Loading State

```tsx
<Icon name="loader-2" className="animate-spin text-blue-500" />
```

## Development

```bash
# Build the library
npx nx build foundation-icons

# Run tests
npx nx test foundation-icons

# Lint
npx nx lint foundation-icons
```

## Architecture

The library is structured as follows:

- **`icon.tsx`** - Main Icon component
- **`icon.ts`** - TypeScript type definitions
- **`constants.ts`** - Size constants and ICON_SIZE_MAPPER
- **`icons/registry.ts`** - Icon registry system
- **`icons/index.ts`** - Icon initialization and exports

## License

MIT

# OpenZentra Design System

A fully extensible, enterprise-grade design system built with Base UI primitives, Tailwind CSS, and TypeScript.

## Key Features

- **Tailwind-Native Tokens** - All design tokens defined in CSS via Tailwind 4's `@theme` directive
- **ThemeProvider = Single Source of Truth** - Every component's styling fully configurable from top level
- **Enterprise-Grade** - WCAG 2.1 AA accessibility, strict TypeScript, SSR/RSC compatible
- **Fully Extensible** - Module augmentation for custom components, nested themes for overrides
- **Zero Runtime CSS** - Pure Tailwind utilities, no CSS-in-JS overhead
- **Open Zentra ID (ozid)** - Every component supports `data-ozid` for testing, analytics, and debugging

## Installation

```bash
npm install @open-zentra/foundation-design-system
```

## Quick Start

```tsx
import { Button, ThemeProvider } from '@open-zentra/foundation-design-system';

import '@open-zentra/foundation-design-system/tokens/tokens.scss';

const theme = {
  components: {
    button: {
      root: {
        base: 'inline-flex items-center justify-center font-medium rounded-md',
        variants: {
          intent: {
            primary: 'bg-primary text-white hover:bg-primary-hover',
            secondary: 'bg-secondary text-foreground hover:bg-secondary-hover',
          },
          size: {
            sm: 'h-8 px-3 text-sm',
            md: 'h-10 px-4',
            lg: 'h-12 px-6 text-lg',
          },
        },
      },
      defaultVariants: {
        intent: 'primary',
        size: 'md',
      },
    },
  },
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <Button intent="primary" ozid="main-action">
        Click me
      </Button>
    </ThemeProvider>
  );
}
```

## Components

### Form Components

- `Button` - Versatile button with loading states and icons
- `IconButton` - Icon-only button (requires aria-label)
- `Input` - Text input with adornments and validation
- `Textarea` - Multi-line text input
- `Checkbox` - Base UI checkbox with indeterminate support
- `RadioGroup` - Base UI radio group (compound)
- `Switch` - Base UI toggle switch
- `Select` - Base UI dropdown select (compound)

### Feedback Components

- `Badge` - Status labels
- `Tag` - Dismissible tags
- `Spinner` - Loading indicator
- `Skeleton` - Loading placeholder
- `Progress` - Progress bar

## Theme Configuration

Every component can be fully customized via ThemeProvider:

```tsx
const theme = {
  // Override design tokens
  tokens: {
    colors: {
      primary: '#8b5cf6',
    },
  },
  components: {
    button: {
      root: {
        base: '...', // Base classes
        variants: {
          intent: {
            primary: '...',
            secondary: '...',
          },
        },
        modifiers: {
          disabled: {
            true: 'opacity-50',
            false: '',
          },
        },
        compoundVariants: [
          {
            intent: 'primary',
            disabled: true,
            className: '...',
          },
        ],
      },
      slots: {
        startIcon: { base: '...', variants: {} },
      },
      defaultVariants: {
        intent: 'primary',
        size: 'md',
      },
    },
  },
};
```

## Nx Generator

Generate new components:

```bash
npx nx g @open-zentra/design-system-plugin:component MyComponent \
  --variants="intent:primary,secondary;size:sm,md,lg" \
  --modifiers="disabled,loading" \
  --slots="icon" \
  --rootElement="button"
```

## Development

```bash
# Build the library
npx nx build foundation-design-system

# Run tests
npx nx test foundation-design-system

# Lint
npx nx lint foundation-design-system
```

## License

MIT

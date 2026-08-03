import { describeComponent } from '../../test/describe-component';
import { Tooltip, TooltipModifiers, TooltipVariants } from './index';

describeComponent(
  <Tooltip content="Tooltip text">
    <button>Hover me</button>
  </Tooltip>,
  {
    name: 'Tooltip',
    rootInstanceOf: window.HTMLDivElement,
    variants: TooltipVariants,
    modifiers: TooltipModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // The tooltip's root element is its popup — that is what theme.root styles
    // and the only div in the tree — so it only exists while open.
    renderRoot: (rootProps) => (
      <Tooltip open content="Tooltip text" {...rootProps}>
        <button>Hover me</button>
      </Tooltip>
    ),
  },
);

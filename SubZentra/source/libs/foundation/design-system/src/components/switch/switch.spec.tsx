import { describeComponent } from '../../test/describe-component';
import { Switch, SwitchModifiers, SwitchVariants } from './index';

describeComponent(<Switch />, {
  name: 'Switch',
  // Base UI's Switch.Root renders a span with role="switch", not a button.
  rootInstanceOf: window.HTMLSpanElement,
  variants: SwitchVariants,
  modifiers: SwitchModifiers,
  shouldSupportPolymorphism: false,
  shouldSupportForwardRef: true,
});

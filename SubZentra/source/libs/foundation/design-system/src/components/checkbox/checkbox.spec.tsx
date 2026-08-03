import { describeComponent } from '../../test/describe-component';
import { Checkbox, CheckboxModifiers, CheckboxVariants } from './index';

describeComponent(<Checkbox />, {
  name: 'Checkbox',
  // Base UI's Checkbox.Root renders a span with role="checkbox", not a button.
  rootInstanceOf: window.HTMLSpanElement,
  variants: CheckboxVariants,
  modifiers: CheckboxModifiers,
  shouldSupportPolymorphism: false,
  shouldSupportForwardRef: true,
});

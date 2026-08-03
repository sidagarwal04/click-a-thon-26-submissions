import { describeComponent } from '../../test/describe-component';
import { Spinner, SpinnerModifiers, SpinnerVariants } from './index';

describeComponent(<Spinner />, {
  name: 'Spinner',
  rootInstanceOf: window.HTMLSpanElement,
  variants: SpinnerVariants,
  modifiers: SpinnerModifiers,
  shouldSupportPolymorphism: true,
});

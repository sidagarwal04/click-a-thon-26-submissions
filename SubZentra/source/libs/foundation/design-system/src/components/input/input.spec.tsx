import { describeComponent } from '../../test/describe-component';
import { Input, InputModifiers, InputVariants } from './index';

describeComponent(<Input />, {
  name: 'Input',
  rootInstanceOf: window.HTMLInputElement,
  variants: InputVariants,
  modifiers: InputModifiers,
  shouldSupportPolymorphism: false,
  shouldSupportForwardRef: true,
});

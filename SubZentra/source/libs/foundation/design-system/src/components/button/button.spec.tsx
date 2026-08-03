import { describeComponent } from '../../test/describe-component';
import { Button, ButtonModifiers, ButtonVariants } from './index';

describeComponent(<Button>Click me</Button>, {
  name: 'Button',
  rootInstanceOf: window.HTMLButtonElement,
  variants: ButtonVariants,
  modifiers: ButtonModifiers,
  shouldSupportPolymorphism: true,
});

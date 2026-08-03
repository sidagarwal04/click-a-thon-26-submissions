import { describeComponent } from '../../test/describe-component';
import { IconButton, IconButtonModifiers, IconButtonVariants } from './index';

describeComponent(<IconButton aria-label="action">X</IconButton>, {
  name: 'IconButton',
  rootInstanceOf: window.HTMLButtonElement,
  variants: IconButtonVariants,
  modifiers: IconButtonModifiers,
  shouldSupportPolymorphism: true,
});

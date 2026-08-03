import { describeComponent } from '../../test/describe-component';
import { Textarea, TextareaModifiers, TextareaVariants } from './index';

describeComponent(<Textarea />, {
  name: 'Textarea',
  rootInstanceOf: window.HTMLTextAreaElement,
  variants: TextareaVariants,
  modifiers: TextareaModifiers,
  shouldSupportPolymorphism: false,
  shouldSupportForwardRef: true,
});

import { describeComponent } from '../../test/describe-component';
import { Toast, ToastModifiers, ToastVariants } from './index';

describeComponent(<Toast>Toast message</Toast>, {
  name: 'Toast',
  rootInstanceOf: window.HTMLDivElement,
  variants: ToastVariants,
  modifiers: ToastModifiers,
  shouldSupportPolymorphism: true,
});

import { describeComponent } from '../../test/describe-component';
import { Loader, LoaderModifiers, LoaderVariants } from './index';

describeComponent(<Loader />, {
  name: 'Loader',
  rootInstanceOf: window.HTMLDivElement,
  variants: LoaderVariants,
  modifiers: LoaderModifiers,
  shouldSupportPolymorphism: true,
});

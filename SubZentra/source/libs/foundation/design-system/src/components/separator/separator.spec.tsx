import { describeComponent } from '../../test/describe-component';
import { Separator, SeparatorModifiers, SeparatorVariants } from './index';

describeComponent(<Separator />, {
  name: 'Separator',
  rootInstanceOf: window.HTMLDivElement,
  variants: SeparatorVariants,
  modifiers: SeparatorModifiers,
  shouldSupportPolymorphism: true,
});

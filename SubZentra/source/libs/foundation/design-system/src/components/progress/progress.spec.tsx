import { describeComponent } from '../../test/describe-component';
import { Progress, ProgressModifiers, ProgressVariants } from './index';

describeComponent(<Progress value={50} />, {
  name: 'Progress',
  rootInstanceOf: window.HTMLDivElement,
  variants: ProgressVariants,
  modifiers: ProgressModifiers,
  shouldSupportPolymorphism: false,
});

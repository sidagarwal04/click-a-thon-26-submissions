import { describeComponent } from '../../test/describe-component';
import { Label, LabelModifiers, LabelVariants } from './index';

describeComponent(<Label>Field label</Label>, {
  name: 'Label',
  rootInstanceOf: window.HTMLLabelElement,
  variants: LabelVariants,
  modifiers: LabelModifiers,
  shouldSupportPolymorphism: true,
});

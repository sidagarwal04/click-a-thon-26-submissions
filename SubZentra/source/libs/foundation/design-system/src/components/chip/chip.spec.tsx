import { describeComponent } from '../../test/describe-component';
import { Chip, ChipModifiers, ChipVariants } from './index';

describeComponent(<Chip>Chip label</Chip>, {
  name: 'Chip',
  rootInstanceOf: window.HTMLSpanElement,
  variants: ChipVariants,
  modifiers: ChipModifiers,
  shouldSupportPolymorphism: true,
});

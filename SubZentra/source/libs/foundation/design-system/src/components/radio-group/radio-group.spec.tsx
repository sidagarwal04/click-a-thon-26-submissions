import { describeComponent } from '../../test/describe-component';
import { RadioGroup, RadioGroupModifiers, RadioGroupVariants } from './index';

describeComponent(
  <RadioGroup>
    <div>Radio option</div>
  </RadioGroup>,
  {
    name: 'RadioGroup',
    rootInstanceOf: window.HTMLDivElement,
    variants: RadioGroupVariants,
    modifiers: RadioGroupModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
  },
);

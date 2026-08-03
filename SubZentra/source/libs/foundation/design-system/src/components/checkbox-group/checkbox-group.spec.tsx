import { describeComponent } from '../../test/describe-component';
import { CheckboxGroup, CheckboxGroupModifiers, CheckboxGroupVariants } from './index';

describeComponent(
  <CheckboxGroup>
    <div>Item 1</div>
  </CheckboxGroup>,
  {
    name: 'CheckboxGroup',
    rootInstanceOf: window.HTMLDivElement,
    variants: CheckboxGroupVariants,
    modifiers: CheckboxGroupModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
  },
);

import { describeComponent } from '../../test/describe-component';
import { MultiSelect, MultiSelectModifiers, MultiSelectVariants } from './index';

describeComponent(
  <MultiSelect options={[]} value={[]} onChange={() => undefined}>
    <div>MultiSelect</div>
  </MultiSelect>,
  {
    name: 'MultiSelect',
    rootInstanceOf: window.HTMLDivElement,
    variants: MultiSelectVariants,
    modifiers: MultiSelectModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: false,
  },
);

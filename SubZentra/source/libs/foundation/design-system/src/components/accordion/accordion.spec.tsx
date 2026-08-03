import { describeComponent } from '../../test/describe-component';
import { Accordion, AccordionModifiers, AccordionVariants } from './index';

describeComponent(
  <Accordion>
    <div>Accordion content</div>
  </Accordion>,
  {
    name: 'Accordion',
    rootInstanceOf: window.HTMLDivElement,
    variants: AccordionVariants,
    modifiers: AccordionModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
  },
);

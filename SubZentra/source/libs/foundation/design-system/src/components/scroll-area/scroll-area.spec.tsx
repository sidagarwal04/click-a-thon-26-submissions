import { describeComponent } from '../../test/describe-component';
import { ScrollArea, ScrollAreaModifiers, ScrollAreaVariants } from './index';

describeComponent(
  <ScrollArea>
    <div>Scrollable content</div>
  </ScrollArea>,
  {
    name: 'ScrollArea',
    rootInstanceOf: window.HTMLDivElement,
    variants: ScrollAreaVariants,
    modifiers: ScrollAreaModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
  },
);

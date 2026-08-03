import { describeComponent } from '../../test/describe-component';
import { Tabs, TabsModifiers, TabsVariants } from './index';

describeComponent(
  <Tabs defaultValue="tab1">
    <div>Tab content</div>
  </Tabs>,
  {
    name: 'Tabs',
    rootInstanceOf: window.HTMLDivElement,
    variants: TabsVariants,
    modifiers: TabsModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
  },
);

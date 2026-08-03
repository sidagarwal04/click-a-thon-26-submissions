import { describeComponent } from '../../test/describe-component';
import { Badge, BadgeModifiers, BadgeVariants } from './index';

describeComponent(<Badge>Label</Badge>, {
  name: 'Badge',
  rootInstanceOf: window.HTMLSpanElement,
  variants: BadgeVariants,
  modifiers: BadgeModifiers,
  shouldSupportPolymorphism: true,
});

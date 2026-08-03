import { describeComponent } from '../../test/describe-component';
import { Tag, TagModifiers, TagVariants } from './index';

describeComponent(<Tag>Tag label</Tag>, {
  name: 'Tag',
  rootInstanceOf: window.HTMLSpanElement,
  variants: TagVariants,
  modifiers: TagModifiers,
  shouldSupportPolymorphism: true,
});

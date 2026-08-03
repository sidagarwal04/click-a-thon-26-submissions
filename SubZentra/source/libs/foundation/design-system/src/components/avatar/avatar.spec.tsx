import { describeComponent } from '../../test/describe-component';
import { Avatar, AvatarModifiers, AvatarVariants } from './index';

describeComponent(<Avatar name="John Doe" />, {
  name: 'Avatar',
  rootInstanceOf: window.HTMLDivElement,
  variants: AvatarVariants,
  modifiers: AvatarModifiers,
  shouldSupportPolymorphism: true,
});

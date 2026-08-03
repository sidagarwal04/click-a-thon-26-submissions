import { describeComponent } from '../../test/describe-component';
import { Skeleton, SkeletonModifiers, SkeletonVariants } from './index';

describeComponent(<Skeleton />, {
  name: 'Skeleton',
  rootInstanceOf: window.HTMLDivElement,
  variants: SkeletonVariants,
  modifiers: SkeletonModifiers,
  shouldSupportPolymorphism: true,
});

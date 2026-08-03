import { describeComponent } from '../../test/describe-component';
import { Banner, BannerModifiers, BannerVariants } from './index';

describeComponent(<Banner>Banner content</Banner>, {
  name: 'Banner',
  rootInstanceOf: window.HTMLDivElement,
  variants: BannerVariants,
  modifiers: BannerModifiers,
  shouldSupportPolymorphism: true,
});

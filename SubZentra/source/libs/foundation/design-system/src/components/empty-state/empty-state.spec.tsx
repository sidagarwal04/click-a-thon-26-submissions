import { describeComponent } from '../../test/describe-component';
import { EmptyState, EmptyStateModifiers, EmptyStateVariants } from './index';

describeComponent(<EmptyState>No data</EmptyState>, {
  name: 'EmptyState',
  rootInstanceOf: window.HTMLDivElement,
  variants: EmptyStateVariants,
  modifiers: EmptyStateModifiers,
  shouldSupportPolymorphism: true,
});

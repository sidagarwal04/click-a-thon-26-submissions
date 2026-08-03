import { describeComponent } from '../../test/describe-component';
import { Alert, AlertModifiers, AlertVariants } from './index';

describeComponent(
  <Alert>Test Content</Alert>,
  {
    name: 'Alert',
    rootInstanceOf: window.HTMLDivElement,
    variants: AlertVariants,
    modifiers: AlertModifiers,
    shouldSupportPolymorphism: true,
  },
  () => {
    // Add custom tests here
  },
);

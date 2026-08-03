import { render, screen } from '@testing-library/react';

import { describeComponent } from '../../test/describe-component';
import { Card, CardModifiers, CardVariants } from './index';

describeComponent(<Card>Panel</Card>, {
  name: 'Card',
  rootInstanceOf: window.HTMLElement,
  variants: CardVariants,
  modifiers: CardModifiers,
  shouldSupportPolymorphism: true,
});

describe('Card composition', () => {
  it('renders the title inside the header row', () => {
    const { container } = render(
      <Card>
        <Card.Header icon={<svg />}>
          <Card.Title>Security protocols</Card.Title>
        </Card.Header>
      </Card>,
    );

    const title = screen.getByRole('heading', { name: 'Security protocols' });
    expect(title.closest('[data-slot="header"]')).not.toBeNull();
    expect(container.querySelector('[data-slot="headerIcon"] svg')).not.toBeNull();
  });

  it('renders trailing header content after the title', () => {
    render(
      <Card>
        <Card.Header end={<span>Reset defaults</span>}>
          <Card.Title>System notifications</Card.Title>
        </Card.Header>
      </Card>,
    );

    expect(screen.getByText('Reset defaults')).toBeTruthy();
  });
});

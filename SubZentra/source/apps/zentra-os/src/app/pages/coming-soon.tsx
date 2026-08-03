import { Button, EmptyState } from '@open-zentra/foundation-design-system';
import { Icon, type IconName } from '@open-zentra/foundation-icons';
import { Link } from 'react-router-dom';

interface ComingSoonProps {
  readonly title: string;
  readonly icon: IconName;
  readonly description: string;
}

/**
 * A destination the rail already names but Phase 2 has not built.
 *
 * Said plainly rather than mocked up: a page that looks finished and does
 * nothing is harder to trust than one that admits what it is.
 */
export const ComingSoon = ({ title, icon, description }: ComingSoonProps) => (
  <section className="px-8 py-10">
    <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
      Phase 2
    </p>
    <h1 className="mt-3 font-serif text-[clamp(2rem,4vw,3rem)] font-normal tracking-[-0.035em]">
      {title}
    </h1>

    <EmptyState className="mt-12 border border-border bg-card" size="lg" icon={<Icon name={icon} size="xl" />}>
      <EmptyState.Title>{title} is not built yet</EmptyState.Title>
      <EmptyState.Description>{description}</EmptyState.Description>
      <EmptyState.Actions>
        <Button component={Link} to="/" intent="secondary">
          Back to investigations
        </Button>
      </EmptyState.Actions>
    </EmptyState>
  </section>
);
